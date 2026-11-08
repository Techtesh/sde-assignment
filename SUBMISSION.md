# Outcome-First Agent Loop — Submission

**Name:** Not supplied · **Date:** 2026-11-08 · **Hours actually spent (be honest):** Not tracked; not reconstructed from the assignment estimate · **Language / storage:** Python / PostgreSQL 17

## 0. TL;DR

One Python process and PostgreSQL manage ingestion, fixed-checkpoint voice tests, incident repair and governed changes.
Public_01 applies eight neutral changes; no public_01/02 voice candidate qualifies for promotion.
Public_02 repairs two incidents: Kestrel conclusion rate +15.5% relative, 97 hallucinated calls versus 330 baseline, six credits spent.
Five crash boundaries recover correctly; load averages 5m46s/day including bootstrap, while cold start plus D0 exceeds ten minutes.
Welcome experiments, call-time optimisation, new language cohorts, cross-client transfer and a web UI are cut.

## 1. Assumptions

1. The HTTP contract and returned workflow policy are authoritative. Memos do not grant permission. The controller never imports simulator code, parses scenario truth, or reads simulator run files.
2. All work uses Asia/Kolkata simulated time. Calling windows, cadence and capacity belong to the business. A loop advances 15 simulated minutes after committed evidence and decisions.
3. Historical cohort/hour comparisons are useful operational references, not randomized causal estimates. An unseen variant has no honest historical counterfactual.
4. Stable person IDs identify repeated observations. Different people are treated as independent for cluster-based inference. Assignment is prospective per call, rather than a person-level lifetime treatment.
5. Each new simulator world receives a new run ID; restart uses the same ID and database. The API has no unique world-instance token, so a perfectly matching reset cannot always be detected.
6. PostgreSQL commits are durable. This demonstration kills the controller, not the database or its disk. One writer owns each run; read-only views remain available concurrently.
7. An ambiguous paid API response may have spent credits. Without remote idempotency/retrieval, safely holding it for review is more honest than promising exactly-once payment.
8. Impact means affected share of known active leads, not expected lift. Unknown future uploads and unknown treatment effects remain unknown.
9. Linux controller and database limits total four CPUs/eight GiB; the simulator is an external HTTP service. Cgroup limits on Docker Desktop are not dedicated physical hardware.
10. The author's full name and actual effort were not provided. The time budget in the work plan is a plan, not an hours-worked claim. AI assistance was used; the implementer must be able to defend the code and decisions.

## 2. Scope decisions

| # | Capability | Built / Partial / Cut | Why | What it would take to finish |
|---|---|---|---|---|
| C1 | Restartable ingestion at load scale | Built | Stream chunks, COPY in transactions, deduplicate event IDs; measured separately below | Production retention and continuous-arrival benchmarking |
| C2 | Lead joins and shared cohorts | Built | Persist lead features; use API cohort IDs and first-match/default semantics throughout | New cohort discovery is deliberately absent |
| C3 | History bootstrap | Built | Import before deciding; separate history/live counters and cursors | Retention and freshness policy in production |
| C4 | Call-time optimisation | Cut | Sparse person histories and interaction costs; business calling constraints remain intact | A cohort-first experiment with time/capacity constraints |
| C5 | Caller-ID health | Partial | Detect against peers/history and rotate with permission | Dedicated safe exploration of unobserved IDs |
| C6 | Welcome × voice experiments | Partial | One voice challenger per workflow/cohort keeps inference and ownership tractable | Welcome experiments, factorial interaction design, more traffic |
| C7 | Promotion, decay, rollback | Built | Governed 80/20 promotion and fresh daily monitoring; synthetic lifecycle checks | Public runs do not establish a promoted-winner decay episode |
| C8 | Hallucination response | Built | Detect, suggest, validate n=300, propose, monitor real safety and engagement | Broader calibration and provider idempotency/retrieval |
| C9 | Governance | Partial | Durable lifecycle, timing, fatigue, conflicts, reconciliation, explicit re-proposal | More general automatic fresh-evidence retry; stricter client notification preferences |
| C10 | Honest proposal facts | Built | Exact diff, known affected leads, reach score, limited historical dry run | Better remaining-attempt reach and causal projections |
| C11 | Consolidated supervisor view | Partial | One read-only CLI JSON view, plus an audit command | Human-facing UI, acknowledgement and notification delivery |
| C12 | Queryable audit | Built | Events, immutable intent and append-only transitions in our database | Production access control, retention and export |
| C13 | Demonstrated process recovery | Built | Five abrupt exit boundaries compared with a clean completed run | Database failover and partition/chaos testing |
| C14 | Loop observability | Partial | Persist timings, checkpoints, backlog, proposal/transition counts and credit ledger | External watchdog, alert delivery and SLO dashboards |
| C15 | Fair credits and attention | Partial | Equal initial tenant credit shares, durable paid-action ordering, reserved incident request slots | Borrowing unused shares and cross-workflow tenant attention budgets |

