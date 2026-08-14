# Agent Judge

A GenLayer Intelligent Contract that evaluates agent answers against an external market quote while keeping the final verdict and reputation logic on-chain.

## Quality-bar mapping

**1. Real trust problem**

Agent outputs can be wrong or stale. The judge obtains an external market reference and makes the verdict reproducible through GenLayer consensus.

**2. Intelligent Contract**

The core evaluation path is implemented as a Python GenLayer Intelligent Contract using `gl.eq_principle.strict_eq` around the external quote fetch.

**3. Live or authoritative data path**

The architecture supports a relayed authoritative quote source. The repository defaults to mock mode because no provider credential is required for the submission package. Live mode is documented separately and is never represented as live while mock mode is active.

**4. Consensus-aware design**

Only normalized, structured quote data participates in strict equality. The tolerance comparison is deterministic and happens after consensus.

**5. Working app path**

`frontend/index.html` provides the interaction surface. The contract API is explicit and ready to connect to GenLayerJS. The relayer exposes `/health` and `/quote` for the external-data boundary.

**6. Risk disclosure**

Known limitations, provider dependence, relayer trust boundary, tolerance assumptions, reputation scope, and disputes are documented in `docs/architecture.md`.

**7. Demonstrable testing**

Static contract checks are included. Before submission, run them and then execute a Studio integration flow for deployment, `create_task`, `submit_answer`, `evaluate`, and `get_task`.

**8. Continued-use path**

Reputation is persisted on-chain and exposed through `get_reputation`, while the architecture defines a credible path toward marketplace ranking and multi-source quote validation.

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

The default mode is mock. It is intentionally labeled as mock data.

## GenLayer Studio

Load `contracts/agent_judge.py` into Studio, deploy it with the default constructor, then exercise:

```text
create_task(prompt, reference_value, tolerance_bps)
submit_answer(task_id, answer_value, agent_label)
evaluate(task_id, pair)
get_task(task_id)
get_reputation(agent_label)
```

A real end-to-end live-data deployment requires the relayer URL to be changed from the placeholder domain in the contract and a live provider adapter to be configured. Do not claim the live path has been validated until that integration is actually run.

## Testing

```bash
python -m pytest tests -q
```

For full GenLayer validation, also run the current GenLayer linter and Studio-mode integration tests in an installed GenLayer environment.
