# Verification

## Live quote consensus update

Replaced `gl.eq_principle.strict_eq` with `gl.eq_principle.prompt_comparative` for the live quote consensus, allowing up to 50 bps of legitimate price movement between independent validator fetches while still requiring exact pair/source match. Added two additional tests for malformed relayer responses (invalid JSON and missing fields).

## Verification status

- Comparative quote consensus: implemented
- Exact pair/source matching: implemented
- 50 bps quote movement tolerance: implemented
- Freshness validation: implemented
- Malformed JSON handling: implemented
- Missing required field handling: implemented
- Local test suite: pending execution
- GitHub Actions: pending workflow result
- GenLayer Studio `evaluate`: pending live verification
