# Agent Judge

A GenLayer Intelligent Contract that evaluates an agent's numeric answer against a fresh external market quote while keeping the verdict, reputation, and dispute logic on-chain.

## Live demo

Frontend: https://agentjudge.netlify.app

The frontend is a Vite app in `frontend/` that connects to the GenLayer contract on Studionet. It supports wallet connection, task creation, answer submission, evaluation, task inspection, and reputation inspection.

## Deployment

The Netlify deployment is defined in the repository by `netlify.toml`:

```text
base directory:    frontend
build command:     npm run build
publish directory: frontend/dist
Node version:      22
```

To deploy from this repository, connect the GitHub repo to a Netlify site. Netlify reads `netlify.toml` and builds on every push to `main`. The publish directory in `netlify.toml` is `dist`, which Netlify resolves relative to the `frontend` base directory, so the built output is `frontend/dist`. No environment variables are needed, because the contract address and chain are set in `frontend/src/main.js`.

To build locally:

```bash
cd frontend
npm install
npm run build
npm run preview
```

`npm run build` writes `frontend/dist/` (`index.html` plus `assets/`). `frontend/package-lock.json` pins `genlayer-js` to `1.1.8` and `vite` to `8.3.1`, so local builds, the Netlify build, and the CI job install the same dependency tree.

## Live data path

The current live path is:

```text
GenLayer AgentJudge
        |
        v
Cloudflare Worker relayer
        |
        v
Binance API
```

The Binance price endpoint needs no API key or secret. The contract accepts only quote responses whose `source` is `binance`.

For local development, `relayer/server.js` implements the same Binance response contract with an injectable API base, so the relayer tests do not contact Binance.

## Quality-bar mapping

**1. Real trust problem**

Agent outputs can be wrong or stale. The judge obtains an external market reference and makes the verdict reproducible through GenLayer consensus.

**2. Intelligent Contract**

The core evaluation path is implemented as a Python GenLayer Intelligent Contract using `gl.eq_principle.prompt_comparative` around the external quote fetch. Validator quote movement is tolerated up to 50 bps, while the agent's own answer is compared deterministically against the agreed quote using the task's `tolerance_bps`.

**3. Live authoritative data boundary**

Binance is the current external quote provider. The relayer validates the upstream response, converts the price to integer `price_x1e6`, enforces a 60 second freshness window, and returns a normalized JSON payload. Binance returns no timestamp in the response body, so the quote time is taken from the HTTP `Date` header.

**4. Consensus-aware design**

The comparative equivalence principle requires the pair, source, and reference to match. Independent validator prices may move within 50 bps, and timestamp/age metadata may differ as long as each quote passes freshness and timestamp validation.

**5. Contract lifecycle**

The contract supports:

```text
create_task -> submit_answer -> evaluate -> optional dispute -> re-evaluate
```

A successful evaluation increments the submitted agent's reputation. If a dispute changes an accepted verdict to rejected, the previous reputation credit is removed.

**6. Risk disclosure**

The MVP still has a single-provider trust boundary, no dispute staking, and no dispute rate limiting. These are documented in `docs/architecture.md`.

## Repository

```text
contracts/agent_judge.py
relayer/server.js
relayer/server.test.js
relayer/worker.js
frontend/index.html
frontend/package.json
frontend/package-lock.json
frontend/src/main.js
tests/test_contract_static.py
tests/test_contract_behavior.py
tests/test_quote_agreement.py
docs/architecture.md
.github/workflows/test.yml
netlify.toml
verification.md
```

## Run the relayer locally

```bash
cd relayer
npm install
npm test
npm start
```

The live relayer needs no API key. It reads `BINANCE_API_BASE` only if you want to point it at another host. The tests inject a local upstream server, so they do not contact Binance.

## GenLayer Studio

Deploy the current `contracts/agent_judge.py` with the deployed Cloudflare Worker URL as the constructor argument.

The current public contract instance is:

```text
0x0F4c2b69BC64784Ef26A15ddAFceb733c4276949
```

Then use:

```text
create_task(prompt, reference_value, tolerance_bps, pair)
submit_answer(task_id, answer_value, agent_label)
evaluate(task_id)
dispute(task_id)
get_task(task_id)
get_reputation(agent_label)
```

Example task:

```text
prompt: ETH price
reference_value: 2478
tolerance_bps: 100
pair: ETHUSDC
```

The Binance adapter passes the requested pair straight through as a symbol, so a request for `ETHUSDC` is a request for Binance's `ETHUSDC` market rather than a base asset price relabelled to the pair. The relayer still supports the pairs it did before (`ETHUSDC`, `ETHUSDT`, `ETHUSD`) and nothing else.

Do not claim a successful live verdict until the Studio evaluation transaction itself reaches `FINALIZED` without a rollback.

## Testing

```bash
python -m pytest -v
cd relayer
npm install
npm test
```

Local result on 2026-09-29: 28 Python tests passed, 6 relayer tests passed. The CI workflow in `.github/workflows/test.yml` runs the same two jobs plus a frontend build job.

For final GenLayer validation, also run the current GenLayer linter and Studio-mode integration flow.
