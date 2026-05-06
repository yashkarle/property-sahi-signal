import uuid
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import AuthDep, DbSession
from app.models.ppr_sales import PPRSale
from app.models.price_model_result import PriceModelResult
from app.models.property import Property
from app.schemas.pricing import ComparableOut, PriceModelResultOut, PricingAnalyseRequest
from app.services.pricing_model_service import run_pricing_pipeline

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.post("/analyse", response_model=PriceModelResultOut)
async def analyse_property(
    request: PricingAnalyseRequest, db: DbSession, _: AuthDep
) -> PriceModelResultOut:
    result = await db.execute(select(Property).where(Property.id == request.property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not prop.latitude or not prop.longitude:
        raise HTTPException(status_code=422, detail="Property missing geocoordinates")

    ppr_result = await db.execute(
        select(PPRSale).where(
            PPRSale.date_of_sale >= date.today() - timedelta(days=730),
            PPRSale.latitude.is_not(None),
        )
    )
    ppr_sales = ppr_result.scalars().all()

    active_result = await db.execute(
        select(Property).where(
            Property.is_active == True,  # noqa: E712
            Property.dublin_district == prop.dublin_district,
        )
    )
    active_count = len(active_result.scalars().all())

    model_result = await run_pricing_pipeline(
        prop,
        ppr_sales,
        active_count,
        request.subjective_inputs,
        request.buyer_aip,
        request.buyer_savings,
    )
    db.add(model_result)
    await db.commit()
    await db.refresh(model_result)
    return PriceModelResultOut.model_validate(model_result)


@router.get("/{property_id}/comparables", response_model=list[ComparableOut])
async def get_comparables(property_id: uuid.UUID, db: DbSession, _: AuthDep) -> list[ComparableOut]:
    from app.ml.comparables import ComparableRecord, haversine_m
    from app.ml.time_adjustment import compute_monthly_drift, time_adjust_prices

    prop_result = await db.execute(select(Property).where(Property.id == property_id))
    prop = prop_result.scalar_one_or_none()
    if not prop or not prop.latitude or not prop.longitude:
        raise HTTPException(status_code=404, detail="Property not found or missing geocoordinates")

    # Query all geocoded PPR sales in the last 24 months then filter to 2 km in Python
    # (haversine in pure SQL is verbose; the result set is small enough to filter in-process)
    cutoff = date.today() - timedelta(days=730)
    ppr_result = await db.execute(
        select(PPRSale).where(PPRSale.date_of_sale >= cutoff, PPRSale.latitude.is_not(None))
    )
    all_sales = ppr_result.scalars().all()

    prop_lat = float(prop.latitude)
    prop_lon = float(prop.longitude)
    within = []
    for sale in all_sales:
        dist = haversine_m(prop_lat, prop_lon, float(sale.latitude), float(sale.longitude))
        if dist <= 2000:
            within.append((sale, dist))

    within.sort(key=lambda x: x[1])
    selected = within[:30]

    if not selected:
        raise HTTPException(
            status_code=404, detail="No comparable sales found within 2 km in the last 24 months."
        )

    comp_records = [
        ComparableRecord(
            id=str(c.id),
            address=c.address,
            date_of_sale=c.date_of_sale,
            price_eur=c.price_eur,
            floor_area_sqm=c.floor_area_sqm,
            price_per_sqm=float(c.price_per_sqm) if c.price_per_sqm else None,
            bedrooms=c.bedrooms,
            property_type=c.property_type,
            latitude=float(c.latitude),
            longitude=float(c.longitude),
        )
        for c, _ in selected
    ]
    monthly_drift = compute_monthly_drift(comp_records, date.today())
    adjusted_pairs = time_adjust_prices(comp_records, monthly_drift, date.today())
    adjusted_by_id = {pair[0].id: pair[1] for pair in adjusted_pairs}

    return sorted(
        [
            ComparableOut(
                address=c.address,
                date_of_sale=c.date_of_sale,
                price_eur=c.price_eur,
                time_adjusted_price=adjusted_by_id.get(str(c.id)),
                floor_area_sqm=c.floor_area_sqm,
                price_per_sqm=float(c.price_per_sqm) if c.price_per_sqm else None,
                bedrooms=c.bedrooms,
                property_type=c.property_type,
                distance_m=round(dist),
                months_ago=round((date.today() - c.date_of_sale).days / 30.44, 1),
                latitude=float(c.latitude),
                longitude=float(c.longitude),
            )
            for c, dist in selected
        ],
        key=lambda x: x.distance_m,
    )


@router.get("/{property_id}/offer-band")
async def get_offer_band(property_id: uuid.UUID, db: DbSession, _: AuthDep) -> dict:
    result = await db.execute(
        select(PriceModelResult)
        .where(PriceModelResult.property_id == property_id, PriceModelResult.status == "ready")
        .order_by(PriceModelResult.run_at.desc())
        .limit(1)
    )
    latest = result.scalars().first()
    if not latest:
        raise HTTPException(status_code=404, detail="Run /pricing/analyse first")

    prop_result = await db.execute(select(Property).where(Property.id == property_id))
    prop = prop_result.scalar_one_or_none()

    return {
        "entry": latest.offer_entry,
        "sealed": latest.offer_sealed,
        "ceiling": latest.offer_ceiling,
        "seller_leverage_score": latest.seller_leverage_score,
        "sealed_bid_probability": latest.sealed_bid_probability,
        "over_asking_probability": latest.over_asking_probability,
        "confidence_final": latest.confidence_final,
        "p25": latest.p25_estimate,
        "p50": latest.p50_estimate,
        "p75": latest.p75_estimate,
        "property_lat": float(prop.latitude) if prop and prop.latitude else None,
        "property_lng": float(prop.longitude) if prop and prop.longitude else None,
    }
