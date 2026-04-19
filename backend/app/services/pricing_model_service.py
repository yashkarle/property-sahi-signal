"""Orchestrates the full BuyerEdge-style pricing pipeline.

Calls the dhub PyMC skill for Bayesian posterior sampling,
then applies our differentiating subjective adjustments.
"""
import asyncio
import hashlib
import json
from datetime import date
from typing import Any

import httpx

from app.config import settings
from app.ml.comparables import select_comparables
from app.ml.confidence_scoring import compute_caf, compute_raw_confidence
from app.ml.distribution import compute_distribution
from app.ml.final_constraints import apply_final_constraints
from app.ml.offer_band import derive_offer_band
from app.ml.sealed_bid_prob import compute_sealed_bid_probability
from app.ml.seller_leverage import compute_seller_leverage
from app.ml.similarity_scoring import score_comparables
from app.ml.subjective_adjustments import compute_adjustment_factor
from app.ml.supply_analysis import compute_supply_metrics
from app.ml.time_adjustment import compute_monthly_drift, time_adjust_prices
from app.ml.winsorisation import winsorise_and_size_adjust
from app.models.price_model_result import PriceModelResult
from app.models.property import Property
from app.schemas.pricing import SubjectiveInputs


async def run_pricing_pipeline(
    prop: Property,
    all_ppr_sales: list[Any],
    active_count: int,
    subjective: SubjectiveInputs,
    buyer_aip: int | None = None,
    buyer_savings: int | None = None,
) -> PriceModelResult:
    if not prop.latitude or not prop.longitude:
        result = PriceModelResult(property_id=prop.id, status="error")
        return result

    today = date.today()

    # Step c: Comparable selection
    comps, radius_m, window_months = select_comparables(
        float(prop.latitude),
        float(prop.longitude),
        prop.eircode[:3] if prop.eircode else None,
        all_ppr_sales,
        today,
    )

    # Step d: Similarity scoring
    target_dict = {
        "bedrooms": prop.bedrooms,
        "property_type": prop.property_type,
        "carpet_area_sqm": prop.carpet_area_sqm,
        "latitude": float(prop.latitude),
        "longitude": float(prop.longitude),
    }
    scored = score_comparables(target_dict, comps, prop.eircode[:3] if prop.eircode else None)
    top_comps = [c for c, _ in scored[:20]]

    # Step e: Time adjustment
    monthly_drift = compute_monthly_drift([c for c in top_comps if c.floor_area_sqm], today)
    adjusted = time_adjust_prices(top_comps, monthly_drift, today)

    # Step f: Winsorisation + size-adjusted fair value
    winsorised, size_adj_value = winsorise_and_size_adjust(adjusted, prop.carpet_area_sqm)

    # Step g: Distribution
    dist = compute_distribution(winsorised)
    if not dist["p25"] or not dist["p50"] or not dist["p75"]:
        return PriceModelResult(property_id=prop.id, status="insufficient_data")

    # Step h+i: Confidence
    raw_conf = compute_raw_confidence(top_comps, radius_m, today)
    caf = compute_caf(raw_conf)

    # Step j: Supply
    supply = compute_supply_metrics(active_count, top_comps, today, window_months)

    # Step k: Seller leverage
    leverage = compute_seller_leverage(
        prop.days_on_market,
        prop.price or dist["p50"],
        dist["p50"],
        supply["months_supply"],
        is_buyer_chain_free=True,
    )

    # Step l: Sealed bid prob
    sealed_prob = compute_sealed_bid_probability(
        leverage, prop.price or dist["p50"], dist["p75"], supply["months_supply"]
    )

    # Our differentiator: subjective adjustments
    adj_factor, adj_breakdown = compute_adjustment_factor(
        renovation_standard=subjective.renovation_standard,
        aspect=subjective.aspect,
        layout_quality=subjective.layout_quality,
        ber_rating=prop.ber_rating,
        heating_type=prop.heating_type,
        is_celtic_tiger_era=prop.is_celtic_tiger_era,
        has_fire_cert=True,
    )

    # Apply subjective adjustment to distribution
    adj_p25 = round(dist["p25"] * adj_factor)
    adj_p50 = round(dist["p50"] * adj_factor)
    adj_p75 = round(dist["p75"] * adj_factor)
    adj_iqr = adj_p75 - adj_p25

    # Step m: Offer band
    raw_band = derive_offer_band(
        adj_p25, adj_p50, adj_p75, adj_iqr,
        prop.price or adj_p50,
        caf, sealed_prob,
    )

    # Step n: Final constraints
    final_band = apply_final_constraints(
        raw_band["entry"], raw_band["sealed"], raw_band["ceiling"],
        buyer_aip, buyer_savings,
        prop.price,
        sealed_prob,
    )

    # dhub PyMC skill call (for posterior uncertainty quantification)
    dhub_result = await _call_dhub_pymc(top_comps, target_dict, adj_factor)

    buyer_ceiling = None
    if buyer_aip and buyer_savings:
        closing_est = round((prop.price or adj_p50) * 0.01) + 3150
        buyer_ceiling = buyer_aip + buyer_savings - closing_est

    model_result = PriceModelResult(
        property_id=prop.id,
        status="ready",
        n_comparables=len(top_comps),
        geographic_radius_m=radius_m,
        temporal_window_months=window_months,
        comparables_used=[c.id for c in top_comps],
        size_adjusted_fair_value=round(size_adj_value * adj_factor) if size_adj_value else None,
        p25_estimate=adj_p25,
        p50_estimate=adj_p50,
        p75_estimate=adj_p75,
        iqr=adj_iqr,
        confidence_raw=raw_conf,
        caf=caf,
        confidence_final=round(raw_conf * caf, 3),
        active_supply_count=supply["active_supply_count"],
        months_supply=supply["months_supply"],
        seller_leverage_score=leverage,
        sealed_bid_probability=sealed_prob,
        over_asking_probability=_over_asking_prob(leverage, supply["months_supply"]),
        offer_entry=final_band["entry"],
        offer_sealed=final_band["sealed"],
        offer_ceiling=final_band["ceiling"],
        subjective_inputs={"inputs": subjective.model_dump(), "breakdown": adj_breakdown},
        subjective_adjustment_factor=adj_factor,
        buyer_ceiling=buyer_ceiling,
        model_params=dhub_result,
    )
    return model_result


async def _call_dhub_pymc(comps: list[Any], target: dict, adj_factor: float) -> dict:
    """Call Decision Hub PyMC skill for Bayesian posterior samples."""
    if not settings.dhub_api_key:
        return {"status": "skipped", "reason": "no dhub api key configured"}

    payload = {
        "comparables": [
            {
                "price_eur": c.price_eur,
                "floor_area_sqm": c.floor_area_sqm,
                "months_ago": 0,
            }
            for c in comps if c.floor_area_sqm
        ],
        "target": {
            "carpet_area_sqm": target.get("carpet_area_sqm"),
            "adjustment_factor": adj_factor,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.dhub_base_url}{settings.dhub_pymc_skill_path}",
                json=payload,
                headers={"Authorization": f"Bearer {settings.dhub_api_key}"},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    return {}


def _over_asking_prob(seller_leverage: float, months_supply: float) -> float:
    """Simple heuristic: high leverage + low supply = likely to sell above asking."""
    score = (seller_leverage / 10.0) * 0.6 + (max(0, 3 - months_supply) / 3.0) * 0.4
    return round(min(0.95, max(0.05, score)), 3)
