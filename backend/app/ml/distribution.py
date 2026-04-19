"""Step g: P25/P50/P75/IQR distribution parameters."""
import numpy as np

from app.ml.comparables import ComparableRecord


def compute_distribution(
    winsorised_comps: list[tuple[ComparableRecord, int]],
) -> dict[str, int | None]:
    """Returns {p25, p50, p75, iqr} in EUR."""
    if not winsorised_comps:
        return {"p25": None, "p50": None, "p75": None, "iqr": None}

    prices = np.array([p for _, p in winsorised_comps], dtype=float)
    p25 = int(np.percentile(prices, 25))
    p50 = int(np.percentile(prices, 50))
    p75 = int(np.percentile(prices, 75))
    iqr = p75 - p25
    return {"p25": p25, "p50": p50, "p75": p75, "iqr": iqr}
