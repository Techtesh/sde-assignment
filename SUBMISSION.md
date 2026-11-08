# Outcome-First Agent Loop — Submission

**Name:** [TODO] · **Date:** 2026-11-08 · **Hours actually spent (be honest):** [TODO] · **Language / storage:** Python / PostgreSQL 17

## 0. TL;DR

One Python process and PostgreSQL provide governed experiments, incident repair, durable evidence and a concise supervisor CLI.
Public_01: ten changes, one beneficial and one harmful; no voice winner qualified.
Public_02: two beneficial repairs, no harmful changes, five credits, no LLM call; prompt repair still took 27h30m.
All five real crash boundaries match a clean run; the latest focused suite passes 137 tests on Linux and 136 on Windows (one Linux-only skip). A fresh-checkout run also passes.
Welcome interactions, new cohort discovery, person-level timing, caller exploration, cross-client transfer and a web/notification service are cut.

## 1. Assumptions

1. HTTP workflow policies are authoritative. Controller code never imports simulator code, reads simulator run files, or parses scenario truth. Baseline/grade commands are external verification only.
2. Simulated Asia/Kolkata time governs windows, permission and checkpoints. Cadence, capacity and calling windows are business-owned. Reads do not advance the world.
3. History supports matched cohort/hour comparisons, not causal counterfactuals. Unobserved treatments and future uploads remain unknown.
4. Stable person IDs identify repeated observations. Clustered inference assumes independent people and estimates rates under per-call assignment, not lifetime person-randomized effects.
5. Startup persists/reuses an automatic identity per simulator URL and isolates observed resets/scenario changes. Explicit run IDs still require operator lifecycle control. The API has no world-instance token; a reset caught up beyond saved counters/time can remain indistinguishable.
6. PostgreSQL commits are durable. Process exits are demonstrated; database failover/disk loss is not. Ambiguous paid results require review because the API lacks idempotency/retrieval.
7. Impact is affected share of known active leads, not predicted lift. If validation policy is absent, use an explicit 0.97 safety threshold.
8. The measured application budget includes controller and PostgreSQL. The simulator is external; Docker Desktop quotas are not dedicated bare-metal resources. Profiling overhead is included where labelled.
9. Name and actual hours are [TODO], to be filled honestly by the author. AI assistance was used; the author must be able to defend the implementation and decisions.

## 2. Scope decisions

| # | Capability | Built / Partial / Cut | Why | What it would take to finish |
|---|---|---|---|---|
| C1 | Restartable load ingestion | Built | Stream/COPY, transactional counters and cursors, measured full load | Retention and continuous-arrival SLOs |
| C2 | Lead joins/shared cohorts | Built | Shared API cohort IDs and first-match/default rules | Automatic formation remains cut |
| C3 | History bootstrap | Built | Separate history/live evidence before decisions | Production refresh/backfill scheduling |
| C4 | Call-time optimisation | Cut | Sparse personal evidence and business constraints | Cohort-first time experiments |
| C5 | Caller-ID health | Partial | Matched peers/history, supported rotation | Exploration of unseen IDs |
| C6 | Welcome × voice | Partial | One prospective voice challenger | Welcome and interaction design/traffic |
| C7 | Promotion/decay/rollback | Built | 90/10 promotion, daily/48h checks, first/repeat populations | Public winner/decay episode remains unproven |
| C8 | Hallucination response | Built | Prior prompt first, n=500 validation, governed repair/verification | Faster calibrated detection and provider idempotency |
| C9 | Governance | Partial | Durable lifecycle, timing, conflicts, batching and bounded retries | General fresh-evidence retry and stricter client preferences |
| C10 | Proposal facts | Built | Exact diff, known reach, limited historical dry run | Remaining-attempt reach and causal predictions |
| C11 | Supervisor view | Partial | One concise CLI plus JSON/audit | UI, acknowledgement and external delivery |
| C12 | Audit | Built | Our events, immutable intent and append-only decisions | Access control, retention/export |
| C13 | Demonstrated recovery | Built | Five abrupt boundaries and fresh-checkout completion | Database/partition chaos testing |
| C14 | Loop health | Partial | Lag, timings, starts, requests/hour, credits and actionable alerts | External watchdog/page delivery |
| C15 | Fair resources | Partial | Tenant credit shares, durable paid-action order, incident slots | Share borrowing and tenant-wide attention budgets |

