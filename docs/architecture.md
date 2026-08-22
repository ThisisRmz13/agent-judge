# Agent Judge architecture

## What the MVP proves

Agent Judge is a GenLayer Intelligent Contract that evaluates an agent's submitted numeric answer against a freshly fetched market quote. The contract owns task state, verdicts, reputation, and dispute history. External market data is the only non-deterministic input.

The intended trust boundary is simple:

`Agent -> Intelligent Contract -> Equivalence Principle -> relayer -> market API`

The relayer is a transport adapter. It does not decide whether an answer passes, does not write contract state, and does not award reputation.

## Consensus design

Each validator independently executes the external quote request inside the `prompt_comparative` equivalence principle. The returned payload is compared as a normalized quote rather than by strict equality. The trading pair and source identifier must match exactly across validator results. The live `price_x1e6` value may differ by up to 50 basis points (0.5%) because validators fetch the live quote independently and legitimate market movement can occur between fetches. `timestamp_ms` and `age_ms` may also differ between validators, provided each result satisfies the contract's freshness window.

This comparative equivalence is intentionally limited to the expected volatility of the live quote. It does not permit a different trading pair, a different quote source, or a stale response to reach consensus.

The contract then performs the task-specific answer tolerance comparison deterministically after consensus returns. A submission passes when its value is within `tolerance_bps` of the agreed live quote.

This follows the GenLayer requirement that `gl.nondet.web.*` calls live inside an Equivalence Principle function, while deterministic state changes occur outside that non-deterministic block.

## Why the relayer exists

The relayer keeps provider credentials off-chain and out of public client code. It forwards a quote request and normalizes the provider response. It cannot change the verdict because verdict calculation and reputation updates are performed by the Intelligent Contract after consensus.

The relayer is therefore an operational trust boundary, not a decision-making authority.

## Tolerance choice

The MVP exposes tolerance as a task parameter in basis points. The consensus layer separately allows up to 50 bps of legitimate live-quote movement between independent validator fetches. The task tolerance controls whether the submitted answer is accepted against the agreed quote.

A production configuration should benchmark repeated quotes during realistic volatility and choose a task tolerance from observed provider variance, expected market movement, and the acceptable false-reject rate. A live benchmark requires provider credentials and is intentionally not faked by this repository.

## Known limitations and future hardening

### Single data source risk

The current MVP can operate against one authoritative source through the relayer. If that provider is unavailable or stale, evaluation can fail. This is accepted as an MVP limitation.

### Path to hardening

A production version should query at least one additional source, such as another exchange aggregator, inside the same non-deterministic evaluation flow and require cross-source agreement before accepting a quote. This reduces dependence on one provider and gives the judge a stronger basis for resolving stale or anomalous data.

### Reputation usage

`get_reputation` stores a per-agent successful evaluation count on-chain. The MVP does not use reputation to alter a verdict. The intended continued-use path is a public reputation layer that marketplaces can query, with an optional future policy that uses reputation only to break ties or prioritize agents in task routing.

### Dispute mechanism

`dispute()` is intentionally minimal. A completed task can be disputed and triggers a fresh evaluation against newly fetched live data. The new verdict replaces the previous stored verdict when the re-evaluation runs. The current MVP has no staking or rate limiting, so production deployments should add anti-spam controls and a bounded dispute window.

## Workflow

1. A user creates a task with a reference value and tolerance.
2. An agent submits an answer.
3. Validators independently obtain the external quote inside `prompt_comparative`.
4. Consensus accepts equivalent live quotes when pair and source match exactly, price movement is within 50 bps, and each quote is fresh.
5. The contract compares the answer with the agreed quote.
6. A passing answer increments the agent's reputation counter.
7. A completed task can be disputed and re-evaluated with fresh data.

## Submission boundary

The repository intentionally includes a mock relayer mode so the complete workflow can be demonstrated without an API key. This is a test/demo mode and must not be described as live market data.
