"""Step l: Sealed bid probability (0-75%)."""
import math


def compute_sealed_bid_probability(
    seller_leverage: float,
    asking_price: int,
    p75_estimate: int | None,
    months_supply: float,
) -> float:
    """
    Logistic function based on:
    - seller_leverage (0-10): high = more likely sealed bid
    - asking vs p75: if asking < p75, competition high = sealed bid likely
    - months_supply: < 3 months = seller's market = sealed bid common
    Returns probability capped at 0-75%.
    """
    score = 0.0

    # Seller leverage contribution (0-10 → 0-5 raw score)
    score += (seller_leverage / 10.0) * 5.0

    # Price relative to P75
    if p75_estimate:
        ratio = asking_price / p75_estimate
        if ratio < 0.9:
            score += 3.0  # heavily underpriced — very likely sealed bid
        elif ratio < 1.0:
            score += 1.5
        else:
            score -= 1.0  # overpriced — less likely

    # Months supply
    if months_supply < 2:
        score += 2.0
    elif months_supply < 3:
        score += 1.0
    elif months_supply > 6:
        score -= 1.5

    # Logistic transform to [0, 1]
    prob = 1 / (1 + math.exp(-score + 3))  # centred so score~3 = 50%
    return round(min(0.75, max(0.0, prob)), 3)
