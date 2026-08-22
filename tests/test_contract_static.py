from pathlib import Path

CONTRACT = Path(__file__).parents[1] / 'contracts' / 'agent_judge.py'
RELAYER = Path(__file__).parents[1] / 'relayer' / 'server.js'


def read_contract():
    return CONTRACT.read_text()


def test_required_public_api_and_real_relayer_config():
    src = read_contract()
    for name in ['create_task', 'submit_answer', 'evaluate', 'dispute', 'get_task', 'get_reputation']:
        assert f'def {name}(' in src
    assert 'relayer_url: str' in src
    assert 'agent-judge-relayer.example' not in src
    assert '.example' in src
    assert 'self.task_data = TreeMap()' in src


def test_nondeterminism_is_isolated():
    src = read_contract()
    assert 'gl.nondet.web.request' in src
    assert 'gl.eq_principle.prompt_comparative' in src
    assert 'gl.eq_principle.strict_eq' not in src
    assert 'storage' not in src.split('def _quote_snapshot', 1)[1].split('def _evaluate', 1)[0]


def test_validator_agreement_tolerates_quote_movement():
    src = read_contract()
    assert 'gl.eq_principle.prompt_comparative' in src
    assert '50 basis points' in src or '50 bps' in src.lower()
    assert 'pair' in src and 'source' in src


def test_dispute_is_authorized_and_one_shot():
    src = read_contract()
    assert 'task_creator: TreeMap[str, Address]' in src
    assert 'gl.message.sender_address' in src
    assert 'only the task creator can dispute' in src
    assert 'task has already been disputed' in src
    assert 'dispute_count.get(task_id, u32(0)) != u32(0)' in src


def test_reputation_reconciles_after_verdict_change():
    src = read_contract()
    assert 'reputation_credited: TreeMap[str, bool]' in src
    assert 'old_accepted' in src
    assert 'old_accepted and not accepted' in src
    assert 'current - u32(1)' in src
    assert 'accepted and not old_accepted' in src


def test_live_relayer_has_real_upstream_adapter():
    src = RELAYER.read_text()
    assert 'api.binance.com/api/v3/ticker/24hr' in src
    assert 'source: \'binance-spot\'' in src
    assert 'lastPrice' in src
    assert 'closeTime' in src
    assert 'MAX_QUOTE_AGE_MS' in src
    assert 'return json(res, 501' not in src
    assert 'price_x1e6: Math.round(price * 1e6)' in src
