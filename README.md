# Agent Judge

A GenLayer Intelligent Contract that evaluates agent answers against an external market quote while keeping the final verdict and reputation logic on-chain.

## Live relayer

The Railway relayer is deployed at:

`https://agent-judge-relayer-production.up.railway.app`

Deploy the contract with that URL as the `relayer_url` constructor argument.

## Quality-bar mapping

**1. Real trust problem**

Agent outputs can be wrong or stale. The judge obtains an external market reference and makes the verdict reproducible through GenLayer consensus.

**2. Intelligent Contract**

The core evaluation path is implemented as a Python GenLayer Intelligent Contract using `gl.eq_principle.strict_eq` around the external quote fetch.

**3. Live or authoritative data path**

The relayer provides the external quote boundary. Mock mode remains available for local development, while the deployed Railway service is configured for live mode.

**4. Consensus-aware design**

Only normalized, structured quote data participates in strict equality. The tolerance comparison is deterministic and happens after consensus.

**5. Working app path**

`frontend/index.html` provides the interaction surface. The contract API is explicit and ready to connect to GenLayerJS. The relayer exposes `/health` and `/quote` for the external-data boundary.

**6. Risk disclosure**

Known limitations, provider dependence, relayer trust boundary, tolerance assumptions, reputation scope, and disputes are documented in `docs/architecture.md`.

**7. Demonstrable testing**

Static contract checks are included. Before submission, run them and execute a Studio integration flow for deployment, `create_task`, `submit_answer`, `evaluate`, `dispute`, and `get_task`.

**8. Continued-use path**

Reputation is persisted on-chain and exposed through `get_reputation`, while the architecture defines a path toward marketplace ranking and multi-source quote validation.

## Repository

```text
contracts/agent_judge.py
relayer/server.js
relayer/.env.example
frontend/index.html
tests/test_contract_static.py
docs/architecture.md
```

## Run the relayer locally

```bash
cd relayer
npm install
npm start
```

The local default mode is mock. The Railway deployment is configured separately for the live adapter.

## GenLayer Studio

Load `contracts/agent_judge.py` into Studio and deploy it with:

```text
AgentJudge("https://agent-judge-relayer-production.up.railway.app")
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

Do not claim a successful live verdict until the Studio integration flow has actually been executed against the deployed relayer.

## Testing

```bash
python -m pytest tests -q
```

For full GenLayer validation, also run the current GenLayer linter and Studio-mode integration tests in an installed GenLayer environment.
