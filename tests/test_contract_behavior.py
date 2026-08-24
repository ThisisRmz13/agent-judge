import importlib.util
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest


CONTRACT = Path(__file__).parents[1] / "contracts" / "agent_judge.py"


class _TreeMap(dict):
    pass


class _Address(str):
    pass


class _Response:
    def __init__(self, body):
        self.body = body.encode("utf-8")


_DEFAULT_RESPONSE = (
    '{"pair":"ETH/USDC","price_x1e6":1906940000,'
    '"source":"binance-spot","timestamp_ms":1723900000000,'
    '"age_ms":1000,"fresh":true,"reference":"1906.94"}'
)


class _FakeRuntime:
    class Contract:
        pass

    TreeMap = _TreeMap
    Address = _Address
    u8 = staticmethod(int)
    u32 = staticmethod(int)
    u64 = staticmethod(int)

    class _Public:
        class _Write:
            def __call__(self, fn):
                return fn

        class _View:
            def __call__(self, fn):
                return fn

        write = _Write()
        view = _View()

    public = _Public()

    class _Message:
        sender_address = _Address("creator")

    message = _Message()

    class _VM:
        class UserError(Exception):
            pass

    vm = _VM()

    class _Web:
        response = _Response(_DEFAULT_RESPONSE)
        captured_url = ""
        raises = None

        @staticmethod
        def request(url, method="GET"):
            _FakeRuntime._Web.captured_url = url
            if _FakeRuntime._Web.raises is not None:
                raise _FakeRuntime._Web.raises
            return _FakeRuntime._Web.response

    class _Nondet:
        pass

    nondet = _Nondet()

    class _EqPrinciple:
        @staticmethod
        def prompt_comparative(fn, principle=""):
            return fn()

    eq_principle = _EqPrinciple()


_FakeRuntime._Nondet.web = _FakeRuntime._Web()


@pytest.fixture(autouse=True)
def reset_fake_runtime_state():
    _FakeRuntime._Web.response = _Response(_DEFAULT_RESPONSE)
    _FakeRuntime._Web.captured_url = ""
    _FakeRuntime._Web.raises = None
    _FakeRuntime.message.sender_address = _Address("creator")


def load_contract():
    fake = types.ModuleType("genlayer")
    fake.gl = _FakeRuntime
    fake.TreeMap = _TreeMap
    fake.Address = _Address
    fake.u8 = int
    fake.u32 = int
    fake.u64 = int
    sys.modules["genlayer"] = fake

    spec = importlib.util.spec_from_file_location("agent_judge_under_test", CONTRACT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AgentJudge


def make_contract():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")
    contract.task_data = _TreeMap()
    contract.task_status = _TreeMap()
    contract.task_creator = _TreeMap()
    contract.task_agent = _TreeMap()
    contract.task_answer = _TreeMap()
    contract.task_verdict = _TreeMap()
    contract.reputation = _TreeMap()
    contract.reputation_credited = _TreeMap()
    contract.dispute_count = _TreeMap()
    return contract


def create_eth_task(contract, prompt="ETH price", reference="1906.94", tolerance=100):
    return contract.create_task(prompt, reference, tolerance, "ETH/USDC")


def test_scenario_accepted_answer_credits_reputation():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-a")
    verdict = contract.evaluate(task_id)
    assert '"accepted": true' in verdict
    assert contract.get_reputation("agent-a") == 1


def test_scenario_wrong_answer_does_not_credit_reputation():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "2500", "agent-b")
    verdict = contract.evaluate(task_id)
    assert '"accepted": false' in verdict
    assert contract.get_reputation("agent-b") == 0


def test_scenario_task_pair_is_bound_and_cannot_be_overridden():
    contract = make_contract()
    task_id = contract.create_task("BTC price", "60000", 100, "BTC/USDC")
    contract.submit_answer(task_id, "60000", "agent-bind")
    with pytest.raises(_FakeRuntime.vm.UserError, match="different trading pair"):
        contract._quote_snapshot("ETH/USDC", "60000")
    assert '"pair": "BTCUSDC"' in contract.get_task(task_id)
    verdict = contract.evaluate(task_id)
    assert '"pair": "BTCUSDC"' in verdict


def test_scenario_dispute_requires_creator_and_is_one_shot():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-c")
    contract.evaluate(task_id)

    _FakeRuntime.message.sender_address = _Address("attacker")
    with pytest.raises(_FakeRuntime.vm.UserError, match="only the task creator can dispute"):
        contract.dispute(task_id)

    _FakeRuntime.message.sender_address = _Address("creator")
    contract.dispute(task_id)
    with pytest.raises(_FakeRuntime.vm.UserError, match="task has already been disputed"):
        contract.dispute(task_id)


