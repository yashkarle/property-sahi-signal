from app.core.bedrock import invoke_claude
from app.models.property import Property

SYSTEM_PROMPT = """You are a property analysis expert for Dublin, Ireland.
Compare properties objectively. Flag critical issues (electric storage heating, Celtic Tiger era,
missing floor area, high management fees). The buyer needs ≥70sqm carpet area, 2+ bed/2+ bath."""


def generate_comparison(properties: list[Property]) -> dict:
    prop_summaries = []
    for p in properties:
        summary = f"""
Property: {p.address or p.title}
Price: {f'€{p.price:,}' if p.price else 'unknown'} | Size: {p.carpet_area_sqm or 'unknown'}sqm | {p.bedrooms}bed/{p.bathrooms}bath
Type: {p.property_type} | BER: {p.ber_rating or 'unknown'} | Heating: {p.heating_type}
Management fee: {f'€{p.management_fee_eur:,}/yr' if p.management_fee_eur else 'N/A'} | Chain-free: {p.is_chain_free}
Days on market: {p.days_on_market} | Year built: {p.year_built or 'unknown'}
"""
        prop_summaries.append(summary)

    prompt = f"""Compare these {len(properties)} Dublin properties for a mortgage-approved buyer:

{'---'.join(prop_summaries)}

Provide:
1. A 3-sentence executive summary with a clear recommendation
2. A comparison table covering: value for money, space efficiency (€/sqm), commute potential, risk flags, overall score /10

Format the table as: Property | Metric | Score/Value"""

    narrative = invoke_claude(prompt, system=SYSTEM_PROMPT)

    comparison_table: dict = {}
    for p in properties:
        comparison_table[str(p.id)] = {
            "price": p.price,
            "carpet_area_sqm": p.carpet_area_sqm,
            "price_per_sqm": p.price_per_sqm,
            "ber_rating": p.ber_rating,
            "heating_type": p.heating_type,
            "is_chain_free": p.is_chain_free,
            "days_on_market": p.days_on_market,
            "management_fee_eur": p.management_fee_eur,
            "is_celtic_tiger_era": p.is_celtic_tiger_era,
        }

    return {"summary": narrative, "comparison_table": comparison_table}