I finished the permission/evidence/recovery path before expanding optimisation. Explicit SQL and small modules make state inspectable without an ORM, agent framework, queue or vector store. PostgreSQL supplies transactional storage; changing engines alone does not remove bad queries. The measured decision path now reads typed counters and campaign/conclusion state, while raw events remain the audit source.

## 3. Stakeholders

Policies were checked through real `GET /workflows`; the captured response is [workflow policies](./reports/steps567_workflow_policies.json).

### 01 — Sales

Accepted clear outcome summaries and fewer requests. Declined blended KPIs, lunchtime winner selection, universal rollout and cross-client prompt transfer. The memo's claims are wrong: Kestrel allows only certain small automatic changes; Northwind KYC auto-apply is disabled.

**Reply I'd send:** We can show conclusion rate, pickup and engagement with the evidence behind each change. GET /workflows confirms Kestrel does not allow automatic prompt changes and Northwind KYC requires approval. We test a small group and decide at the planned checkpoint; the result stays within that workflow. I will show inconclusive and harmful outcomes as well as repairs. Would you trade broader summit coverage for a smaller demonstration with defensible evidence and permission? A lunchtime lead cannot justify a universal rollout.

### 02 — Northwind Compliance

Accepted approvals, validation, actual-variant traceability and signed operational latitude. Hours match the API: renewals 10–19, KYC 10–18. Named approval identity and a contractual 24-hour response SLA are not demonstrated; the API exposes IDs/status, not human names.

**Reply I'd send:** Northwind voice and script changes require approval. Script requests carry validation evidence; actual calls retain their version and variant. Caller-ID rotation uses signed operational policy. We can query why a config was live and which approval allowed it. The simulator gives an approval ID rather than a human name. Can we use that trace for the assignment demonstration while blocking production until named identity and audit-response ownership are connected? Validation checks safety; we also watch engagement after application.

### 03 — Platform / SRE

Accepted PostgreSQL, no new stateful service, measured limits, kill/restart proof and actionable health. No incorrect policy claim was found. Paid calls cannot be made exactly-once solely by a local client; ambiguity becomes a durable review hold.

**Reply I'd send:** The loop uses PostgreSQL and needs no Redis or queue. The real crash script exits without cleanup around ingestion and remote writes, restarts, and compares completed evidence and remote history. Status shows lag, pending work, tick cost, credit use and page/ticket actions. Load reporting includes bootstrap and profiling overhead rather than hiding them. Uncertain paid calls are held, not charged again. Production needs provider idempotency/result lookup and an external watchdog; the controller cannot reliably page about its own death.

### 04 — Kestrel Operations

Accepted preservation of supervisor edits, a concise view, compatible batching, explicit reversal summaries and real engagement checks. Two requests/day after 11:00 is a stricter preference than the API's four/24h and 10–19, not an inaccurate client statement. That preference and advance notification delivery remain unimplemented; status/proposals contain alerts only.

**Reply I'd send:** Your edits create new versions; old full-config requests cannot overwrite them. Status shows tests, pending work, incidents and changes. A prompt repair says when it reverses your edit and waits for approval. A safe script still needs live engagement checks. Your two-requests-after-11 preference is stricter than the API policy we received. This version does not enforce it or deliver advance notices outside the approval queue. Would you accept a limited assignment demonstration, then delay production rollout until those controls are connected?

### 05 — Product

Accepted separate KPIs, shared cohorts, actual exposure, honest proposal facts and workflow-only promotion. Expired requests are retired; fresh attempts require evidence and IDs. No factual contract conflict was found. Per-person timing is cut, and the supervisor surface is a CLI.

**Reply I'd send:** Detection, experiments and status use the same cohort IDs. Waiting for approval is not exposure. One voice challenger gets a 72-hour checkpoint, declared populations and a guardrail test. New winners retain 10% control, with matched daily and two-day monitoring; old declared plans keep their original rules. Impact means reach, not promised lift. Expired prompt repairs need fresh evidence and another candidate. I chose caller-ID health and an auditable CLI over per-person timing; welcome interactions and automatic cohort discovery remain outside this version.

### 06 — CTO

Accepted explainable outcomes, bounded spending, measurement and explicit cuts. No incorrect policy claim was found. Public_01/02 do not support a discovered voice-winner claim; supported repairs are the strongest result.

**Reply I'd send:** We can explain each repair and permission from our own store. Deterministic rules decide voice trials; inconclusive evidence stays inconclusive. The reports retain a harmful cleanup, slow detection, a database crash and a failed input comparison. We spend on prompt incidents only and try supported prior evidence before buying suggestions. I kept one process and PostgreSQL so the next engineer can inspect and restart it. Production work starts with identity, delivery, watchdogs, provider idempotency and calibrated detection power before broader optimisation.

