from pathlib import Path

CONTRACT = Path(__file__).parents[1] / 'contracts' / 'agent_judge.py'


def test_contract_has_required_public_api():
    src = CONTRACT.read_text()
    for name in ['create_task', 'submit_answer', 'evaluate', 'dispute', 'get_task', 'get_reputation']:
        assert f'def {name}(' in src


def test_nondeterminism_is_isolated():
    src = CONTRACT.read_text()
    assert 'gl.nondet.web.request' in src
    assert 'gl.eq_principle.strict_eq' in src


def test_no_secret_in_contract():
    src = CONTRACT.read_text()
    assert 'ONEINCH_API_KEY' not in src
    assert '.env' not in src
