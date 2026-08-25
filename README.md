# Agent Judge

A GenLayer Intelligent Contract that evaluates an agent's numeric answer against a fresh external market quote while keeping the verdict, reputation, and dispute logic on-chain.

## Live data path

The current live path is:

```text
GenLayer AgentJudge
        |
        v
Cloudflare Worker relayer
        |
        v
CoinCap API
```

The deployed Worker is configured with the `COINCAP_API_KEY` secret. The contract accepts only quote responses whose `source` is `coincap`.

For local development, `relayer/server.js` implements the same CoinCap response contract with an injectable API base and API key, so the relayer tests do not require a real credential.

## Quality-bar mapping

**1. Real trust problem**

Agent outputs can be wrong or stale. The judge obtains an external market reference and makes the verdict reproducible through GenLayer consensus.

**2. Intelligent Contract**

The core evaluation path is implemented as a Python GenLayer Intelligent Contract using `gl.eq_principle.prompt_comparative` around the external quote fetch. Validator quote movement is tolerated up to 50 bps, while the agent's own answer is compared deterministically against the agreed quote using the task's `tolerance_bps`.

**3. Live authoritative data boundary**

CoinCap is the current external quote provider. The relayer validates the upstream response, converts the price to integer `price_x1e6`, enforces a 60 second freshness window, and returns a normalized JSON payload.

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
frontend/src/main.js
tests/test_contract_static.py
tests/test_contract_behavior.py
tests/test_quote_agreement.py
docs/architecture.md
```

## Run the relayer locally

```bash
cd relayer
npm install
npm test
npm start
```

Set `COINCAP_API_KEY` before starting the live relayer. The tests inject a fake key and a local upstream server, so they do not contact CoinCap.

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

The current CoinCap adapter uses the base asset from pairs such as `ETHUSDC` and returns the CoinCap USD price under the requested pair label. The project should therefore treat `ETHUSDC` as the current MVP market identifier, not as proof of a direct CoinCap ETH/USDC order-book quote.

Do not claim a successful live verdict until the Studio evaluation transaction itself reaches `FINALIZED` without a rollback.

## Testing

```bash
python -m pytest tests -q
cd relayer
npm test
```

For final GenLayer validation, also run the current GenLayer linter and Studio-mode integration flow.