def test_scenario_verdict_reversal_removes_prior_reputation_credit():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-d")
    contract.evaluate(task_id)
    assert contract.get_reputation("agent-d") == 1

    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":2200000000,'
        '"source":"binance-spot","timestamp_ms":1723900000000,'
        '"age_ms":1000,"fresh":true,"reference":"1906.94"}'
    )
    contract.dispute(task_id)
    assert contract.get_reputation("agent-d") == 0
    assert '"accepted": false' in contract.get_task(task_id)


def test_scenario_live_source_failure_is_rejected():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-e")
    _FakeRuntime._Web.response = _Response('{"error":"live quote request failed"}')
    with pytest.raises(_FakeRuntime.vm.UserError, match="missing required fields"):
        contract.evaluate(task_id)


def test_scenario_actual_http_failure_is_rejected():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-http")
    _FakeRuntime._Web.raises = TimeoutError("network timeout")
    with pytest.raises(_FakeRuntime.vm.UserError, match="live quote request failed"):
        contract.evaluate(task_id)


def test_scenario_requested_pair_must_match_returned_pair():
    contract = make_contract()
    task_id = contract.create_task("BTC price", "60000", 100, "BTC/USDC")
    contract.submit_answer(task_id, "60000", "agent-f")
    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":1906940000,'
        '"source":"binance-spot","timestamp_ms":1723900000000,'
        '"age_ms":1000,"fresh":true,"reference":"60000"}'
    )
    with pytest.raises(_FakeRuntime.vm.UserError, match="different trading pair"):
        contract.evaluate(task_id)


def test_scenario_source_mismatch_is_rejected():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-source")
    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":1906940000,'
        '"source":"mock","timestamp_ms":1723900000000,'
        '"age_ms":1000,"fresh":true,"reference":"1906.94"}'
    )
    with pytest.raises(_FakeRuntime.vm.UserError, match="approved live source"):
        contract.evaluate(task_id)


def test_scenario_stale_quote_is_rejected():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-g")
    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":1906940000,'
        '"source":"binance-spot","timestamp_ms":1723900000000,'
        '"age_ms":60001,"fresh":false,"reference":"1906.94"}'
    )
    with pytest.raises(_FakeRuntime.vm.UserError, match="stale quote"):
        contract.evaluate(task_id)


def test_scenario_fresh_true_but_stale_age_is_rejected():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-fresh")
    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":1906940000,'
        '"source":"binance-spot","timestamp_ms":1723900000000,'
        '"age_ms":60001,"fresh":true,"reference":"1906.94"}'
    )
    with pytest.raises(_FakeRuntime.vm.UserError, match="stale quote"):
        contract.evaluate(task_id)


def test_scenario_future_timestamp_is_rejected():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-future")
    future_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + 60_000
    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":1906940000,'
        f'"source":"binance-spot","timestamp_ms":{future_ms},'
        '"age_ms":0,"fresh":true,"reference":"1906.94"}'
    )
    with pytest.raises(_FakeRuntime.vm.UserError, match="invalid quote timestamp"):
        contract.evaluate(task_id)


def test_scenario_reference_mismatch_is_rejected():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-ref")
    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":1906940000,'
        '"source":"binance-spot","timestamp_ms":1723900000000,'
        '"age_ms":1000,"fresh":true,"reference":"9999"}'
    )
    with pytest.raises(_FakeRuntime.vm.UserError, match="different reference"):
        contract.evaluate(task_id)


def test_scenario_reference_and_pair_are_url_encoded():
    contract = make_contract()
    contract._quote_snapshot("ETH/USDC & test", "1906.94+foo&bar")
    assert "pair=ETH%2FUSDC%20%26%20test" in _FakeRuntime._Web.captured_url
    assert "reference=1906.94%2Bfoo%26bar" in _FakeRuntime._Web.captured_url


def test_scenario_malformed_response_is_rejected():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-h")
    _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC", "price_x1e6": ')
    with pytest.raises(_FakeRuntime.vm.UserError, match="malformed JSON"):
        contract.evaluate(task_id)


def test_scenario_malformed_missing_fields_is_rejected():
    contract = make_contract()
    task_id = create_eth_task(contract)
    contract.submit_answer(task_id, "1906.94", "agent-i")
    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","source":"binance-spot",'
        '"fresh":true,"age_ms":100,"reference":"1906.94"}'
    )
    with pytest.raises(_FakeRuntime.vm.UserError, match="missing required fields"):
        contract.evaluate(task_id)