The choice was to finish the permission/evidence/recovery path before expanding optimisation. Small explicit modules and SQL keep the state visible. A new service, vector database or generic agent framework would add operations without solving this assignment's decisions. PostgreSQL supports durable transactions and queryable populations; changing database engines alone does not prove scale.

## 3. Stakeholders

### 01 — Sales

Accepted a simple client outcome summary and fewer, batched requests. Declined a blended KPI, lunchtime winner selection, universal rollout and cross-client prompt transfer. The memo is wrong about Kestrel auto-apply covering everything and Northwind KYC allowing auto-apply: Kestrel's allowed dimensions exclude prompts/cohort changes; KYC auto-apply is disabled.

**Reply I'd send:** We can show business conclusion rate, pickup and engagement together, with the evidence behind each change. We cannot blend pickup and engagement or call a lunchtime lead a winner. Kestrel allows some small automatic changes; prompts still need permission. Northwind KYC requires approval. We test one voice on a small group, decide at the planned checkpoint and keep the result within that workflow. I'll show the measured results, including cases where we did not have enough evidence.

### 02 — Northwind Compliance

Accepted approvals for customer-facing changes, prompt validation, separate operational permissions and traceable actual variants. Approver hours match the API: renewals 10–19, KYC 10–18. The named-human requirement cannot be fully met through this API: it exposes approval IDs/status, not human identity. An operational audit query is built; a contractual 24-hour response SLA is not demonstrated.

**Reply I'd send:** Voice and script changes on Northwind go through approval. Script requests include validation evidence, and actual calls retain their variant and config version. Caller-ID changes use only the signed operational policy. Your hours are respected. We can trace why a config was live and which approval allowed it. The simulator gives us an approval ID, not the approver's name; production needs that identity attached before we claim to meet the named-human requirement. Validation checks safety; we also watch engagement after application.

### 03 — Platform / SRE

Accepted PostgreSQL, no additional stateful infrastructure, restart evidence, actionable health and a measured load run. Redis is unnecessary for a single writer. No incorrect contract claim was found. Pushback: paid endpoints cannot be made exactly-once locally without server support; ambiguity becomes a durable review hold.

**Reply I'd send:** The loop uses the existing PostgreSQL pattern and needs no Redis or queue. The recovery harness exits without cleanup during ingestion and around remote writes, then compares the completed run with a clean one. Status shows the last tick, backlog, pending work and credit ledger without taking the writer lock. Load results include bootstrap and stage costs under explicit resource limits. For an uncertain paid call we keep the intent and stop retrying it; production needs a provider lookup or idempotency key to recover that result automatically.

### 04 — Kestrel Operations

Accepted preservation of supervisor edits, one consolidated view, batched compatible repairs and real engagement checks after safe-script validation. The request for two proposals/day after 11:00 is a stricter preference than the signed API policy: four requests/24h and 10–19. The implementation follows API policy and reserves incident capacity; it does **not** enforce the additional preference or deliver pre-change notifications. Those are explicitly unfinished product work.

**Reply I'd send:** Your edits create a new config version; experiments stop and old proposals cannot overwrite it. One status command shows tests, pending approvals, incidents and recent changes. A safe script still has to keep people engaged, so validation is followed by live checks. Your two-requests-after-11 preference is stricter than the API policy we received. This version does not yet enforce that preference or send a notice before each live change. Those need explicit settings and delivery before a production rollout to your team.

### 05 — Product

Accepted separate KPI definitions, one cohort ID, prospective observed exposure, honest proposal facts and workflow-only promotion. Expiry retires the old request; new attempts need fresh IDs/evidence. No factual contradiction with the contract was found, but all requested P0s do not fit. Per-person timing is cut; the consolidated view is a CLI.

