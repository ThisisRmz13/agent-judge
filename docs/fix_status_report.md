# Steward Fix Status Report

Submission: `32be1da4-80f8-417d-928d-e56703f93381` — Projects / Agent Judge
Repository: https://github.com/ThisisRmz13/agent-judge
Last updated: 2026-09-09

> خلاصه (Finglish): Hame-ye khast-haye steward piade-sazi shod. Quote source faghat **CoinCap** hast (provider-e ghabli pak shode). `fresh=true` be tanhayi baraye freshness kafi nist — timestamp va age dotayi dobare ba'd az consensus check mishan. Python 28/28 va relayer 6/6 sabz hastand. Faghat Resubmit ba matn-e CoinCap va link-e CI-e jadid mande.

## 1) Chikar bayad mikardi (Steward chikar khasth)

1. Placeholder quote path ro ba yek source-e live-e vaghe'i avaz koni ke joz-e darkhasti (`requested pair`) va tazegi-ye quote (`freshness`) ro validate kone.
2. Dispute va reputation transitions ro dorost koni (tanha creator betavanad dispute konad, yekbar masraf, reversal-e reputation).
3. `prompt_comparative` baraye 50 bps quote movement tolerance.
4. Behavioral test-haye passing baraye: failed source, malformed JSON, stale quotes, mismatched pair/source, HTTP/provider failure.
5. Timestamp/freshness validation bayad mostaghel az `relayer` bashad (contract-clock, clock skew 5s, effective age).
6. **Post-consensus**: khoruji-ye consensus harchi ham `fresh=true` dasht, bayad dobare timestamp va age az nazar-e contract check shavand — `age_ms=0` ya `fresh=true` nabayad stale timestamp ro bepooshanad. Chahar test-e tampered-consensus baray hamin.

## 2) Chikar karde (ta alan)

### Commits
- `b9f9634` — *Enforce timestamped pair validation and quote freshness; repair tests and verification notes*
  - `_quote_snapshot` strict pair binding + source/reference/fresh/age/timestamp/price validation, URL-encoding-e pair/reference.
  - Test-haye 2024 hardcode → dynamic timestamps (`_quote_body` / `_now_ms`).
  - `verification.md` be CoinCap update shod.
- `b2511a7` — *Re-validate consensus quote timing after prompt_comparative*
  - Helper-e `_validate_quote_timing(timestamp_ms, age_ms)` — single source of truth baraye hame-ye timing checks.
  - `_quote_snapshot` va post-consensus-e `_fetch_and_compute` har do az hamin helper estefade mikonand.
  - Post-consensus: pair/source/reference/fresh + `timestamp_ms`/`age_ms`/`price_x1e6` numeric + `_validate_quote_timing` + price>0. Yani forge-haye `fresh=true` ya `age_ms=0` dige nemitoonand stale timestamp ro pass konand.
  - Chahar test-e tampered-consensus ezafe shod.
  - `verification.md` va `docs/verification.md` be-rooz shodand ta post-consensus re-validation va 28 test ro tozih dahand.

### Quote path (source: CoinCap)
- `relayer/server.js` + `relayer/worker.js`: adapter-e live-e CoinCap (`rest.coincap.io/v3/price/bysymbol/{asset}`) ba `COINCAP_API_KEY` (Bearer), `source: "coincap"`.
- `contracts/agent_judge.py`: `MAX_QUOTE_AGE_MS = 60_000`, `CLOCK_SKEW_MS = 5_000`.
- `_validate_quote_timing` rejects: `age_ms` manfi ya >60s, `timestamp_ms` ≤0 ya >5s dar ayandeh, `effective_age_ms = max(age_ms, max(0, now - timestamp_ms))` >60s.

### Validator agreement
- `gl.eq_principle.prompt_comparative` — identity fields (pair, source, reference) bayad daghighan yeki bashand; price-ha ta 50 bps tafavot, timestamp/age mitavanand fargh konand chon har validator jodagane freshness ro pass karde.

### Dispute & reputation
- `dispute()`: tanha creator, tanha task-haye completed, tanha yekbar (`dispute_count` check).
- `_apply_verdict` moshtarak baraye `evaluate` va `dispute`; reversal-e reputation dorost reconciliation mishavad.
- `get_task`: double-encoding-e verdict barطرف shode.

### Tests
- Behavioral 16: accepted/wrong answer, pair binding, dispute auth + one-shot, reversal, live-source failure, HTTP failure, pair mismatch, source mismatch, stale, fresh-but-stale-age, future timestamp, reference mismatch, URL encoding, malformed JSON, missing fields.
- Agreement + tampered 6: movement ≤50 bps accept, >50 bps reject; 4 tampered-consensus (stale ts, future ts, fresh=true+stale ts, age0+stale ts).
- Static 6: public API, nondeterminism isolation, movement tolerance, dispute checks, reputation reconciliation, CoinCap relayer config.
- Hame test-ha ba timestamp-haye dynamic (`now - age_ms`), na hardcode-e tarikhi.

### CI evidence
- `b9f9634` — https://github.com/ThisisRmz13/agent-judge/actions/runs/34350684187 — `success`.
- `b2511a7` — workflow run bar roo-ye `main` trigger shode; pas az push-e akhar dobare check konid (Actions tab). Local: `python -m pytest -v` 28 passed, `npm test` 6 passed.

## 3) Chikara monde (ghabl az Resubmit)

1. **Anjam shod dar hamin commit**:
   - `docs/verification.md` — tamame eshare-haye provider-e ghabli pak va ba `CoinCap` avaz shodand.
   - `relayer/.env.example` — env-e ghabli pak va ba `COINCAP_API_BASE`/`COINCAP_API_KEY`/`MAX_QUOTE_AGE_MS` avaz shod.
   - `verification.md` — khat-e `Failed provider response handling: implemented` ezafe shod.
2. **Mande**:
   - Commit-e jadid push shavad (dar hамин gozar report shode).
   - GitHub Actions-e akhar ta `success` sabr konid (har do job: `pytest` va `relayer` sabz).
   - **Resubmit** ba matn-e daghigh-e CoinCap (hargez esm-e provider-e ghabli nagoo) va link-e CI-e jadid.
   - (Ekhtiyari vali pishnahadi) yek `evaluate` dar GenLayer Studio ta `FINALIZED` begirid va screenshot begzarid — steward in ra be onvan-e evidence-e live ghabul mikonad.

## 4) Checklist-e nahayi baraye Steward

- [x] Strict requested-pair binding
- [x] CoinCap source validation
- [x] Reference validation
- [x] Timestamp validation
- [x] Contract-clock freshness + future rejection + 5s clock skew + effective-age
- [x] Post-consensus timestamp/freshness re-validation (helper-e moshtarak)
- [x] Validator identity agreement + 50 bps movement
- [x] Malformed JSON / missing fields / failed provider handling
- [x] Dispute authorization, one-shot, reversal/reconciliation
- [x] Python 28 passed, relayer 6 passed
- [x] `CODE` va `DOCS` har do CoinCap (hich esm-e provider-e ghabli nist)

Risk-e baghi-mande: single-source (CoinCap) — dar `docs/architecture.md` be onvan-e limitation-e MVP zekr shode; baraye production multi-source pishnahad shode. In blocker-e Resubmit nist.
