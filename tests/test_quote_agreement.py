import json

import pytest

from test_contract_behavior import _FakeRuntime, _Response, _now_ms, _quote_body, make_contract


def _quote(price):
    return _Response(_quote_body(price_x1e6=price))


@pytest.fixture(autouse=True)
def reset_runtime():
    _FakeRuntime._Web.response = _Response(_quote_body())
    _FakeRuntime.message.sender_address = _FakeRuntime.Address("creator")
    _FakeRuntime.eq_principle.prompt_comparative = staticmethod(
        lambda fn, principle="": fn()
    )


def _run_with_two_quotes(first_price, second_price):
    contract = make_contract()
    task_id = contract.create_task("ETH price", "1906.94", 100, "ETH/USDC")
    contract.submit_answer(task_id, "1906.94", "agent-movement")

    responses = iter([_quote(first_price), _quote(second_price)])
    _FakeRuntime._Web.response = next(responses)
    captured = {}

    def comparative(fn, principle=""):
        captured["principle"] = principle
        first = json.loads(fn())
        _FakeRuntime._Web.response = next(responses)
        second = json.loads(fn())
        first_price_value = float(first["price_x1e6"])
        second_price_value = float(second["price_x1e6"])
        movement_bps = abs(first_price_value - second_price_value) / min(
            first_price_value, second_price_value
        ) * 10000.0
        if movement_bps > 50:
            raise _FakeRuntime.vm.UserError("validator quote movement exceeds tolerance")
        return json.dumps(first)

    _FakeRuntime.eq_principle.prompt_comparative = staticmethod(comparative)
    return contract.evaluate(task_id), captured["principle"]


def test_validator_agreement_accepts_legitimate_quote_movement():
    verdict, principle = _run_with_two_quotes(1906940000, 1910000000)
    assert '"accepted": true' in verdict
    assert "50 bps" in principle
    assert "pair" in principle
    assert "source" in principle
    assert "reference" in principle
    assert "Timestamp and age" in principle
    assert "freshness" in principle
    assert "CoinCap" in principle


def test_validator_agreement_rejects_excessive_quote_movement():
    with pytest.raises(_FakeRuntime.vm.UserError, match="exceeds tolerance"):
        _run_with_two_quotes(1906940000, 2020000000)


def _run_with_tampered_consensus(snapshot_mutator):
    """Simulate a consensus result whose timing fields were forged after the
    per-validator freshness checks already passed."""
    contract = make_contract()
    task_id = contract.create_task("ETH price", "1906.94", 100, "ETH/USDC")
    contract.submit_answer(task_id, "1906.94", "agent-consensus")

    def comparative(fn, principle=""):
        snapshot = json.loads(fn())
        snapshot_mutator(snapshot)
        return json.dumps(snapshot)

    _FakeRuntime.eq_principle.prompt_comparative = staticmethod(comparative)
    return contract.evaluate(task_id)


def _stale_timestamp():
    return _now_ms() - 300_000


def test_consensus_with_stale_timestamp_is_rejected():
    with pytest.raises(_FakeRuntime.vm.UserError, match="stale quote"):
        _run_with_tampered_consensus(
            lambda snapshot: snapshot.update(timestamp_ms=_stale_timestamp())
        )


def test_consensus_with_future_timestamp_is_rejected():
    with pytest.raises(_FakeRuntime.vm.UserError, match="invalid quote timestamp"):
        _run_with_tampered_consensus(
            lambda snapshot: snapshot.update(timestamp_ms=_now_ms() + 60_000)
        )


def test_consensus_with_fresh_true_but_stale_timestamp_is_rejected():
    def forger(snapshot):
        snapshot["timestamp_ms"] = _stale_timestamp()
        snapshot["fresh"] = True

    with pytest.raises(_FakeRuntime.vm.UserError, match="stale quote"):
        _run_with_tampered_consensus(forger)


def test_consensus_with_fabricated_zero_age_but_stale_timestamp_is_rejected():
    def forger(snapshot):
        snapshot["timestamp_ms"] = _stale_timestamp()
        snapshot["age_ms"] = 0
        snapshot["fresh"] = True

    with pytest.raises(_FakeRuntime.vm.UserError, match="stale quote"):
        _run_with_tampered_consensus(forger)
