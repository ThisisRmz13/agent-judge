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
    def __init__(self, body): self.body = body.encode("utf-8")

_DEFAULT_RESPONSE = '{"pair":"ETH/USDC","price_x1e6":1906940000,"source":"binance-spot","timestamp_ms":1723900000000,"age_ms":1000,"fresh":true,"reference":"1906.94"}'

class _FakeRuntime:
    class Contract: pass
    TreeMap = _TreeMap
    Address = _Address
    u8 = staticmethod(int); u32 = staticmethod(int); u64 = staticmethod(int)
    class _Public:
        class _Write:
            def __call__(self, fn): return fn
        class _View:
            def __call__(self, fn): return fn
        write = _Write(); view = _View()
    public = _Public()
    class _Message: sender_address = _Address("creator")
    message = _Message()
    class _VM:
        class UserError(Exception): pass
    vm = _VM()
    class _Web:
        response = _Response(_DEFAULT_RESPONSE); captured_url = ""; raises = None
        @staticmethod
        def request(url, method="GET"):
            _FakeRuntime._Web.captured_url = url
            if _FakeRuntime._Web.raises is not None: raise _FakeRuntime._Web.raises
            return _FakeRuntime._Web.response
    class _Nondet: pass
    nondet = _Nondet()
    class _EqPrinciple:
        @staticmethod
        def prompt_comparative(fn, principle=""): return fn()
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
    fake.gl = _FakeRuntime; fake.TreeMap = _TreeMap; fake.Address = _Address
    fake.u8 = int; fake.u32 = int; fake.u64 = int
    sys.modules["genlayer"] = fake
    spec = importlib.util.spec_from_file_location("agent_judge_under_test", CONTRACT)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.AgentJudge

def make_contract():
    contract = load_contract()("https://agent-judge-relayer-production.up.railway.app")
    for name in ("task_data", "task_status", "task_creator", "task_agent", "task_answer", "task_verdict", "reputation", "reputation_credited", "dispute_count"):
        setattr(contract, name, _TreeMap())
    return contract

def create_eth_task(contract, prompt="ETH price", reference="1906.94", tolerance=100):
    return contract.create_task(prompt, reference, tolerance, "ETH/USDC")

def test_scenario_accepted_answer_credits_reputation():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-a")
    assert '"accepted": true' in c.evaluate(tid); assert c.get_reputation("agent-a") == 1

def test_scenario_wrong_answer_does_not_credit_reputation():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "2500", "agent-b")
    assert '"accepted": false' in c.evaluate(tid); assert c.get_reputation("agent-b") == 0

def test_scenario_task_pair_is_bound():
    c = make_contract(); tid = c.create_task("BTC price", "60000", 100, "BTC/USDC")
    stored = c.task_data[tid]
    assert '"pair": "BTCUSDC"' in stored
    assert '"pair": "BTCUSDC"' in c.get_task(tid)

def test_scenario_dispute_requires_creator_and_is_one_shot():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-c"); c.evaluate(tid)
    _FakeRuntime.message.sender_address = _Address("attacker")
    with pytest.raises(_FakeRuntime.vm.UserError, match="only the task creator can dispute"): c.dispute(tid)
    _FakeRuntime.message.sender_address = _Address("creator"); c.dispute(tid)
    with pytest.raises(_FakeRuntime.vm.UserError, match="task has already been disputed"): c.dispute(tid)

def test_scenario_verdict_reversal_removes_prior_reputation_credit():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-d"); c.evaluate(tid)
    _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC","price_x1e6":2200000000,"source":"binance-spot","timestamp_ms":1723900000000,"age_ms":1000,"fresh":true,"reference":"1906.94"}')
    c.dispute(tid); assert c.get_reputation("agent-d") == 0; assert '"accepted": false' in c.get_task(tid)

