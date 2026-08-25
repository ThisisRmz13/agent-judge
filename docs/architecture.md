# Agent Judge architecture

## What the MVP proves

Agent Judge is a GenLayer Intelligent Contract that evaluates an agent's submitted numeric answer against a freshly fetched market quote. The contract owns task state, verdicts, reputation, and dispute history. External market data is the non-deterministic input.

The current trust boundary is:

`Agent -> Intelligent Contract -> Equivalence Principle -> Cloudflare Worker -> CoinCap API`

The relayer is a transport and validation adapter. It does not decide whether an answer passes, does not write contract state, and does not award reputation.

## Consensus design

Each validator independently executes the external quote request inside `gl.eq_principle.prompt_comparative`. The contract validates the returned payload before it participates in the comparison.

The normalized quote contains the trading pair, integer price in 1e-6 units, source identifier, reference value, and quote timing metadata.

Strict byte-for-byte equality is not used because independent validators fetch live data at slightly different moments. The comparison principle requires the pair, source, and reference to match exactly. Price values may differ by up to 50 bps. Timestamp and age metadata may differ as long as each validator independently satisfies the freshness and timestamp checks.

After consensus returns, the contract deterministically compares the submitted answer with the agreed live price using the task's `tolerance_bps`.

## CoinCap adapter

The current live provider is CoinCap. The Cloudflare Worker reads `COINCAP_API_KEY` from a secret binding and calls the CoinCap price-by-symbol endpoint.

For a requested pair such as `ETHUSDC`, the adapter extracts the base asset (`ETH`) and obtains the CoinCap asset price. The response keeps the requested pair as the contract-facing identifier and labels the source `coincap`.

This is an MVP normalization boundary. It should not be described as a direct CoinCap ETH/USDC order-book quote because CoinCap's asset price is USD-denominated. A future multi-source adapter can provide true quote-pair prices when required.

The Node relayer in `relayer/server.js` mirrors this behavior for local development and tests. It is deliberately dependency-injected so tests can use a local fake upstream without a real CoinCap credential.

## Freshness and integrity checks

The contract rejects:

- missing required quote fields
- returned pair mismatches
- source mismatches
- reference mismatches
- `fresh: false`
- negative or excessive quote age
- non-positive or future timestamps
- non-positive prices

The relayer also rejects stale upstream data before returning a quote.

## Reputation and disputes

`get_reputation` stores a per-agent successful evaluation count on-chain. A completed task can be disputed only by its creator and only once. A dispute triggers a fresh evaluation. If the new verdict reverses an earlier accepted result, the previous reputation credit is reconciled.

The MVP has no dispute staking, rate limiting, or bounded dispute window. These remain production hardening items.

## Known limitations and future hardening

### Single data source risk

CoinCap is currently the single external provider. If it is unavailable or returns data outside the freshness window, evaluation can fail.

### Pair semantics

The MVP accepts market identifiers such as `ETHUSDC`, but the current CoinCap adapter obtains the base asset's USD price. This is suitable for the current demo but should be replaced with a true quote-pair source before presenting the system as an exact USDC oracle.

### Multi-source validation

A production version should query at least one additional independent source inside the same non-deterministic evaluation flow and require cross-source agreement.

### Frontend

The repository includes a small browser UI that can call the relayer health and quote endpoints. It is an operational demo surface, not a replacement for GenLayer Studio.

## Workflow

1. A user creates a task with a prompt, reference value, tolerance, and pair.
2. An agent submits an answer.
3. Validators independently obtain the external quote inside the comparative Equivalence Principle boundary.
4. Consensus returns a normalized quote.
5. The contract compares the answer with the agreed quote.
6. A passing answer increments the agent's reputation.
7. The task creator may dispute once, causing a fresh evaluation.

## Submission boundary

The repository contains deterministic local relayer tests. The live Cloudflare Worker requires the `COINCAP_API_KEY` secret and should be the relayer URL used by the deployed contract.