## 4. Architecture

```text
Simulator HTTP -> streamed ingest -> PostgreSQL raw evidence + typed counters
                                          |
                               incidents / voice experiments
                                          |
                                durable intent + evidence
                                          |
                              governance / reconciliation
                                          |
                           approval or policy-permitted config API
                                          |
                                     observed calls
Read-only status/audit CLI <---------------+
```

[api.py](./controller/api.py) owns HTTP; [store.py](./controller/store.py) owns transactions and derived evidence; [metrics.py](./controller/metrics.py) and [statistics.py](./controller/statistics.py) own population decisions; [incidents.py](./controller/incidents.py) and [experiments.py](./controller/experiments.py) own lifecycles; [governance.py](./controller/governance.py) owns configuration writes.

A chunk atomically commits unseen events, lead joins, hourly/person counters, campaign/conclusion state, audit and its cursor. Old runs backfill derived evidence once transactionally. Restart reads state, discovers missing chunks, reconciles remote permissions/history, then resumes. A session lock allows one writer per run; read-only views remain available. Experiment counters and their time cursors also commit together.

## 5. The learning loop

**Cohorts/design.** Use the largest supported existing/default cohort with one incumbent, not new fragmented slices. Require 200 historical primary observations before planning. Split one voice challenger at 20% through governance. Start at actual authorised exposure; pinned old campaigns are excluded. Welcome interactions are cut. Finish once at 72 hours, without an extension until significance.

**Winner.** Person-clustered ratio uncertainty retains covariance for people appearing in both arms. Require planned samples, at least 100 contributing people/arm for both KPIs, positive primary lower bound, observed primary lift of eight points, and guardrail lower bound above the negative policy margin. Trial i spends `0.05/(i*(i+1))` per workflow. One challenger avoids unnecessary simultaneous-arm correction. Sparse/boundary cases remain inconclusive. Sequential testing defaults false and errors if enabled. This is asymptotic inference, not an exact platform-wide error guarantee.

Seeded correlated-null calibration: 2 full-procedure false winners/500 (0.4%; 95% Wilson interval 0.11–1.45%); primary-positive alone 18/500 (3.6%; interval 2.29–5.62%) at nominal alpha 0.025. Known-lift, covariance, guardrail, timing and lifecycle checks are in the focused tests; these simulations do not prove production power.

**Promotion/decay.** New plans promote 90/10 only in the measured cohort, storing reference lift, applied version and time. Old v1 plans keep 80/20 and their original rules. Daily matched winner/control windows track all/first/repeat exposure. Two adequately sampled days below half reference lift request rollback. Fixed non-overlapping 48-hour checkpoints can retire benefit whose lower bound is no longer positive. That is insufficient continued evidence, not proof of harm. Floors are 200 primary observations and 100 people/arm with defined uncertainty for both KPIs; sparse holdouts wait. Material primary/guardrail harm can stop separately under a declared spending budget. First/repeat strata are observational because earlier outcomes affect return calls.

**Caller/time/guardrails.** Call-time and person-level scheduling are cut. Caller alarms compare matched hours/cohorts against own history and supported peers. Every experiment measures pickup and engagement separately and requires guardrail non-inferiority for promotion. Incident verification is observational, labelled no detected material harm rather than proven non-inferiority. Rollback remains governed and can wait for permission/new campaigns. See [EXPERIMENTS.md](./docs/EXPERIMENTS.md).

## 6. Governance

```text
planned -> submitted -> pending -> approved -> applying -> applied
                \---- rejected / expired / lapsed / stale / blocked
fresh evidence + new decision ID -> linked new proposal
```

Persist immutable intent before HTTP. IDs hash run and stable decision identity. Reconcile remote history/approvals before writes, including lost responses and duplicate-ID 409s. Auto-apply requires enabled policy, allowed dimensions and each effective cohort's total-variation bound. Prompt changes always take approval. Do not split large shifts to evade permission.

Non-urgent requests wait for approver hours. Urgent requests still need TTL feasibility; apply before apply-by. Rolling counts include remote and uncertain local IDs, with one incident slot where possible. Batch compatible repairs without adopting unapproved experiment settings. Rejected/expired prompt repairs move to another candidate only with fresh alarm evidence and bounded budgets. Generic automatic experiment re-proposal is partial.

