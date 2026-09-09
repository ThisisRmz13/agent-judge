# Verification

## Steward feedback fixes (timestamped pair validation)

- The quote path binds the requested pair: the contract normalizes the requested pair, URL-encodes it into the relayer request, and rejects any response whose returned pair does not match after normalization.
- Quote freshness is validated independently of relayer self-reporting: the contract compares `timestamp_ms` against its own clock (allowing 5s clock skew), rejects future timestamps, and takes `effective_age_ms = max(age_ms, timestamp_age_ms)` so a relayer cannot hide a stale timestamp behind a small reported age. Quotes older than 60 seconds are rejected.
- Post-consensus re-validation: after `prompt_comparative` returns, the contract re-checks pair, source, reference, fresh, and price, **and re-validates timestamp and age timing through the same `_validate_quote_timing` helper** — a forged `fresh=true` flag or fabricated `age_ms` in the consensus output cannot pass final checks. Covered by four tampered-consensus tests.
- Validator agreement tolerates legitimate quote movement: prices from independent validator fetches may differ by up to 50 bps, and timestamp/age may differ; identity fields (pair, source, reference) must match exactly.

## Dispute and reputation fixes

- Only the original task creator can dispute; completed tasks only; one dispute per task.
- Reputation reconciles when a verdict is reversed: an accepted-then-rejected verdict removes the previously credited reputation point, and a rejected-then-accepted one credits it.

## Verification status

- Comparative quote consensus: implemented
- Exact pair/source/reference matching: implemented
- 50 bps quote movement tolerance: implemented
- Freshness validation with timestamp cross-check: implemented
- Post-consensus timestamp/age re-validation: implemented (4 tampered-consensus tests)
- Malformed JSON handling: implemented
- Missing required field handling: implemented
- Failed provider response handling: implemented (HTTP failure and malformed upstream)
- Local Python test suite: 28 passed (`python -m pytest -v`)
- Relayer test suite: 6 passed (`npm test` in `relayer/`)
- GitHub Actions: triggered by push of these changes
- GenLayer Studio `evaluate`: pending live verification
