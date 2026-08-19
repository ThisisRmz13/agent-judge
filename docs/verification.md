# Verification Evidence

This document records the evidence for the fixes applied in response to the "Action needed" status from the GenLayer Foundation steward on submission `32be1da4-80f8-417d-928d-e56703f93381`.

## Summary of changes

1. Replaced the placeholder quote path in the relayer with a live Binance Spot adapter.
2. Added requested-pair validation and quote freshness validation in the contract/relayer flow.
3. Restricted dispute initiation to the original task creator and prevented repeated disputes.
4. Corrected reputation transitions when a verdict changes, including reversal of a prior reputation credit.
5. Added behavioral and static tests covering live-source failures, pair mismatches, stale quotes, authorization, repeated disputes, reputation transitions, and the live adapter configuration.

## 1. Live Binance API adapter

**Files:** `contracts/agent_judge.py`, `relayer/server.js`

The relayer uses Binance Spot `GET /api/v3/ticker/24hr` in live mode. It normalizes the requested pair, reads `lastPrice` and `closeTime`, computes quote age, rejects stale upstream data above `MAX_QUOTE_AGE_MS`, and returns a normalized payload containing `pair`, `price_x1e6`, `timestamp_ms`, `age_ms`, `fresh`, and `source: "binance-spot"`.

The contract validates that the returned pair matches the requested pair, the source is the approved live source, the quote is marked fresh, the quote age is within `MAX_QUOTE_AGE_MS`, and the quote timestamp is valid before using the price.

## 2. Dispute restricted to task creator

**File:** `contracts/agent_judge.py`

`dispute()` compares `gl.message.sender_address` with the stored task creator and raises `"only the task creator can dispute"` for unauthorized callers. It also rejects a second dispute when `dispute_count` is already nonzero.

Behavioral coverage:

- `test_scenario_dispute_requires_creator_and_is_one_shot`
- `test_dispute_is_authorized_and_one_shot`

## 3. Corrected reputation transitions

**File:** `contracts/agent_judge.py`

The contract tracks whether a task previously received a reputation credit using `reputation_credited`. A successful verdict credits reputation once. If a later dispute changes the verdict from accepted to rejected, the prior credit is removed and the credited flag is cleared.

Behavioral coverage:

- `test_scenario_accepted_answer_credits_reputation`
- `test_scenario_wrong_answer_does_not_credit_reputation`
- `test_scenario_verdict_reversal_removes_prior_reputation_credit`
- `test_reputation_reconciles_after_verdict_change`

## 4. Behavioral and static tests

**Files:** `tests/test_contract_behavior.py`, `tests/test_contract_static.py`

Behavioral tests:

- `test_scenario_accepted_answer_credits_reputation`
- `test_scenario_wrong_answer_does_not_credit_reputation`
- `test_scenario_dispute_requires_creator_and_is_one_shot`
- `test_scenario_verdict_reversal_removes_prior_reputation_credit`
- `test_scenario_live_source_failure_is_rejected`
- `test_scenario_requested_pair_must_match_returned_pair`
- `test_scenario_stale_quote_is_rejected`

Static tests:

- `test_required_public_api_and_real_relayer_config`
- `test_nondeterminism_is_isolated`
- `test_dispute_is_authorized_and_one_shot`
- `test_reputation_reconciles_after_verdict_change`
- `test_live_relayer_has_real_upstream_adapter`

**Evidence — GitHub Actions:**

Run: `Fix nested verdict serialization in get_task #8`

Workflow run: https://github.com/ThisisRmz13/agent-judge/actions/runs/32267162582/job/96114358852

Result:

```text
============================= test session starts ==============================
platform linux -- Python 3.11.16, pytest-9.1.1, pluggy-1.6.0 -- /opt/hostedtoolcache/Python/3.11.16/x64/bin/python
cachedir: .pytest_cache
rootdir: /home/runner/work/agent-judge/agent-judge
collecting ... collected 12 items

tests/test_contract_behavior.py::test_scenario_accepted_answer_credits_reputation PASSED [  8%]
tests/test_contract_behavior.py::test_scenario_wrong_answer_does_not_credit_reputation PASSED [ 16%]
tests/test_contract_behavior.py::test_scenario_dispute_requires_creator_and_is_one_shot PASSED [ 25%]
tests/test_contract_behavior.py::test_scenario_verdict_reversal_removes_prior_reputation_credit PASSED [ 33%]
tests/test_contract_behavior.py::test_scenario_live_source_failure_is_rejected PASSED [ 41%]
tests/test_contract_behavior.py::test_scenario_requested_pair_must_match_returned_pair PASSED [ 50%]
tests/test_contract_behavior.py::test_scenario_stale_quote_is_rejected PASSED [ 58%]
tests/test_contract_static.py::test_required_public_api_and_real_relayer_config PASSED [ 66%]
tests/test_contract_static.py::test_nondeterminism_is_isolated PASSED    [ 75%]
tests/test_contract_static.py::test_dispute_is_authorized_and_one_shot PASSED [ 83%]
tests/test_contract_static.py::test_reputation_reconciles_after_verdict_change PASSED [ 91%]
tests/test_contract_static.py::test_live_relayer_has_real_upstream_adapter PASSED [100%]

============================== 12 passed in 0.04s ==============================
```

## 5. Studio / live integration flow

The relayer is deployed from `ThisisRmz13/agent-judge` with Railway service root `relayer`. The production service exposes `/health` and `/quote`, and the deployed configuration uses `node server.js` with healthcheck path `/health`.

The live adapter implementation is in `relayer/server.js`, and the contract is configured to call the production relayer URL through its nondeterministic web request path.

## Notes for the steward

All four flagged items from the steward review have been addressed in the repository. The GitHub Actions run above provides the final automated verification evidence with all 12 tests passing. The latest implementation commit for the nested verdict serialization fix is `bdff90365f2e6abf074dfabebc2a709b4ba9509b`. This document is the consolidated verification record for re-review.