**Reply I'd send:** Pickup and engagement stay separate everywhere. Detection, experiments and the view use the same cohort IDs. An arm only starts when calls actually use its approved version; waiting for permission is not exposure. We use one voice challenger, a 72-hour checkpoint and explicit sample/guardrail requirements. Expired requests are retired, not recycled. The impact score means reach, with unsupported dry runs labelled unknown. I chose caller-ID health and an auditable CLI view over per-person timing. Welcome interactions and new cohort discovery remain outside this version.

### 06 — CTO

Accepted explainable outcomes, spending only on actionable incidents, measured compute, clear cuts and operating instructions. No incorrect policy claim was found in this memo. The public_01/02 experiments do not justify a self-improvement marketing claim: none qualified for promotion under the predeclared rules.

**Reply I'd send:** The strongest result is repairing supported incidents with permission and recorded evidence. Voice trials use deterministic statistical rules; we do not claim a winner when the sample is inconclusive. The implementation spends credits only on prompt incidents and keeps a reserve. The submission includes load and restart evidence, harmful historical outcomes, the cuts and what would break at ten times the traffic. I kept one process and PostgreSQL so the next engineer can inspect the state and recover it. Production work starts with identity, notifications, monitoring and broader calibration.

## 4. Architecture

```text
Simulator HTTP -> API client -> streamed ingest -> PostgreSQL
                                           |       events/leads/hourly counters
                                           |       workflow/config snapshots
                                           v
                          incident rules + fixed-checkpoint experiments
                                           |
                                durable intent / evidence
                                           |
                                governance / reconciliation
                                           |
                      approval API or policy-permitted config API
                                           |
                                    observed calls

Read-only status/audit CLI <---------------- PostgreSQL
```

[api.py](./controller/api.py) owns HTTP/retry rules; [store.py](./controller/store.py) owns transactions/queries; [metrics.py](./controller/metrics.py) and [statistics.py](./controller/statistics.py) make population decisions; [incidents.py](./controller/incidents.py) and [experiments.py](./controller/experiments.py) own their lifecycles; [governance.py](./controller/governance.py) owns every configuration write. [observability.py](./controller/observability.py) reads the same state without acquiring the writer lock.

On restart, read simulator state, reject a backward/reset world, restore snapshots, discover missing history/live chunks, reconcile remote approvals/config history, then resume decisions. A session advisory lock prevents two writers for one run. One chunk commits raw events, lead joins, counters, audit and its checkpoint together. Experiment person counters and their time cursor also commit together. No queue, ORM, vector store or LLM-driven decision layer is needed.

## 5. The learning loop

**Cohorts.** Reuse existing ordered cohorts/default; do not create fragmented language slices. Pick the largest historically supported cohort whose voice has one incumbent. Require at least 200 historical primary-denominator observations before planning; final inference requires at least 100 contributing people per arm for each KPI, plus the planned primary sample. A large cohort cannot supply missing evidence for an untested cohort. Lead features are retained for joins/audit, not treated as automatic permission to split further.

**Experiment design.** Give one challenger 20%, with governance before exposure. Voice is the only experimental dimension; welcome × voice interactions are not estimated. A context change or unrelated config epoch interrupts the test. Campaign-pinned old-version calls do not enter the new epoch. Trials start at first observed authorized exposure and finish exactly 72 hours later; starting a test with less than 72 hours left is avoided.

**Deciding a winner.** Use person-clustered delta-method uncertainty for ratios, retaining covariance when the same person contributes to both arms. Require the planned sample, positive primary lower bound, observed lift at least eight percentage points, and guardrail lower bound above the negative policy margin. Boundary/zero-variance/sparse cases are inconclusive. Working sample targets use historical rate and 80% power; they are not a clustered-power guarantee. One challenger avoids simultaneous-arm correction. Across trial i, spend `0.05/(i*(i+1))` per workflow; this sums to 0.05. There is one final winner look, never repeated extension until significance. Sequential testing defaults false and explicitly errors if enabled.

Seeded calibration uses 500 replications with 600 people/arm and four perfectly correlated calls/person. The complete procedure declares 2 false winners/500 (0.4%; 95% Wilson interval 0.11–1.45%). The primary positive test alone declares 18/500 (3.6%; interval 2.29–5.62%) at nominal alpha 0.025. These finite simulations support scrutiny, not a proven platform-wide 5% guarantee. Known-lift, shared-person covariance, sparse populations and guardrail failures are tested in [test_experiment_statistics.py](./tests/test_experiment_statistics.py) and [test_experiments.py](./tests/test_experiments.py).

