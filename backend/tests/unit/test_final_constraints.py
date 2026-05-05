from app.ml.final_constraints import apply_final_constraints


def test_closing_costs_formula_uses_4500_fixed() -> None:
    """Closing costs = stamp duty 1% + €4,500 (solicitor €2.5k + land reg €1k + survey/val €1k)."""
    result = apply_final_constraints(
        entry=350_000,
        sealed=360_000,
        ceiling=500_000,
        buyer_aip=370_000,
        buyer_savings=50_000,
        asking_price=400_000,
    )
    # buyer_ceiling = 370k + 50k - (round(400k * 0.01) + 4500) = 420k - 8500 = 411500
    # floored to nearest 2500 (never round UP — would exceed funded max) = 410000
    assert result["ceiling"] == 410_000


def test_closing_costs_old_formula_is_not_used() -> None:
    """Old formula was round(price*0.01) + 3150. New adds €4,500."""
    result = apply_final_constraints(
        entry=300_000,
        sealed=320_000,
        ceiling=600_000,
        buyer_aip=300_000,
        buyer_savings=40_000,
        asking_price=300_000,
    )
    # stamp = 3000, fixed = 4500, closing = 7500
    # buyer_ceiling = 300k + 40k - 7500 = 332500 → round to 2500 = 332500
    assert result["ceiling"] == 332_500


def test_no_buyer_ceiling_when_savings_missing() -> None:
    """buyer_ceiling is not applied when either aip or savings is None."""
    result = apply_final_constraints(
        entry=300_000,
        sealed=320_000,
        ceiling=400_000,
        buyer_aip=300_000,
        buyer_savings=None,
    )
    assert result["ceiling"] == 400_000


def test_ceiling_is_capped_by_buyer_ceiling() -> None:
    """Market ceiling above buyer ceiling gets capped."""
    result = apply_final_constraints(
        entry=350_000,
        sealed=370_000,
        ceiling=665_000,
        buyer_aip=370_000,
        buyer_savings=50_000,
        asking_price=365_000,
    )
    # stamp = 3650, fixed = 4500, closing = 8150
    # buyer_ceiling = 370k + 50k - 8150 = 411850 → floored to 2500 = 410000
    assert result["ceiling"] == 410_000
    assert result["ceiling"] < 665_000


def test_entry_and_sealed_respect_ordering() -> None:
    """entry ≤ sealed ≤ ceiling always holds."""
    result = apply_final_constraints(
        entry=400_000,
        sealed=380_000,
        ceiling=350_000,
        buyer_aip=300_000,
        buyer_savings=50_000,
        asking_price=300_000,
    )
    assert result["entry"] <= result["sealed"] <= result["ceiling"]
