# Agent Judge

A GenLayer Intelligent Contract that evaluates agent answers against an external market quote while keeping the final verdict and reputation logic on-chain.

## Quality-bar mapping

**1. Real trust problem**

Agent outputs can be wrong or stale. The judge obtains an external market reference and makes the verdict reproducible through GenLayer consensus.

**2. Intelligent Contract**

The evaluation path uses `gl.eq_principle.strict_eq` around the external quote fetch. Only normalized quote data enters consensus.

**3. Live authoritative data path**

The relayer now has a live Binance Spot adapter and returns normalized `price_x1e6` data. Mock mode remains available for local tests. The contract no longer contains the `agent-judge-relayer.example` placeholder. Its `relayer_url` is supplied at deployment time and rejects placeholder domains.

**4. Consensus-aware design**

The quote fetch is isolated in the nondeterministic block. The verdict and tolerance calculation happen deterministically after strict equality.

**5. Working app path**

`frontend/index.html` provides the interaction surface. The relayer exposes `/health` and `/quote` for the external-data boundary.

**6. Risk disclosure**

The relayer remains a trust boundary. Binance availability and symbol support are external dependencies. Multi-source validation and a stronger oracle model remain future work.

**7. Dispute and reputation safety**

Tasks record their creator address. Only the task creator can dispute, and each task can be disputed once. A disputed verdict is re-evaluated through the same consensus path. Reputation is reconciled when a verdict changes, including removing a previously credited point when an accepted result becomes rejected.

**8. Testing**

`tests/test_contract_static.py` covers the four review scenarios: real relayer configuration, authorized one-shot disputes, reputation reconciliation after a verdict change, and the live relayer adapter. Run the tests before Studio validation.

## Repository

```text
contracts/agent_judge.py
relayer/server.js
relayer/.env.example
frontend/index.html
tests/test_contract_static.py
docs/architecture.md
```

## Run the relayer

```bash
cd relayer
npm install
npm start
```

For local development use `QUOTE_MODE=mock`. For live quotes use `QUOTE_MODE=live` with the Binance API URL from `.env.example`.

## GenLayer Studio

The constructor now requires the deployed relayer base URL:

```text
AgentJudge(relayer_url)
```

Then exercise:

```text
create_task(prompt, reference_value, tolerance_bps)
submit_answer(task_id, answer_value, agent_label)
evaluate(task_id, pair)
dispute(task_id, pair)
get_task(task_id)
get_reputation(agent_label)
```

For a production submission, use the actual public HTTPS URL of the deployed relayer as `relayer_url`, then run the full Studio flow. The repository does not claim that a live deployment has been validated merely because the adapter exists.

## Testing

```bash
python -m pytest tests -q
```

For full GenLayer validation, also run the current GenLayer linter and Studio integration tests in an installed GenLayer environment.