**Decay and rollback.** A qualified winner is proposed at 80% with 20% concurrent incumbent control. Hourly population safety checks can stop harm but cannot declare an early winner. Fresh 24-hour post-promotion windows test primary degradation of at least two points or guardrail harm, with a separate declared spending schedule. Governed rollback can take an approver window; campaign pinning can delay actual exposure changes. Low-volume decay can remain inconclusive. Public runs did not promote a winner; promotion/decay paths are exercised with synthetic HTTP and real PostgreSQL.

**Call time and caller ID.** Call-time changes and per-person schedules are cut. Caller health compares matching cohort/hour exposure to its own history and supported current peers. Rotate only the affected cohort through governance; preserve other explicit/inherited settings. There is no exploration policy for unobserved caller IDs.

**Guardrail KPI.** Every trial evaluates both ratios. Non-inferiority is required for promotion, not merely a nonsignificant harm test. Separate spending controls scheduled emergency-stop comparisons. Incident post-change guards are conservative observational pre/post checks adjusted by historical clock-hour ratios; they establish no detected material harm, not formal non-inferiority.

See [EXPERIMENTS.md](./docs/EXPERIMENTS.md) for rules and assumptions. The user-authored WIP from line 138 of [WorkPlan.md](./WorkPlan.md) is preserved; its proposed 90/10 holdout and revised decay/validation rules are not implemented here.

## 6. Governance

```text
planned -> submitted -> pending -> approved -> applying -> applied
              |           |           |
              +-- rejected / expired / lapsed / stale / blocked

auto: planned -> submitted -> applied
fresh evidence + fresh decision ID -> new proposal linked to its parent
```

Persist the exact immutable body and governing policy before network I/O. IDs hash run ID and a stable decision ID. Reusing a decision ID for different intent fails. Every tick checks remote config history/approvals before writing; an accepted request or applied config can be recovered after a lost response. Duplicate-ID 409 means reconcile, not assume success.

Non-urgent requests wait for approver hours; urgent ones can be submitted outside hours only when TTL survives the next available window plus maximum latency. Check rolling 24-hour request counts using remote and uncertain local IDs. Leave one slot for incidents where the policy permits. Apply approved work in the same tick before `apply_by`. Batch compatible urgent caller/prompt repairs; do not import a pending experiment's unapproved voice change into an urgent prompt repair.

Auto-apply requires enabled policy, allowed changed dimensions and per-effective-cohort total-variation shifts below the signed bound. Never split a large change into repeated small changes to bypass permission. Existing mixtures are not overwritten to create experiments, and new writes stop when the scenario finishes.

`affected_leads` counts known nonconcluded leads in active campaign lifespans whose effective settings change. It can overestimate leads with no attempts left and excludes future uploads. `impact_score = affected/known_active`, or zero when empty. Dry runs reweight observed historical rates only where supported; joint/unseen counterfactuals remain unknown. This is reach plus observational evidence, not a promised uplift ranking.

A supervisor edit invalidates stale full configs and interrupts the experiment epoch. Voice cleanup preserves unrelated edits; a conflicting edit to the tested voice is retained and escalated. Expiry/rejection/lapse never counts as exposure or permission. Explicit re-proposal re-reads the base and recomputes facts. Incident retry is bounded and requires a fresh current signal; generic automatic statistical re-proposal is not implemented.

## 7. Incidents

Use two consecutive completed-hour signals in one config epoch. Caller-ID alarms need 60 current dials, 200 historical dials, a three-point drop from own history and two-point drop from a supported peer; both one-sided Fisher p-values must be at most 0.01. QA alarms need 30 connected calls, at least three flags, 200 historical connected calls, two points excess flags and Fisher p≤0.01. A single call cannot trigger a repair. Repeated testing and repeated people mean these are not whole-run 1% false-alarm guarantees. Healthy seeded populations are covered by regression tests; broad production calibration remains.

