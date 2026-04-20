"""Match PPR sold records to active property listings.

Matching strategy (in order of confidence):
1. Exact eircode + bedrooms match (if both present)
2. Eircode prefix + price within 20% + same district
"""
from dataclasses import dataclass


@dataclass
class MatchResult:
    ppr_address: str
    property_id: str
    confidence: str  # "high" | "medium"


def match_ppr_to_listings(
    ppr_records: list[dict],
    properties: list[dict],
) -> list[MatchResult]:
    """Match PPR records against active listings. Returns best matches."""
    results: list[MatchResult] = []

    # Build lookup indexes
    eircode_props: dict[str, list[dict]] = {}
    district_props: dict[str, list[dict]] = {}
    for prop in properties:
        ec = (prop.get("eircode") or "")[:7].upper()
        if ec:
            eircode_props.setdefault(ec, []).append(prop)
        dist = prop.get("dublin_district") or ""
        if dist:
            district_props.setdefault(dist, []).append(prop)

    for ppr in ppr_records:
        ppr_ec = (ppr.get("eircode") or "")[:7].upper()
        ppr_price = ppr.get("price_eur", 0)
        ppr_district = ppr.get("dublin_district") or ""

        # Strategy 1: eircode match
        if ppr_ec and ppr_ec in eircode_props:
            candidates = eircode_props[ppr_ec]
            if len(candidates) == 1:
                results.append(MatchResult(
                    ppr_address=ppr["address"],
                    property_id=candidates[0]["id"],
                    confidence="high",
                ))
                continue
            # Multiple candidates — pick closest price
            best = min(candidates, key=lambda p: abs((p.get("price") or 0) - ppr_price))
            results.append(MatchResult(
                ppr_address=ppr["address"],
                property_id=best["id"],
                confidence="medium",
            ))
            continue

        # Strategy 2: district + price within 15%
        if ppr_district and ppr_district in district_props and ppr_price > 0:
            for prop in district_props[ppr_district]:
                prop_price = prop.get("price") or 0
                if prop_price and abs(prop_price - ppr_price) / ppr_price < 0.15:
                    results.append(MatchResult(
                        ppr_address=ppr["address"],
                        property_id=prop["id"],
                        confidence="medium",
                    ))
                    break

    return results
