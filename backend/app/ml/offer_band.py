"""Step m: Derive Entry / Sealed / Ceiling offer band."""


def derive_offer_band(
    p25: int,
    p50: int,
    p75: int,
    iqr: int,
    asking_price: int,
    caf: float,
    sealed_bid_probability: float,
) -> dict[str, int]:
    """
    Entry = max(P25, asking_price * 0.95)  — opening bid
    Sealed = P50 * CAF                     — full target
    Ceiling = P75 + (IQR * 0.25)          — absolute max before overpaying

    If sealed_bid_probability > 50%: Entry must be ≥ P50 (don't underbid in a hot market).
    """
    entry = max(p25, round(asking_price * 0.95))
    sealed = round(p50 * caf)
    ceiling = round(p75 + iqr * 0.25)

    # In a hot sealed bid market, don't open below P50
    if sealed_bid_probability > 0.5:
        entry = max(entry, p50)

    return {"entry": entry, "sealed": sealed, "ceiling": ceiling}