Caller repair shifts the bad ID's weight to an observed supported peer in the measured cohort. Prompt repair asks for suggestions, then considers observed historical alternatives and available suggestions deterministically. Validate candidates at n=300 against the workflow safety threshold. A passing validation is attached to the governed proposal; it is not engagement evidence. After application, skip partial hours, require at least 200 dials/60 connected calls, check population recovery and cohort guardrails. A supported failure tries the next candidate within budget; never roll back to a prompt already known to hallucinate merely to regain engagement.

Credit policy: reserve six globally, cap twelve per incident, divide initial spendable credits equally across tenants, and allow one new paid call per tick in durable fair order. Suggestion costs three; n=300 validation costs three. Save request intent before payment and successful response before advancing the phase. Unknown results are charged against local quota and held for review. Unused tenant shares are not borrowed.

The final public_02 timeline, measured spend and recovery evidence are recorded in [DELIVERY.md](./reports/DELIVERY.md). Earlier stage-four evidence is retained in [EXPERIMENTS.md](./reports/EXPERIMENTS.md); it used six credits and repaired the bad prompt in five simulated hours, including detection and approval. Final figures below supersede earlier trials where results differ.

## 8. Scale

See [LOAD.md](./reports/LOAD.md) and machine-readable [load_public03.json](./reports/load_public03.json) for the complete five-day public_03 run: bootstrap versus live throughput, stage totals, decision-lag bound, controller peak RSS, database footprint and wall time/day.

Measured: **9,737,478 events**, including 4,200,099 live events; **11,747.2 live events/sec**; **38.283 seconds maximum advance-plus-decision bound**; **101.36 MiB controller peak RSS**; **1,729.883 seconds total**, or **345.977 seconds/day including bootstrap**. Live days range from 159.278 to 314.501 seconds. Bootstrap plus initial decisions takes 539.334 seconds; **cold start plus D0 is about 11m47s**, exceeding ten minutes despite the passing full-run average. This is an explicit limitation. Tables/indexes/TOAST occupy about 7.31 GiB, excluding WAL/temp storage; person/arm counters contain 943,089 rows.

The first attempt failed after history committed: PostgreSQL 17.11 reported a backend segmentation fault during proposal reach calculation. Repeating the query after recovery did not reproduce it. [LOAD_ATTEMPT.md](./reports/LOAD_ATTEMPT.md) retains the failure and plan. The rerun removes unnecessary chunk validation/sorting and disables per-session JIT compilation after measuring its overhead; neither change is claimed to identify the server crash's root cause.

The application resource budget is split into controller 3 CPUs/6 GiB and PostgreSQL 1 CPU/2 GiB. The simulator is external. Image/dependency setup, simulator initialization and post-run verification are outside the timed controller run; history bootstrap is inside. This measures a synchronous closed-loop simulator, not arrivals continuing while the controller falls behind.

At ten times traffic, one PostgreSQL writer's JSONB validation/index/aggregation work and person-counter queries are the first suspects; raw evidence retention also grows linearly. Measure query plans and WAL/disk pressure before partitioning. Next, partition retained events by run/time and shard ownership by tenant/workflow, keeping one writer and one proposal stream per workflow. Stable person clusters and shared tenant credit/attention budgets need coordination across shards. Do not put calls through a vector database or add a queue merely to rename the bottleneck. Ten-times capacity is a projection, not a measured claim.

In the live phase, decisions consume 763.906 seconds versus 357.540 seconds of ingestion. Prioritise the decision queries/person-counter transfer and inference, alongside ingestion/WAL. At unchanged throughput, 10× ingestion alone projects to about 715 seconds/day, already over the ten-minute budget before decisions. The measured run therefore supports the stated envelope, not 10× under the same budget.

## 9. Reliability

[verify_delivery.py](./scripts/verify_delivery.py) launches fresh identical worlds, runs a clean controller, then forces exit 137 mid-COPY, after advance, after durable intent, after accepted approval submission, and after remote config application. Each restart completes and is compared with the clean world. [crash_recovery.json](./reports/crash_recovery.json) records the run/schema, timing and evidence signatures. The harness checks raw event fingerprints, checkpoints, counters, proposals, experiments/person counters, incidents, config-change audit, remote approvals and history. Remote proposal IDs must occur once per submission/application. Extra recovery audit transitions are retained rather than erased to make logs identical.

