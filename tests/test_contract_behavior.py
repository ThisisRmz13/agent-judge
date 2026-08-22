import importlib.util
import sys
import types
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
    '"age_ms":1000,"fresh":true}'
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

        @staticmethod
        def request(url, method="GET"):
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


def test_scenario_accepted_answer_credits_reputation():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")

    task_id = contract.create_task("ETH price", "1906.94", 100)
    contract.submit_answer(task_id, "1906.94", "agent-a")
    verdict = contract.evaluate(task_id, "ETH/USDC")

    assert '"accepted": true' in verdict
    assert contract.get_reputation("agent-a") == 1


def test_scenario_wrong_answer_does_not_credit_reputation():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")

    task_id = contract.create_task("ETH price", "1906.94", 100)
    contract.submit_answer(task_id, "2500", "agent-b")
    verdict = contract.evaluate(task_id, "ETH/USDC")

    assert '"accepted": false' in verdict
    assert contract.get_reputation("agent-b") == 0


def test_scenario_dispute_requires_creator_and_is_one_shot():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")
    task_id = contract.create_task("ETH price", "1906.94", 100)
    contract.submit_answer(task_id, "1906.94", "agent-c")
    contract.evaluate(task_id, "ETH/USDC")

    _FakeRuntime.message.sender_address = _Address("attacker")
    try:
        contract.dispute(task_id, "ETH/USDC")
        assert False, "unauthorized dispute must fail"
    except _FakeRuntime.vm.UserError as exc:
        assert str(exc) == "only the task creator can dispute"

    _FakeRuntime.message.sender_address = _Address("creator")
    contract.dispute(task_id, "ETH/USDC")
    try:
        contract.dispute(task_id, "ETH/USDC")
        assert False, "duplicate dispute must fail"
    except _FakeRuntime.vm.UserError as exc:
        assert str(exc) == "task has already been disputed"


def test_scenario_verdict_reversal_removes_prior_reputation_credit():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")

    task_id = contract.create_task("ETH price", "1906.94", 100)
    contract.submit_answer(task_id, "1906.94", "agent-d")
    contract.evaluate(task_id, "ETH/USDC")
    assert contract.get_reputation("agent-d") == 1

    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":2200000000,'
        '"source":"binance-spot","timestamp_ms":1723900000000,'
        '"age_ms":1000,"fresh":true}'
    )
    contract.dispute(task_id, "ETH/USDC")

    assert contract.get_reputation("agent-d") == 0
    assert '"accepted": false' in contract.get_task(task_id)


def test_scenario_live_source_failure_is_rejected():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")
    task_id = contract.create_task("ETH price", "1906.94", 100)
    contract.submit_answer(task_id, "1906.94", "agent-e")
    _FakeRuntime._Web.response = _Response('{"error":"live quote request failed"}')

    with pytest.raises(_FakeRuntime.vm.UserError, match="missing required fields"):
        contract.evaluate(task_id, "ETH/USDC")


def test_scenario_requested_pair_must_match_returned_pair():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")
    task_id = contract.create_task("BTC price", "60000", 100)
    contract.submit_answer(task_id, "60000", "agent-f")
    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":1906940000,'
        '"source":"binance-spot","timestamp_ms":1723900000000,'
        '"age_ms":1000,"fresh":true}'
    )

    with pytest.raises(_FakeRuntime.vm.UserError, match="different trading pair"):
        contract.evaluate(task_id, "BTC/USDC")


def test_scenario_stale_quote_is_rejected():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")
    task_id = contract.create_task("ETH price", "1906.94", 100)
    contract.submit_answer(task_id, "1906.94", "agent-g")
    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","price_x1e6":1906940000,'
        '"source":"binance-spot","timestamp_ms":1723900000000,'
        '"age_ms":60001,"fresh":false}'
    )

    with pytest.raises(_FakeRuntime.vm.UserError, match="stale quote"):
        contract.evaluate(task_id, "ETH/USDC")


def test_scenario_malformed_response_is_rejected():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")
    task_id = contract.create_task("ETH price", "1906.94", 100)
    contract.submit_answer(task_id, "1906.94", "agent-h")

    _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC", "price_x1e6": ')

    with pytest.raises(_FakeRuntime.vm.UserError, match="malformed JSON"):
        contract.evaluate(task_id, "ETH/USDC")


def test_scenario_malformed_missing_fields_is_rejected():
    AgentJudge = load_contract()
    contract = AgentJudge("https://agent-judge-relayer-production.up.railway.app")
    task_id = contract.create_task("ETH price", "1906.94", 100)
    contract.submit_answer(task_id, "1906.94", "agent-i")

    _FakeRuntime._Web.response = _Response(
        '{"pair":"ETH/USDC","source":"binance-spot",'
        '"fresh":true,"age_ms":100}'
    )

    with pytest.raises(_FakeRuntime.vm.UserError, match="missing required fields"):
        contract.evaluate(task_id, "ETH/USDC")
