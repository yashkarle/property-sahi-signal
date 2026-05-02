import json
from unittest.mock import MagicMock
from app.services.bidding_service import _rule_based_strategy


def _mock_model(p25=386_000, sealed_prob=0.75, leverage=4.0,
                supply=2.4, active_count=4):
    m = MagicMock()
    m.p25_estimate = p25
    m.sealed_bid_probability = sealed_prob
    m.seller_leverage_score = leverage
    m.months_supply = supply
    m.active_supply_count = active_count
    return m


def _mock_prop(price=365_000):
    p = MagicMock()
    p.price = price
    p.address = "16 Beechdale Court, Dublin 24"
    return p


def test_strategy_returns_valid_json() -> None:
    result = _rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model())
    data = json.loads(result)
    assert all(k in data for k in ("opening", "escalation", "best_and_final", "walk_away"))


def test_opening_bid_is_above_asking() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(365_000), 401_000, 370_000, 50_000, _mock_model()))
    assert result["opening"]["amount"] > 365_000


def test_best_and_final_equals_buyer_ceiling() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model()))
    assert result["best_and_final"]["amount"] == 401_000


def test_walk_away_ceiling_equals_buyer_ceiling() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model()))
    assert result["walk_away"]["ceiling"] == 401_000


def test_escalation_increment_is_2500() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model()))
    assert result["escalation"]["increment"] == 2500


def test_max_before_final_is_below_ceiling() -> None:
    result = json.loads(_rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, _mock_model()))
    assert result["escalation"]["max_before_final"] < result["best_and_final"]["amount"]


def test_strategy_works_without_price_model() -> None:
    result = _rule_based_strategy(_mock_prop(), 401_000, 370_000, 50_000, None)
    data = json.loads(result)
    assert data["best_and_final"]["amount"] == 401_000


def test_strategy_works_without_aip_savings() -> None:
    result = _rule_based_strategy(_mock_prop(), 401_000, None, None, None)
    data = json.loads(result)
    assert data["best_and_final"]["amount"] == 401_000