That five-point matrix uses `18e3e82`. After the ingestion optimization, a clean checkout of `7c20533` also completes a mid-COPY exit/restart and matches the original clean reference exactly; [crash_recovery_final.json](./reports/crash_recovery_final.json) records it. The final focused suite passes **100 tests on Linux/Python 3.12.16 with real PostgreSQL**. Network-governance code did not change in the optimization; its earlier real fault evidence is kept with its actual version.

Uncommitted chunks roll back; committed chunks/cursors do not replay into counters. An advance response lost after the world moved is handled by state discovery at restart. An accepted approval/config write with a missing local acknowledgement is discovered remotely before another write. Approval state and immutable intent survive. Proposal IDs make one logical write recognizable across attempts; new justified attempts receive new IDs.

Reads retry transport/5xx at most three times. Failed streams roll back the chunk for rediscovery. Mutations are not blindly retried. Stale-base 409 becomes stale; duplicate-ID 409 reconciles; apply 410 becomes lapsed; other 4xx/402 become explicit blocked/review outcomes. Network/5xx on governed writes retains uncertainty and stops execution for restart. Paid uncertainty cannot be fully recovered automatically with this API and becomes a review hold. Database loss, failover, network partitions and every possible instruction-level crash are not demonstrated.

## 10. Audit & observability

The consolidated view is `python -m controller status --run-id <run>`. It reads shared cohorts, recent per-cohort metrics, experiments, pending proposals, changes, incidents, credit spending, latest tick/stage costs, event backlog against last observed API state, and decisions/hour from our database. It works alongside the writer and has no simulator side effects.

The audit command is:

```bash
python -m controller audit --run-id delivery02 --workflow ks_cancel \
  --at '2027-01-07T18:30:00+05:30'
```

Set `PGOPTIONS` to the retained verification schema recorded in [delivery_public02.json](./reports/delivery_public02.json). [DELIVERY.md](./reports/DELIVERY.md) contains the real command result, approval ID, rationale, applied version and observed next-window counts. The command uses our events/proposals/approval audit and hourly counters; it does not consult simulator logs. Named human identity is unavailable through the contract and is not invented.

Status includes suggested actionable alerts, not an external paging service. Page for an unsafe prompt needing intervention, sustained ingestion/loop failure, or missed approved safety work. Ticket low volume, inconclusive tests, ordinary rejection and non-safety cleanup conflicts. A production external watchdog is necessary to detect a dead process. See [OPERATIONS.md](./docs/OPERATIONS.md).

## 11. Results

Final reports: [public_01.md](./reports/public_01.md), [public_02.md](./reports/public_02.md). Deltas are relative changes against the no-op baseline, not percentage-point changes. Earlier step reports remain historical evidence; they are not silently replaced with improved outcomes.

Public_01:

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.335 | +0.6% | 0.240 | +0.6% | 0.490 | -0.1% | 0% | 51 (47) |
| nw_kyc | 0.369 | +1.6% | 0.245 | +1.1% | 0.592 | +0.3% | 0% | 36 (21) |
| nw_renewal | 0.430 | +2.5% | 0.264 | +0.2% | 0.557 | +2.1% | 0% | 47 (42) |
| ALL | 0.374 | +1.5% | 0.249 | +0.5% | 0.534 | +0.8% | 0% | 134 (110) |

Public_02:

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.286 | +15.5% | 0.202 | +9.6% | 0.494 | +3.7% | 28% | 97 (330) |
| nw_kyc | 0.381 | +1.6% | 0.243 | +0.6% | 0.599 | +1.2% | 4% | 26 (31) |
| nw_renewal | 0.423 | -0.7% | 0.258 | -1.6% | 0.553 | +0.9% | 6% | 54 (55) |
| ALL | 0.352 | +5.3% | 0.229 | +3.1% | 0.539 | +1.6% | 15% | 177 (416) |

Public_01 applies eight neutral changes; one rejected trial never becomes exposure. Public_02 applies eleven neutral changes and two beneficial incident repairs, with zero harmful changes. Both finish without expiry, lapse or apply conflict. Public_02 uses six credits, repairs the prompt in seven simulated hours, and resolves both incidents in our own store. Most of the defensible benefit is Kestrel incident recovery. Small whole-workflow differences elsewhere are single-seed observations, not evidence that a voice won. Public_01's higher QA-call count deserves calibration work even though no graded harmful change was applied; a neutral grade is not a blanket safety claim.