Affected leads are known nonconcluded leads in active campaign lifespans; future uploads are excluded and remaining attempts can be overestimated. Impact is affected/known-active, or zero when empty. Dry runs reweight supported historical rates and label missing/joint counterfactuals unknown. Supervisor edits interrupt epochs; cleanup preserves unrelated changes and escalates conflicts.

## 7. Incidents

Two consecutive completed-hour signals are required. Caller IDs need 60 current/200 historical dials, three points below own history and two below a supported peer, both Fisher p≤0.01. QA needs 30 connected, three flags, 200 historical connected and two points excess flags at p≤0.01. Fisher is an exact conditional comparison of binomial populations, retaining historical-rate uncertainty. Repeated people/windows mean it is not a whole-run 1% false-alarm guarantee. Prompt/cohort changes reset QA persistence; voice-only changes do not.

Attribute the latest observed prompt edit; validate the supported previous prompt first at n=500. Only then buy suggestions, filtering unavailable, tried and originally unsafe prompts. Validation is safety evidence, not engagement. The summary identifies a supervisor reversal, waits for approval and exposes a durable supervisor alert. Verify real post-apply populations and cohort guards; reopen or escalate failures. Provider ambiguity never causes a blind re-purchase.

New incidents have an 18-credit cap, a six-credit global reserve, initial tenant shares and one paid action/tick. Five-credit prior-prompt validation plus a three-credit suggestion and two further validations fits that cap. Old incidents retain their declared n=300/12-credit rules. Unused tenant shares are not borrowed.

Final public_02: two beneficial repairs, zero harmful changes, five credits and zero LLM calls. Bad prompt edit: D3 11:30; detector: D4 13:00; validated: 13:15; submitted: 13:30; applied: 15:00; verified by 19:00. **Onset-to-apply is 27h30m**, including 25h30m before qualifying persistence and two hours from detection to apply. Earlier positive hours were followed by nonqualifying hours; the stored windows show why. A rapid-response SLA is not demonstrated. See [rehearsal](./reports/REVIEW_REHEARSAL.md).

## 8. Scale

Final **profiled** run: **9,737,475 events**, **7,537.7 live events/sec**, **90.79 MiB peak controller RSS**, **1,943.207 seconds total**, **388.641 seconds/day including bootstrap**. Mean live tick is **2,759.615 ms**; the maximum advance-plus-decision bound is **25.434 seconds**. Live days take 191.478–358.727 seconds. **Cold start plus D0 is 13m40s**, exceeding ten minutes; the mean is not a tail/cold-start guarantee. Database tables/indexes/TOAST occupy about **8.69 GiB**, excluding WAL/temp files. Exact-time person counters have **3,240,000 rows**; the cohort/hour cube has **8,791 keys**. [LOAD.md](./reports/LOAD.md) includes the cProfile findings and [steps567_load.json](./reports/steps567_load.json) the raw summary. [MILESTONE5_LOAD.md](./reports/MILESTONE5_LOAD.md) preserves an earlier, different unprofiled version; do not claim a controlled speedup.

The application budget is controller 3 CPUs/6 GiB plus PostgreSQL 1 CPU/2 GiB; simulator initialization and post-run comparison are outside the timer, history bootstrap inside. Profile overhead is included when enabled. cProfile elapsed times include blocked I/O and are not backend CPU. Continuous arrivals while the controller falls behind are not simulated.

At 10×, include ingestion/WAL, decision inference and person-counter transfer. The cohort cube grows with distinct cohort keys, but exact-time person evidence can approach call count and leads grow with uploads. First reduce sufficient statistics/retention costs, then partition tenant/workflow ownership with atomic shared budgets. PostgreSQL is already used; moving to it is not a future scaling fix. A queue/vector store does not remove those costs. Ten-times capacity is unmeasured.

## 9. Reliability

[crash_test.py](./tests/crash_test.py) reuses the external verification harness. Each case starts a fresh world, exits 137 mid-ingest, after advance, after saved intent, after accepted POST, or after apply, then restarts. All five completed cases match their clean reference's evidence, typed counters, decisions and remote approvals/config history. Duplicate remote proposal IDs are rejected. Extra recovery audit transitions are allowed. [Matrix](./reports/steps567_crash_final.json); [fresh checkout](./reports/steps567_fresh_clone.json). The earlier suite passed 118 checks on Windows and Linux, including an interruption between a decay conclusion and restore intent. The [PR follow-up](./reports/PR1_FOLLOWUP.md) adds startup/approval/allocation checks: 137 pass on Linux and 136 on Windows, with one Linux-only skip. The measured profile predates that final checkpoint-ordering correction; its normal hot path is unchanged.