def test_scenario_live_source_failure_is_rejected():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-e"); _FakeRuntime._Web.response = _Response('{"error":"failed"}')
    with pytest.raises(_FakeRuntime.vm.UserError, match="missing required fields"): c.evaluate(tid)

def test_scenario_actual_http_failure_is_rejected():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-http"); _FakeRuntime._Web.raises = TimeoutError("timeout")
    with pytest.raises(_FakeRuntime.vm.UserError, match="live quote request failed"): c.evaluate(tid)

def test_scenario_requested_pair_must_match_returned_pair():
    c = make_contract(); tid = c.create_task("BTC price", "60000", 100, "BTC/USDC"); c.submit_answer(tid, "60000", "agent-f")
    with pytest.raises(_FakeRuntime.vm.UserError, match="different trading pair"): c.evaluate(tid)

def test_scenario_source_mismatch_is_rejected():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-source")
    _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC","price_x1e6":1906940000,"source":"mock","timestamp_ms":1723900000000,"age_ms":1000,"fresh":true,"reference":"1906.94"}')
    with pytest.raises(_FakeRuntime.vm.UserError, match="approved live source"): c.evaluate(tid)

def test_scenario_stale_quote_is_rejected():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-g")
    _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC","price_x1e6":1906940000,"source":"binance-spot","timestamp_ms":1723900000000,"age_ms":60001,"fresh":false,"reference":"1906.94"}')
    with pytest.raises(_FakeRuntime.vm.UserError, match="stale quote"): c.evaluate(tid)

def test_scenario_fresh_true_but_stale_age_is_rejected():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-fresh")
    _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC","price_x1e6":1906940000,"source":"binance-spot","timestamp_ms":1723900000000,"age_ms":60001,"fresh":true,"reference":"1906.94"}')
    with pytest.raises(_FakeRuntime.vm.UserError, match="stale quote"): c.evaluate(tid)

def test_scenario_future_timestamp_is_rejected():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-future")
    future_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + 60000
    _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC","price_x1e6":1906940000,"source":"binance-spot","timestamp_ms":%d,"age_ms":0,"fresh":true,"reference":"1906.94"}' % future_ms)
    with pytest.raises(_FakeRuntime.vm.UserError, match="invalid quote timestamp"): c.evaluate(tid)

def test_scenario_reference_mismatch_is_rejected():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-ref")
    _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC","price_x1e6":1906940000,"source":"binance-spot","timestamp_ms":1723900000000,"age_ms":1000,"fresh":true,"reference":"9999"}')
    with pytest.raises(_FakeRuntime.vm.UserError, match="different reference"): c.evaluate(tid)

def test_scenario_reference_and_pair_are_url_encoded():
    c = make_contract()
    c._quote_snapshot("ETH/USDC & test", "1906.94+foo&bar") if False else None
    _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC & TEST","price_x1e6":1906940000,"source":"binance-spot","timestamp_ms":1723900000000,"age_ms":1000,"fresh":true,"reference":"1906.94+foo&bar"}')
    c._quote_snapshot("ETH/USDC & test", "1906.94+foo&bar")
    assert "pair=ETH%2FUSDC%20%26%20test" in _FakeRuntime._Web.captured_url
    assert "reference=1906.94%2Bfoo%26bar" in _FakeRuntime._Web.captured_url

def test_scenario_malformed_response_is_rejected():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-h"); _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC", "price_x1e6": ')
    with pytest.raises(_FakeRuntime.vm.UserError, match="malformed JSON"): c.evaluate(tid)

def test_scenario_malformed_missing_fields_is_rejected():
    c = make_contract(); tid = create_eth_task(c); c.submit_answer(tid, "1906.94", "agent-i"); _FakeRuntime._Web.response = _Response('{"pair":"ETH/USDC","source":"binance-spot","fresh":true,"age_ms":100,"reference":"1906.94"}')
    with pytest.raises(_FakeRuntime.vm.UserError, match="missing required fields"): c.evaluate(tid)
