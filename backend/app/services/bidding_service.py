"""Bidding strategy generation — Bedrock primary, rule-based fallback."""
from __future__ import annotations

import json

from app.core.bedrock import invoke_claude
from app.models.bid import BidSession
from app.models.property import Property

SYSTEM_PROMPT = """You are a Dublin property bidding strategist.
The buyer is mortgage-approved, chain-free, and can close in 6-8 weeks.
This is their strongest negotiating advantage. Be direct and tactical."""


def generate_strategy(
    prop: Property,
    user_max_budget: int,
    user_aip: int | None = None,
    user_savings: int | None = None,
    price_model=None,
    is_first_time_buyer: bool = True,
) -> str | None:
    """Generate bidding strategy. Uses Bedrock when available; falls back to rule-based."""
    try:
        prompt = f"""Advise on bidding strategy for this Dublin property:

Property: {prop.address or prop.title}
Asking price: €{prop.price:,}
User's maximum budget: €{user_max_budget:,}
Days on market: {prop.days_on_market or 'unknown'}
Chain-free seller: {prop.is_chain_free}
Seller status: {prop.seller_status}
Heating type: {prop.heating_type}
Year built: {prop.year_built}

Return a JSON object with keys: opening, escalation, best_and_final, walk_away.
Each has: amount (int), rationale (str). escalation also has: increment (int), max_before_final (int).
walk_away has: ceiling (int), rationale (str).
Be specific with €amounts rounded to nearest €2,500."""
        return invoke_claude(prompt, system=SYSTEM_PROMPT)
    except Exception:
        return _rule_based_strategy(prop, user_max_budget, user_aip, user_savings, price_model, is_first_time_buyer)


def _rule_based_strategy(
    prop: Property,
    user_max_budget: int,
    user_aip: int | None,
    user_savings: int | None,
    price_model,
    is_first_time_buyer: bool = True,
) -> str:
    """Derive a 4-step bidding strategy from the pricing model data without AI."""
    asking = prop.price or 0

    # Buyer ceiling — Central Bank LTV: FTB can borrow 90% (10% min deposit),
    # non-FTB capped at 80% (20% min deposit).
    ltv = 0.9 if is_first_time_buyer else 0.8
    ltv_label = "90% LTV (FTB)" if is_first_time_buyer else "80% LTV (non-FTB)"
    if user_aip and user_savings:
        ltv_ceiling = int(user_aip / ltv)
        closing = round(ltv_ceiling * 0.01) + 4500
        affordability = user_aip + user_savings - closing
        buyer_ceiling = (min(ltv_ceiling, affordability, user_max_budget) // 2500) * 2500
    else:
        buyer_ceiling = user_max_budget

    # Extract model stats
    p25 = int(price_model.p25_estimate) if price_model and price_model.p25_estimate else None
    sealed_prob = float(price_model.sealed_bid_probability) if price_model else 0.5
    leverage = float(price_model.seller_leverage_score) if price_model else 3.0
    supply = float(price_model.months_supply) if price_model else 6.0
    active = int(price_model.active_supply_count) if price_model and price_model.active_supply_count else None

    # Opening bid: above asking, at least at P25 floor if available
    floor = int(p25 * 0.98) if p25 else asking
    opening = max(asking + 2500, floor)
    opening = round(opening / 2500) * 2500

    # Escalation cap: leave €7,500 gap before ceiling for best & final
    max_before_final = min(buyer_ceiling - 7500, opening + 5 * 2500)
    max_before_final = round(max_before_final / 2500) * 2500

    sealed_desc = "very likely" if sealed_prob > 0.7 else "likely" if sealed_prob > 0.4 else "unlikely"
    market_desc = "strong seller's market" if leverage > 3.5 else "balanced market" if leverage > 2.5 else "buyer-friendly market"
    supply_note = f"Only {active} active listings in this area." if active else ""

    walk_note = f"P25 comparable sales start at €{p25 // 1000}k — similar properties will appear." if p25 else "Comparable properties will appear."

    strategy = {
        "opening": {
            "amount": int(opening),
            "rationale": (
                f"Bid €{opening:,} — above asking (€{asking:,}), shows intent without revealing ceiling. "
                f"Ask the agent immediately: are there other bidders? Any cash buyers in the pool?"
            ),
        },
        "escalation": {
            "increment": 2500,
            "max_before_final": int(max_before_final),
            "rationale": (
                f"Move in €2,500 steps up to €{max_before_final:,}. Do not volunteer increases — wait for the agent "
                f"to call back. Sealed bid is {sealed_desc} ({int(sealed_prob * 100)}%) in this "
                f"{market_desc} ({supply:.1f} months supply). {supply_note}"
            ),
        },
        "best_and_final": {
            "amount": int(buyer_ceiling),
            "rationale": (
                f"Put in €{buyer_ceiling:,} as your sealed bid — your Central Bank {ltv_label} ceiling. "
                f"Accompany with a bid letter: chain-free, AIP in hand, solicitor instructed, 6–8 week close. "
                f"Speed-to-close often beats a marginally higher uncertain bid."
            ),
        },
        "walk_away": {
            "ceiling": int(buyer_ceiling),
            "rationale": (
                f"Above €{buyer_ceiling:,} you exceed your mortgage limit ({ltv_label}). Walk away with confidence. "
                f"{walk_note}"
            ),
        },
    }
    return json.dumps(strategy)


def generate_bid_letter(
    prop: Property,
    user_bid: int,
    competing_bid: int | None,
    context: str,
) -> str:
    competing_text = f"There is a competing bid of €{competing_bid:,}." if competing_bid else ""
    prompt = f"""Write a persuasive letter to an Irish estate agent presenting a buyer's bid.

Property: {prop.address or prop.title}
User's bid: €{user_bid:,}
{competing_text}
{f'Context: {context}' if context else ''}

The buyer's key advantages:
- Fully mortgage-approved with AIP in hand
- No onward chain — no property to sell
- Title deeds ready with solicitor
- Can guarantee closing in 6-8 weeks
- First-time buyer (if applicable)

Note: Estate agents in Ireland are legally obligated to present ALL bids to the vendor.
Make clear this bid comes with certainty the competing bid may lack.

Write a professional 3-paragraph letter. Address it to "The Selling Agent"."""

    return invoke_claude(prompt, system=SYSTEM_PROMPT)
