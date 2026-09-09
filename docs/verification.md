# Verification Evidence

This document records the evidence for the fixes applied in response to the "Action needed" status from the GenLayer Foundation steward on submission `32be1da4-80f8-417d-928d-e56703f93381`.

## Summary of changes

1. Replaced the placeholder quote path in the relayer with a live CoinCap adapter.
2. Added requested-pair validation and quote freshness validation in the contract/relayer flow, centralized in a `_validate_quote_timing` helper and re-validated after consensus.
3. Restricted dispute initiation to the original task creator and prevented repeated disputes.
4. Corrected reputation transitions when a verdict changes, including reversal of a prior reputation credit.
5. Added behavioral and static tests covering live-source failures, pair mismatches, stale quotes, future timestamps, reference mismatches, authorization, repeated disputes, reputation transitions, validator movement, tampered-consensus scenarios, and the live adapter configuration.

## 1. Live CoinCap adapter

**Files:** `contracts/agent_judge.py`, `relayer/server.js`, `relayer/worker.js`

The relayer uses CoinCap `GET https://rest.coincap.io/v3/price/bysymbol/{asset}` in live mode (requires `COINCAP_API_KEY` as a `Bearer` token). It normalizes the requested pair, extracts the base asset, reads `payload.data[0]` as price and `payload.timestamp` as upstream timestamp, computes `age_ms = max(0, now - timestamp_ms)`, rejects stale upstream data above `MAX_QUOTE_AGE_MS` (60,000 ms), and returns a normalized payload containing `pair`, `price_x1e6`, `timestamp_ms`, `age_ms`, `fresh: true`, and `source: "coincap"` plus the echoed `reference`.

The contract validates that the returned pair matches the requested pair after normalization, the `source` is the approved live source `coincap`, the `reference` matches, numeric fields are valid, `fresh` is exactly `true`, and quote timing passes the contract-clock checks before using the price. Validator agreement uses `gl.eq_principle.prompt_comparative`, requiring exact pair/source/reference agreement while tolerating price movement up to 50 bps and timestamp/age differences that each pass the same timing checks.

## 2. Dispute restricted to task creator

**File:** `contracts/agent_judge.py`

`dispute()` compares `gl.message.sender_address` with the stored task creator and raises `"only the task creator can dispute"` for unauthorized callers. It also rejects a second dispute when `dispute_count` is already nonzero.

Behavioral coverage:

- `test_scenario_dispute_requires_creator_and_is_one_shot`
- `test_dispute_is_authorized_and_one_shot`

## 3. Corrected reputation transitions

**File:** `contracts/agent_judge.py`

The contract tracks whether a task previously received a reputation credit using `reputation_credited`. A successful verdict credits reputation once. If a later dispute changes the verdict from accepted to rejected, the prior credit is removed and the credited flag is cleared. The shared `_apply_verdict` helper is used by both `evaluate` and `dispute`.

Behavioral coverage:

- `test_scenario_accepted_answer_credits_reputation`
- `test_scenario_wrong_answer_does_not_credit_reputation`
- `test_scenario_verdict_reversal_removes_prior_reputation_credit`
- `test_reputation_reconciles_after_verdict_change`

## 4. Freshness and post-consensus timing validation

**File:** `contracts/agent_judge.py`

Timing validation is centralized in `_validate_quote_timing(timestamp_ms, age_ms)`, the single source of truth for freshness. It rejects negative or excessive `age_ms` (> 60,000 ms), rejects non-positive or future timestamps (beyond 5,000 ms clock skew), computes `effective_age_ms = max(age_ms, max(0, now_ms - timestamp_ms))` so a forged `age_ms: 0` cannot hide a stale timestamp, and rejects when `effective_age_ms` exceeds `MAX_QUOTE_AGE_MS`.

The helper is called both from `_quote_snapshot` and from the post-consensus validation path in `_fetch_and_compute`. After `prompt_comparative` returns, the contract independently re-validates pair, source, reference, `fresh == True`, numeric `timestamp_ms`/`age_ms`/`price_x1e6`, and timing via `_validate_quote_timing`. A `fresh: true` flag alone cannot pass a stale timestamp.

Tampered-consensus coverage:

