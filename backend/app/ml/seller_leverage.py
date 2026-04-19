"""Step k: Seller leverage score (0-10). Higher = seller has more power."""


def compute_seller_leverage(
    days_on_market: int | None,
    asking_price: int,
    p50_estimate: int | None,
    months_supply: float,
    price_reductions: int = 0,
    is_buyer_chain_free: bool = True,
) -> float:
    """
    Inputs:
    - days_on_market: longer = lower seller leverage
    - asking_price vs p50: overpriced = lower leverage
    - months_supply: <3 = seller's market (high leverage), >6 = buyer's market
    - price_reductions: each reduction = seller losing leverage
    - is_buyer_chain_free: buyer being chain-free reduces seller leverage they can extract
    Returns score 0-10 (10 = seller has all leverage).
    """
    score = 5.0  # neutral starting point

    # Days on market: >90 days = seller losing leverage
    dom = days_on_market or 30
    if dom < 14:
        score += 2.0
    elif dom < 30:
        score += 1.0
    elif dom < 60:
        score += 0.0
    elif dom < 90:
        score -= 1.0
    else:
        score -= 2.5

    # Price reductions: each reduction = -0.75 leverage
    score -= price_reductions * 0.75

    # Months supply: <3 = seller's market
    if months_supply < 2:
        score += 2.0
    elif months_supply < 3:
        score += 1.0
    elif months_supply < 5:
        score += 0.0
    elif months_supply < 8:
        score -= 1.0
    else:
        score -= 2.0

    # Asking vs P50
    if p50_estimate:
        ratio = asking_price / p50_estimate
        if ratio < 0.95:
            score -= 1.5  # underpriced = high competition = seller leverage
        elif ratio < 1.0:
            score += 0.0
        elif ratio < 1.05:
            score -= 0.5  # slightly overpriced
        else:
            score -= 1.5  # overpriced = reduced leverage

    # Buyer chain-free advantage: slightly reduces leverage differential
    if is_buyer_chain_free:
        score -= 0.5

    return round(max(0.0, min(10.0, score)), 1)
