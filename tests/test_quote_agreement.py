import json

import pytest

from test_contract_behavior import _FakeRuntime, _Response, _DEFAULT_RESPONSE, load_contract


def _quote(price):
    return _Response(json.dumps({
        "pair": "ETH/USDC",
        "price_x1e6": price,
        "source": "binance-spot",
        "timestamp_ms": 1723900000000,
        "age_ms": 1000,
        "fresh": True,
    }))


@pytest.fixture(autouse=True)
def reset_runtime():
    _FakeRuntime._Web.response = _Response(_DEFAULT_RESPONSE)
    _FakeRuntime.message.sender_address = _FakeRuntime.Address("creator")
    _FakeRuntime.eq_principle.prompt_comparative = staticmethod(
        lambda fn, principle="": fn()
    )


def _run_with_two_quotes(first_price, second_price):
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")
    task_id = contract.create_task("ETH price", "1906.94", 100)
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
    return contract.evaluate(task_id, "ETH/USDC"), captured["principle"]


def test_validator_agreement_accepts_legitimate_quote_movement():
    verdict, principle = _run_with_two_quotes(1906940000, 1910000000)
    assert '"accepted": true' in verdict
    assert "50 basis points" in principle
    assert "pair" in principle
    assert "source" in principle
    assert "timestamp_ms" in principle
    assert "age_ms" in principle


def test_validator_agreement_rejects_excessive_quote_movement():
    with pytest.raises(_FakeRuntime.vm.UserError, match="exceeds tolerance"):
        _run_with_two_quotes(1906940000, 2020000000)
