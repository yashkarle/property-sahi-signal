from app.core.bedrock import invoke_claude
from app.models.bid import BidSession
from app.models.property import Property

SYSTEM_PROMPT = """You are a Dublin property bidding strategist.
The buyer is mortgage-approved, chain-free, and can close in 6-8 weeks.
This is their strongest negotiating advantage. Be direct and tactical."""


def generate_strategy(prop: Property, user_max_budget: int) -> str:
    prompt = f"""Advise on bidding strategy for this Dublin property:

Property: {prop.address or prop.title}
Asking price: €{prop.price:,}
User's maximum budget: €{user_max_budget:,}
Days on market: {prop.days_on_market or 'unknown'}
Chain-free seller: {prop.is_chain_free}
Seller status: {prop.seller_status}
Heating type: {prop.heating_type}
Year built: {prop.year_built}

Provide:
1. Opening bid recommendation (with rationale)
2. Escalation strategy if outbid (step increments)
3. Walk-away conditions
4. Key leverage points to communicate to the estate agent
5. Red flags to watch for during the process

Be specific with €amounts rounded to nearest €2,500."""

    return invoke_claude(prompt, system=SYSTEM_PROMPT)


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