- `test_consensus_with_stale_timestamp_is_rejected`
- `test_consensus_with_future_timestamp_is_rejected`
- `test_consensus_with_fresh_true_but_stale_timestamp_is_rejected`
- `test_consensus_with_fabricated_zero_age_but_stale_timestamp_is_rejected`

## 5. Behavioral and static tests

**Files:** `tests/test_contract_behavior.py`, `tests/test_contract_static.py`, `tests/test_quote_agreement.py`

Behavioral tests (16):

- `test_scenario_accepted_answer_credits_reputation`
- `test_scenario_wrong_answer_does_not_credit_reputation`
- `test_scenario_task_pair_is_bound`
- `test_scenario_dispute_requires_creator_and_is_one_shot`
- `test_scenario_verdict_reversal_removes_prior_reputation_credit`
- `test_scenario_live_source_failure_is_rejected` (provider returns wrong shape)
- `test_scenario_actual_http_failure_is_rejected` (network timeout)
- `test_scenario_requested_pair_must_match_returned_pair`
- `test_scenario_source_mismatch_is_rejected`
- `test_scenario_stale_quote_is_rejected`
- `test_scenario_fresh_true_but_stale_age_is_rejected`
- `test_scenario_future_timestamp_is_rejected`
- `test_scenario_reference_mismatch_is_rejected`
- `test_scenario_reference_and_pair_are_url_encoded`
- `test_scenario_malformed_response_is_rejected`
- `test_scenario_malformed_missing_fields_is_rejected`

Agreement and tampered-consensus tests (6):

- `test_validator_agreement_accepts_legitimate_quote_movement`
- `test_validator_agreement_rejects_excessive_quote_movement`
- `test_consensus_with_stale_timestamp_is_rejected`
- `test_consensus_with_future_timestamp_is_rejected`
- `test_consensus_with_fresh_true_but_stale_timestamp_is_rejected`
- `test_consensus_with_fabricated_zero_age_but_stale_timestamp_is_rejected`

Static tests (6):

- `test_required_public_api_and_real_relayer_config`
- `test_nondeterminism_is_isolated`
- `test_validator_agreement_tolerates_quote_movement`
- `test_dispute_is_authorized_and_one_shot`
- `test_reputation_reconciles_after_verdict_change`
- `test_live_relayer_has_real_upstream_adapter`

All tests use dynamic timestamps (`now - age_ms`), never hardcoded historical timestamps.

**Evidence — GitHub Actions:**

Workflow: `.github/workflows/test.yml` (jobs: `pytest`, `relayer`)

Latest verified run for this implementation: `b2511a7` and the subsequent doc-cleanup commit trigger the workflow; see the Actions tab for the run triggered by the latest push to `main`. Prior verified run:

- `b9f9634` — https://github.com/ThisisRmz13/agent-judge/actions/runs/34350684187 — `success` (28 Python + 6 relayer in that run's successor; 24 Python in `b9f9634` itself before the 4 tampered tests)

Current local verification:

```text
python -m pytest -v  → 28 passed
npm test (relayer)   → 6 passed
```

## 6. Studio / live integration flow

The relayer is deployed as a Cloudflare Worker from `ThisisRmz13/agent-judge` (`relayer/worker.js` and `relayer/server.js` share the same CoinCap adapter). The production service exposes `/health` and `/quote`, configured with the `COINCAP_API_KEY` secret, and the deployed Worker URL (e.g. `https://…workers.dev`) is the `relayer_url` passed to the contract constructor. Healthcheck path is `/health`.

The live adapter implementation is in `relayer/server.js` / `relayer/worker.js`, and the contract is configured to call that URL through its nondeterministic web request path.

## Notes for the steward

All flagged items from the steward review have been addressed in the repository. The approved quote source is **CoinCap** (`source: "coincap"`, `COINCAP_API_KEY`, `COINCAP_API_BASE=https://rest.coincap.io/v3/price/bysymbol`). GitHub Actions provides the automated verification evidence with 28 Python tests and 6 relayer tests passing. The current post-consensus validation enforces timestamp/age timing independently of the `fresh` flag and prevents stale-timestamp forgeries such as `fresh=true + stale timestamp` and `age_ms=0 + stale timestamp`.