Reads retry bounded transport/5xx failures. Failed streams roll back the chunk. Mutations reconcile rather than blindly retry; stale/duplicate 409s, lapse 410s and credit 402s remain explicit. Paid unknown results require review. Database failover and every instruction-level crash are unproven.

Two failures remain visible: an earlier PostgreSQL backend segmentation fault whose cause was not isolated ([record](./reports/LOAD_ATTEMPT.md)), and a reference history event recorded as `ball` instead of `call` ([record](./reports/INPUT_ANOMALY.md)). The latter invalidated that comparison; new incoming unknown types now fail transactionally. Fresh reruns do not establish that arbitrary infrastructure corruption is fixed.

## 10. Audit & observability

`python -m controller status --run-id RUN` prints a concise view; `--json` includes full cohorts, outcomes, experiments, proposals, changes, incidents and ledger. Lag is against the last observed API state. Pages suggest action for stale ticks, impending approved expiry, unsafe prompt work and repeated starts without progress. Tickets cover low credit reserve, old non-safety incidents and ordinary blocked experiments. This is local alert visibility, not external delivery/watchdog integration.

Real command, already executed against our retained store:

```bash
export PGOPTIONS='-csearch_path=steps567_finalinc_clean_b96a70'
python -m controller audit --run-id steps567_finalinc --workflow ks_cancel \
  --at '2027-01-08T15:00:00+05:30' --version 10
```

It identifies supervisor version 6/P2, prior observed P1/version 5, validation val_00001 and approval apr_00007. Exact version selection disambiguates multiple changes at one timestamp. Version-10 complete hours show 1,600 dials, 286 connected, 154 engaged and five flags. That is descriptive exposure, not causal lift. Named human identity is unavailable. Three complete decision walkthroughs and executable queries are in [REVIEW_REHEARSAL.md](./reports/REVIEW_REHEARSAL.md).

## 11. Results

The following tables are pasted from the final grader reports. Deltas are relative to no-op baseline, not percentage points. Full outputs: [public_01](./reports/public_01.md), [public_02](./reports/public_02.md), and [public_03](./reports/public_03.md).

Public_01:

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.339 | +1.7% | 0.239 | +0.5% | 0.497 | +1.3% | 0% | 60 (47) |
| nw_kyc | 0.368 | +1.3% | 0.240 | -0.9% | 0.602 | +1.9% | 3% | 19 (21) |
| nw_renewal | 0.413 | -1.7% | 0.261 | -1.1% | 0.548 | +0.4% | 1% | 41 (42) |
| ALL | 0.370 | +0.3% | 0.247 | -0.4% | 0.535 | +1.1% | 1% | 120 (110) |

Public_02:

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.280 | +13.0% | 0.201 | +9.6% | 0.485 | +1.7% | 25% | 122 (330) |
| nw_kyc | 0.379 | +1.1% | 0.244 | +0.8% | 0.596 | +0.6% | 5% | 43 (31) |
| nw_renewal | 0.429 | +0.6% | 0.261 | -0.5% | 0.553 | +1.0% | 6% | 61 (55) |
| ALL | 0.351 | +4.9% | 0.230 | +3.6% | 0.534 | +0.8% | 13% | 226 (416) |

Public_03:

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.342 | +0.1% | 0.245 | +0.3% | 0.498 | -0.5% | 0% | 413 (408) |
| arav_kyc_1 | 0.358 | +1.1% | 0.213 | -0.7% | 0.602 | +1.1% | 5% | 355 (370) |
| arav_renewal_0 | 0.405 | +0.7% | 0.264 | -0.1% | 0.547 | +0.7% | 0% | 423 (440) |
| kest_cancel_2 | 0.338 | -0.1% | 0.244 | +0.5% | 0.495 | -0.8% | 0% | 398 (411) |
| kest_kyc_1 | 0.361 | +2.2% | 0.215 | +0.4% | 0.602 | +1.3% | 3% | 348 (339) |
| kest_renewal_0 | 0.403 | +0.8% | 0.263 | -0.1% | 0.545 | +0.5% | 0% | 452 (433) |
| nort_cancel_2 | 0.344 | +1.5% | 0.245 | +1.1% | 0.499 | +0.1% | 0% | 418 (393) |
| nort_kyc_1 | 0.355 | +0.3% | 0.213 | -0.2% | 0.601 | +0.9% | 3% | 353 (323) |
| nort_renewal_0 | 0.405 | +0.1% | 0.264 | +0.1% | 0.548 | +0.1% | 0% | 447 (411) |
| tide_cancel_2 | 0.339 | +0.1% | 0.245 | +0.3% | 0.496 | -0.6% | 0% | 396 (407) |
| tide_kyc_1 | 0.357 | +1.1% | 0.214 | -0.1% | 0.599 | +1.1% | 5% | 308 (356) |
| tide_renewal_0 | 0.402 | +0.2% | 0.264 | -0.0% | 0.544 | +0.2% | 0% | 408 (438) |
| ALL | 0.367 | +0.7% | 0.241 | +0.1% | 0.546 | +0.3% | 1% | 4719 (4729) |