No public_01/02 voice trial qualified for promotion under the declared rules. The earlier stage-four public_01 run graded one incumbent restoration harmful: the trial had a real but unproven small lift, and the planned inconclusive cleanup removed it. This is an exploration/decision cost, not a statistical winner or something to omit because the final run differs. Reducing the eight-point target or changing cleanup policy needs a prospective design and fresh evidence; tuning to hidden grading truth would be invalid.

## 12. Trade-offs & rejected alternatives

| Option | Why considered | Why rejected / what instead |
|---|---|---|
| SQLite | Minimal local persistence | PostgreSQL chosen for explicit concurrent-query/durability needs; actual SQL work still measured |
| ORM/repository framework | Abstract database access | Explicit SQL and transactions make recovery boundaries inspectable |
| RAG/vector store | Retrieve history and explanations | Structured counts, exact joins and templated rationale need SQL; semantic search does not decide rates/permission |
| General agent/LLM controller | Flexible reasoning | Deterministic rules select decisions; paid suggestions are narrow hypotheses |
| Redis/queue/workers | Buffer and scale | One measured writer is simpler; add workflow ownership boundaries when measurements require it |
| Multiple challengers/dimensions | Faster discovery | More comparisons, interactions and sample demands; one voice challenger first |
| Sequential winner checks | Earlier promotion | Fixed checkpoint chosen; reserved flag rejects activation until a validated evaluator exists |
| Automatic cohort discovery | Personalisation | Reuse supported cohorts to avoid fragmentation and weak guardrails |
| Per-person call time | Summit feature | Too little independent data and business-window complexity for this slice |
| UI/notification service | Supervisor convenience | One CLI view now; identity and notification delivery are unfinished production work |

## 13. Known weaknesses

- Conservative effect/sample rules found no public winners. The demonstration proves mechanics and supported incident repair, not broad autonomous optimisation.
- Cluster/delta inference is asymptotic and assumes independent people; calibration is finite and not a platform-wide guarantee. Incident alarms and post-change comparisons remain observational.
- No welcome interactions, new cohort discovery, caller exploration or call-time optimisation. Existing client-owned mixtures may be skipped.
- Safety rollback waits for governance and possibly new campaigns. Low-volume effects and decay can remain inconclusive.
- Uncertain paid results require review. Equal tenant shares can strand credits. Cross-workflow tenant attention preferences are incomplete.
- Kestrel's stricter 11:00/two-request preference, advance notification delivery and named human identity are not implemented.
- The status view reflects the last observed API state; no external watchdog or delivery integration exists. Raw JSON is less convenient than a supervisor UI.
- Raw JSONB retention has no production deletion/partition policy. Single database/session failure halts the loop. A reset with matching metadata may evade detection without a unique world ID.
- The first load attempt exposed an unresolved PostgreSQL backend segmentation fault. A completed rerun is evidence of that run, not proof that the server defect is fixed; production needs a core dump/reproducer and database investigation.
- Load and recovery conclusions apply to the measured setup and cases, not ten-times traffic, disk failure or all hidden scenarios. Dependencies use the assignment's version ranges rather than a production lock file.
- Cold start plus the first live day exceeds the ten-minute target (about 11m47s); only the overall average and individual live-day totals meet it. This synchronous simulator also pauses arrivals while the controller works.
- The user's WIP changes remain deliberately untouched. Name/effort fields require the author's factual input.

## 14. If this went to production at Formi next month

1. Confirm each client's signed policy and stricter operating preferences. Add named approver identity, pre-change notifications and acknowledgement. Keep the same governance boundary.
2. Add provider idempotency/result lookup for paid calls, immutable world IDs, database backups/restore drills, least-privilege credentials and audit access controls.
3. Run a shadow controller on continuously arriving traffic; add an external heartbeat/watchdog, backlog/decision SLOs and tested page/ticket delivery with clear ownership.
4. Calibrate detector and clustered-inference behavior across traffic volumes, repeated-person patterns, rare harms and hidden-like policy mixes. Review actual harmful/inconclusive cleanups before prospectively changing statistical rules.
5. Profile database plans/WAL/retention under sustained load and failure. Partition time-based evidence or shard tenant/workflow ownership only if measured limits justify it; preserve atomic per-workflow actions and fair shared budgets.
6. Ship a small supervisor interface backed by the existing read-only queries. Add welcome/cohort exploration only after capacity, guardrail evidence and client attention budgets support it.