Public_01 applies eight neutral, one beneficial and **one harmful** change: the KYC incumbent restoration removed a true small engagement benefit after an inconclusive primary/guardrail test. Do not describe that cleanup as superior treatment. Public_02 applies thirteen neutral and two beneficial changes, with **zero harmful** changes, no expiry/lapse/apply conflict, and five credits spent. The strongest benefit is incident repair. No public_01/02 voice candidate qualified for promotion. Public_03 applies sixteen neutral, four beneficial and two harmful changes; the harmful changes are again inconclusive KYC restorations. Ten trials are inconclusive and two unfinished; no public load winner is promoted. Synthetic tests demonstrate promotion/decay mechanics, not live winner lift. Single-seed aggregate differences are not causal estimates.

## 12. Trade-offs & rejected alternatives

| Option | Why considered | Why rejected / what instead |
|---|---|---|
| SQLite | Minimal persistence | PostgreSQL transactions/queries chosen; SQL work still measured |
| ORM/repository framework | Abstract storage | Explicit SQL exposes atomicity and recovery boundaries |
| RAG/vector database | Evidence retrieval | Exact populations, joins and templates fit SQL |
| LLM-selected winners | Flexible reasoning | Deterministic statistical rules; paid suggestions are hypotheses only |
| Redis/queue/workers | Throughput | One measured writer first; reduce query/retention cost before adding ownership coordination |
| Multiple arms/welcome interactions | Faster discovery | More comparisons and sample demands; one voice challenger |
| Sequential testing | Earlier promotion | Fixed checkpoints; reserved flag errors until a validated method exists |
| Automatic language cohorts/person schedules | Personalisation | Fragmentation, sparse evidence and business constraints |
| Web/notification service | Supervisor convenience | Concise CLI and approval queue now; production delivery remains unfinished |

## 13. Known weaknesses

- Conservative rules find no public_01/02 winner and can remove a true but unproven small benefit. Decay retirement can also stop a small positive effect whose holdout is too imprecise; it is not proof of harm.
- QA persistence remains slow in the measured incident. Cluster/delta inference is asymptotic; operational alarms, first/repeat strata and post-change guards are not causal or whole-platform guarantees.
- No welcome interactions, new cohorts, caller exploration or call-time optimisation. Rollback can wait for approvers/new campaigns.
- Paid uncertainty requires review. Tenant shares can strand credits; tenant-wide attention preferences are incomplete.
- Kestrel's stricter 11:00/two-request preference, external notification delivery, named human identity and external watchdog remain unimplemented.
- Person/time counters can grow with calls. Retention, database failover and continuous-arrival SLOs need production work.
- The backend crash and one-record input anomaly have unresolved origins. Runtime/test package snapshots are pinned; base image tags remain mutable. Indistinguishable world resets may evade detection.
- Profile/cold-start limits must be read with the measured results. Name/effort are [TODO]; external reviewer/form/deadline details remain [TODO].

## 14. If this went to production at Formi next month

1. Confirm signed policies and stricter client preferences; add named identity, notification delivery and acknowledgement before live rollout.
2. Add provider idempotency/result lookup, immutable world IDs, least-privilege access and tested backup/restore. Investigate the database/input anomalies with reproducible infrastructure evidence.
3. Run a shadow controller with continuous arrivals; add an external watchdog, backlog/decision SLOs and tested page/ticket ownership.
4. Prospectively calibrate detection power/delay, correlated people, rare harms, inconclusive cleanup costs and holdout retirement. Do not retune to a public grader's hidden truth.
5. Profile sufficient-statistic transfer, WAL and retention; partition/shard only where measured limits justify it, preserving per-workflow writes and shared budgets.
6. Put the existing queries behind a supervisor UI; add broader exploration only when traffic and attention budgets support it.
