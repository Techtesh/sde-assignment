# Outcome-First Agent Loop — Submission

**Name:** Hitesh Jetwani · **Date:** 2026-11-08 · **Hours actually spent (be honest):** 12 hrs (basically 1 day in hackathon mode) · **Language / storage:** Python / PostgreSQL 17

**Reviewer:** Harshavardhan KR · **Deadline:** end of day Nov 9th.

## 0. TL;DR

I built one Python controller with PostgreSQL. It tests voices, repairs caller-ID and prompt
incidents, and records why each change was allowed.

Public_01 had ten changes: one beneficial and one harmful. Public_02 had two beneficial repairs, no
harmful changes, and spent five credits without an LLM call. Prompt repair still took 27h30m. No
voice trial qualified for promotion.

All five crash cases matched a clean run. The latest full focused suite passed 137 tests on Linux
and 136 on Windows, with one Linux-only skip. A fresh checkout also completed.

I cut welcome interactions, automatic cohort discovery, person-level timing, caller exploration,
cross-client transfer and the web/notification service.

## 1. Assumptions

1. Policies returned by HTTP are the permission contract. The controller never imports simulator code or reads scenario truth/run files. Baseline and grading commands are used outside it for verification.
2. Windows and checkpoints use simulated Asia/Kolkata time. The business owns cadence, capacity and calling windows. Reads leave time unchanged.
3. History supplies cohort/hour comparisons. It cannot establish what an unobserved treatment would have done, and future uploads are unknown.
4. Stable person IDs let the analysis group repeated calls. It assumes independent people and estimates per-call assignment effects.
5. Startup saves an identity per simulator URL and isolates detected resets/scenario changes. Explicit IDs must be managed by the operator. The API has no world token, so a reset caught up past saved time/counters may look like the old world.
6. PostgreSQL commits survive process exits. Database failover and disk loss were not tested. Uncertain paid requests need review because the API cannot retrieve or deduplicate their result.
7. Impact means the affected share of known active leads. With no validation policy threshold, the assumed safety threshold is 0.97.
8. The measured budget covers the controller and PostgreSQL. The simulator runs outside it. Docker quotas share host hardware; labelled profiled runs include profiler overhead.

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

I prioritized permission checks, audit and restart behavior before adding more optimisation.
Explicit SQL makes transactions and queries visible. PostgreSQL handles the stored state; slow
queries still need work. Decisions read counters and campaign/conclusion tables, while raw events
remain available for audit. An ORM, agent framework, queue and vector store were unnecessary for
this scope.

## 3. Stakeholders

The policy checks used real `GET /workflows` responses, saved in [workflow policies](./reports/steps567_workflow_policies.json).

### 01 — Sales

Sales asked for clear results with fewer approval requests. The demo can show that, but a lunchtime
lead cannot establish a winner or justify rollout across clients. The API also contradicts the
requested automatic permissions: Kestrel only allows certain small changes and Northwind KYC has
auto-apply disabled.

**Reply I'd send:** I can show conclusion rate, pickup and engagement, with the decision behind each
change. GET /workflows says Kestrel prompt edits need approval and Northwind KYC cannot auto-apply.
Tests start with a small group and stay within that workflow. The demo will include inconclusive and
harmful results. Can we reduce summit coverage to a smaller approved demo? There is not enough
evidence for a lunchtime winner or a universal rollout.

### 02 — Northwind Compliance

Northwind asks for approvals, validated scripts and traceability to the variant each lead heard.
Those are built. Calling hours match the API: renewals 10–19 and KYC 10–18. The API supplies
approval IDs/status rather than human names; a named approver and contractual 24-hour audit-response
SLA are still missing.

**Reply I'd send:** Northwind voice and script changes go through approval. Script proposals include
validation, and call records identify the version and variant heard. Caller-ID rotation follows the
signed operational policy. I can query the decision and approval ID for a live config, but the API
gives no human name. Can we use that trace for the demo and require named identity and an
audit-response owner before production? Live engagement is checked after a validated script applies.

### 03 — Platform / SRE

SRE asks for PostgreSQL, measured resource use, restart evidence and useful alerts. Those are
covered locally without another stateful service. The policy claims checked out. Exactly-once paid
calls require provider support; uncertain results stay on review hold.

**Reply I'd send:** The controller uses one process and PostgreSQL. The crash script kills it around
ingestion and remote writes, restarts it, then checks evidence and remote history. Status shows
backlog, pending work, tick cost, credits and suggested page/ticket actions. Load timing includes
bootstrap and profiling overhead. An uncertain paid request waits for review. Production still needs
provider result lookup/idempotency and an external watchdog that can notice when the controller is
dead.

### 04 — Kestrel Operations

Kestrel asks for supervisor edits to survive, fewer combined requests, reversal notices and
engagement checks. The implementation covers edits, batching, explicit reversal summaries and
monitoring. The two-requests/day-after-11:00 preference is stricter than the API's four/24h and
10–19 window. That preference and advance notification delivery are still missing; alerts are shown
in status/proposals.

**Reply I'd send:** Your edits create a new version, so stale requests cannot overwrite them. Status
shows tests, pending requests, incidents and changes. A prompt repair names the supervisor edit it
reverses and waits for approval; engagement is checked afterward. Your two-requests-after-11 rule is
stricter than the API policy. It is not enforced yet, and notices stay in the approval queue. Is a
limited demo acceptable while those two controls are finished before production?

### 05 — Product

Product asks for separate KPIs, consistent cohorts, measured exposure and useful proposal facts. The
controller uses the same cohort IDs across detection, experiments and status. Failed/expired work
needs fresh evidence and decision IDs. No policy conflict was found. Person-level timing is cut, and
the supervisor interface is a CLI.

**Reply I'd send:** Detection, tests and status share cohort IDs. Measurement starts when calls use
the approved version. One voice challenger gets a 72-hour checkpoint and a guardrail test. New
winners keep 10% control for daily/two-day checks; older plans keep their rules. Impact is reach.
Expired prompt repairs need fresh evidence and another candidate. I chose caller-ID health and a CLI
that can explain changes. Person-level timing, welcome interactions and automatic cohort discovery
are cut.

### 06 — CTO

The CTO asks for results that can be explained, spending limits and a clear scope. Incident repairs
are the strongest measured result. Public_01/02 produced no qualifying voice winner. No incorrect
policy claim was found.

**Reply I'd send:** Each repair can be traced to evidence and permission in PostgreSQL. The voice
rules are deterministic, and no public trial qualified for promotion. The reports include a harmful
cleanup, late detection, a database crash and a failed input comparison. Prompt incidents try
supported previous prompts before buying suggestions. I kept one process and PostgreSQL. Before
broader optimisation, I would finish identity, notifications, watchdogs and provider idempotency,
then calibrate detection against delay and false alarms.

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

[api.py](./controller/api.py) handles HTTP. [store.py](./controller/store.py) manages transactions and counters. [metrics.py](./controller/metrics.py) and [statistics.py](./controller/statistics.py)
evaluate populations. [incidents.py](./controller/incidents.py) and [experiments.py](./controller/experiments.py) manage their respective states. [governance.py](./controller/governance.py) submits
and applies configuration changes.

One transaction saves each chunk's new events, lead joins, hourly/person counters,
campaign/conclusion state, audit and checkpoint. Older runs build missing derived tables once.
Startup reads simulator state, imports outstanding chunks and reconciles approvals/history before
resuming. A session lock allows one writer per run. Views are read-only, and experiment counts
commit with their time cursors.

## 5. The learning loop

Use the largest supported existing/default cohort with one incumbent voice and 200 historical
primary observations. Propose a 20% challenger split through governance. The 72-hour clock starts
with actual authorized exposure; pinned old campaigns are excluded. There are no welcome
interactions and no extension until significance.

Evaluate rates with person-clustered uncertainty, keeping covariance when people appear in both
arms. Require planned samples, at least 100 contributing people/arm for both KPIs, a positive
primary lower bound, eight points of observed primary lift, and a guardrail lower bound above its
negative policy margin. Trial i uses `0.05/(i*(i+1))` per workflow. One challenger avoids simultaneous-arm
correction. Sparse or boundary cases stay inconclusive. Only fixed checkpoints are exposed;
sequential testing is unimplemented. The cluster approximation has no exact platform-wide error
guarantee.

In the seeded correlated-null simulation, the full rule selected 2 false winners/500 (0.4%; 95%
Wilson interval 0.11–1.45%). Primary positivity alone was 18/500 (3.6%; interval 2.29–5.62%) at
nominal alpha 0.025. Tests also cover known lift, covariance, guardrails, timing and state changes.
These checks do not measure production power.

New plans promote 90/10 in the tested cohort and save reference lift, version and time. Old v1 plans
keep 80/20 and their rules. Monitor matched daily all/first/repeat exposure. Two adequately sampled
days below half the reference lift request rollback. A fixed non-overlapping 48-hour check can
retire a winner whose primary lower bound is no longer positive. It requires 200 primary
observations, 100 people/arm and defined uncertainty for both KPIs; sparse holdouts wait. This can
retire an imprecise positive effect. Separate safety checks stop material harm. First/repeat
comparisons are observational because earlier outcomes affect who receives another call.

Caller alarms compare matched cohort/hours with the ID's own history and current peers. Every voice
test measures pickup and engagement separately and requires guardrail non-inferiority for promotion.
Incident verification reports no detected material harm; its observational comparison does not prove
non-inferiority. Rollback needs permission and may wait for new campaigns. Call-time and
person-level scheduling are cut. See [EXPERIMENTS.md](./docs/EXPERIMENTS.md).

## 6. Governance

```text
planned -> submitted -> pending -> approved -> applying -> applied
                \---- rejected / expired / lapsed / stale / blocked
fresh evidence + new decision ID -> linked new proposal
```

Save the exact intent before HTTP. Run and decision IDs determine a stable proposal ID. Check remote
history and approvals before writing, including after lost responses or duplicate-ID 409s.
Auto-apply needs enabled policy, permitted dimensions and an acceptable total-variation shift in
every effective cohort. Prompt changes always need approval. Large shifts cannot be split to evade
it.

Routine requests wait for approver hours. Urgent work still needs a feasible TTL, and approvals must
apply before their deadline. Rolling limits combine remote and uncertain local IDs, leaving an
incident slot when possible. Compatible repairs can be batched without adopting an unapproved
experiment change. Rejected/expired prompt candidates advance only with fresh alarm evidence and
within budget. Generic automatic experiment re-proposal is only partly implemented.

Reach counts known, nonconcluded leads in active campaign lifespans. Future uploads are excluded and
leads with no attempts left can be overcounted. Impact is affected/known-active, or zero for an
empty population. Dry runs reweight supported history; missing variants and joint counterfactuals
stay unknown. Supervisor edits interrupt experiments; cleanup keeps unrelated edits and reports
conflicts.

## 7. Incidents

Require two consecutive positive completed hours. Caller alarms need 60 current/200 historical
dials, a three-point drop against own history and two points against a supported peer, both at
Fisher p≤0.01. QA needs 30 connected calls, three flags, 200 historical connected calls and two
points of excess flags at p≤0.01. Fisher compares binomial counts while accounting for
historical-rate uncertainty. Repeated people/windows mean this is not a whole-run 1% false-alarm
guarantee. Prompt/cohort changes reset QA persistence; voice-only changes do not.

Record the latest observed prompt edit and try the supported previous prompt first at n=500. Buy
suggestions only after that fails or is denied, filtering unavailable, tried and originally unsafe
prompts. A passing safety validation still needs live engagement checks. The proposal names any
supervisor reversal and waits for approval. The supervisor alert is saved locally. After
application, verify real QA and per-cohort guardrails; reopen or escalate a failed repair. Uncertain
paid results are not bought again.

New incidents can spend 18 credits, subject to a six-credit global reserve, tenant shares and one
paid action/tick. That funds a five-credit previous-prompt validation, a three-credit suggestion and
two more validations. Existing incidents keep n=300/12-credit rules. Unused tenant shares are not
borrowed.

Final public_02 had two beneficial repairs, zero harmful changes, five credits spent and zero LLM
calls. The bad prompt arrived D3 11:30, was detected D4 13:00, validated at 13:15, submitted at
13:30, applied at 15:00 and verified by 19:00. Onset-to-apply was 27h30m: 25h30m before qualifying
persistence and two hours from detection to apply. Earlier positive windows were followed by
negative ones. That is too slow for a rapid-response SLA. For example, an hour at p=0.00034 was followed by p=0.055; another hour at p=0.010089 missed the 0.01 cutoff.

## 8. Scale

The profiled run processed 9,737,475 events at 7,537.7 live events/sec. Peak controller RSS was
90.79 MiB. Total wall time was 1,943.207 seconds, or 388.641 seconds/day including bootstrap. Mean
live tick time was 2,759.615 ms and the maximum advance-plus-decision bound was 25.434 seconds. Live
days took 191.478–358.727 seconds. Cold start plus D0 took 13m40s, over the ten-minute target.

Tables/indexes/TOAST used about 8.69 GiB, excluding WAL/temp files. Exact-time person counters had
3,240,000 rows; the cohort/hour cube had 8,791 keys. [LOAD.md](./reports/LOAD.md) has the profile analysis and
[steps567_load.json](./reports/steps567_load.json) the summary. Earlier unprofiled runs used different code; these numbers do not establish a controlled speedup.

Limits were controller 3 CPUs/6 GiB plus PostgreSQL 1 CPU/2 GiB. The timer includes history
bootstrap and excludes simulator initialization and post-run comparisons. Profiling overhead is
included. cProfile elapsed time includes blocked I/O, so it cannot identify backend CPU use. The
synchronous simulator does not test recovery from continuously arriving backlog.

At 10×, ingestion/WAL, person-counter transfer and inference all need work. The small cohort cube
does not bound exact-time person evidence, which can grow with calls. Leads grow with uploads. First
reduce query/retention cost, then partition ownership by tenant/workflow while keeping shared
budgets atomic. PostgreSQL is already in use. A queue or vector store would leave these measured
costs. Ten-times capacity has not been tested.

## 9. Reliability

[crash_test.py](./tests/crash_test.py) starts a fresh world per case, forces exit 137 mid-ingest, after advance, after intent,
after accepted POST or after apply, and restarts. All five cases matched their clean run's counters,
decisions and remote approvals/history. Duplicate remote proposal IDs fail the check; extra recovery
audit transitions are allowed. See the [matrix](./reports/steps567_crash_final.json), measured at `3d83779`. A fresh local checkout of that version also completed public_01 through the Bash launcher.

The earlier 118-check Windows/Linux suite covers interruption between a decay conclusion and
restore intent. Later startup, approval and allocation checks passed 137 on Linux and 136 on
Windows, with one Linux-only skip. CLI-focused checks passed 46 on Linux and 45 on Windows.
The [test sources](./tests/) contain those cases. The full profile predates the checkpoint-ordering
fix; it improves stop durability without changing the normal hot path.

Reads retry transport/5xx failures within bounds. Failed event streams roll back their chunk. Writes
check remote state before retrying. Stale/duplicate 409s, lapse 410s and credit 402s are recorded
separately. Unknown paid results need review. Database failover and crashes at every instruction
were not tested.

Two earlier failures remain unexplained. PostgreSQL 17.11 lost a backend to signal 11 during a
proposal-reach query after committing 5,537,379 history events. It recovered from WAL and Docker
reported `OOMKilled=false`. The same query later worked with JIT off (6.767s) and on (6.625s).
Disabling session JIT removes compilation cost; it is not a proven fix for that crash.

An earlier recovery comparison stored event 183742 as `ball` in the reference and `call` after
restart. Both had 297,040 events but different call/audit counters, so that comparison was invalid.
Unknown incoming types now roll back ingestion. The final matrix used fresh worlds and matched,
but does not explain the original mismatch.

## 10. Audit & observability

`python -m controller status --run-id RUN` prints a short view; `--json` adds cohorts, outcomes, plans, proposals, changes,
incidents and credits. Backlog is against the last observed API state. Page suggestions cover stale
ticks, approaching apply deadlines, prompt work needing intervention and repeated starts without
progress. Tickets cover credit reserve, older non-safety incidents and blocked experiments. Alerts
are local; external delivery and a watchdog are still missing.

The following command was checked against the saved incident run:

```bash
export PGOPTIONS='-csearch_path=steps567_finalinc_clean_b96a70'
python -m controller audit --run-id steps567_finalinc --workflow ks_cancel \
  --end-time '2027-01-08T15:00:00+05:30' --version 10
```

The answer links supervisor version 6/P2, previous P1/version 5, validation val_00001 and approval
apr_00007. `--version` selects the exact change when timestamps tie. Complete version-10 hours
contain 1,600 dials, 286 connected, 154 engaged and five flags. These describe post-change exposure;
the API gives no human approver name.


Two other audit decisions can be inspected with the same CLI:

```bash
export PGOPTIONS='-csearch_path=steps567_finalinc_clean_b96a70'
python -m controller audit --run-id steps567_finalinc --workflow ks_cancel \
  --end-time '2027-01-06T14:00:00+05:30' --version 3

export PGOPTIONS='-csearch_path=steps567_finaldev_clean_67f3af'
python -m controller audit --run-id steps567_finaldev --workflow nw_kyc \
  --end-time '2027-01-08T13:00:00+05:30' --version 3
```

The caller repair compared D2's 23/205 connected calls with peer D1's 63/195 and its own
770/2,805 history. Both one-sided p-values were below 0.01, with two hourly confirmations.
Approval apr_00003 authorized the rotation. Cleanup created version 4 in the same minute,
keeping the repair, so version 3 itself has no calls. Later incident verification counted
400 dials, 71 connected, 37 engaged and zero flags without detected material guardrail harm.

The KYC cleanup followed an inconclusive trial: pickup was 829/3,391 for control and 217/833
for challenger. The +1.60-point difference had bounds -1.73 to +4.93 at alpha 0.025, failing
the eight-point lift and positive-bound requirements. Engagement's -4.94-point lower bound
also failed the two-point non-inferiority margin. Approval apr_00005 allowed restoration.
The grader marked it harmful because it removed a real small engagement benefit.

## 11. Results

These tables come from the final grader reports. Deltas are relative changes from the no-op
baseline, not percentage points. Full reports: [public_01](./reports/public_01.md), [public_02](./reports/public_02.md), [public_03](./reports/public_03.md).

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

Public_01 had eight neutral, one beneficial and one harmful change. Restoring the KYC incumbent
after an inconclusive test removed a real small engagement benefit. Public_02 had thirteen neutral
and two beneficial changes, zero harmful changes, no expiry/lapse/apply conflict and five credits
spent. Its main benefit was incident repair. No public_01/02 voice candidate qualified.

Public_03 had sixteen neutral, four beneficial and two harmful changes. The harmful changes were
again inconclusive KYC restorations. Ten trials were inconclusive and two unfinished, with no
promoted winner. Synthetic tests cover promotion/decay behavior; the public runs do not demonstrate
winner lift. Aggregate changes from one seed cannot isolate treatment effects.

## 12. Trade-offs & rejected alternatives

| Option | Why considered | Why rejected / what instead |
|---|---|---|
| SQLite | Minimal persistence | PostgreSQL transactions/queries chosen; SQL work still measured |
| ORM/repository framework | Abstract storage | Explicit SQL exposes atomicity and recovery boundaries |
| RAG/vector database | Evidence retrieval | Exact populations, joins and templates fit SQL |
| LLM-selected winners | Flexible reasoning | Deterministic statistical rules; paid suggestions are hypotheses only |
| Redis/queue/workers | Throughput | One measured writer first; reduce query/retention cost before adding ownership coordination |
| Multiple arms/welcome interactions | Faster discovery | More comparisons and sample demands; one voice challenger |
| Sequential testing | Earlier promotion | Fixed checkpoints only; no sequential-testing CLI option |
| Automatic language cohorts/person schedules | Personalisation | Fragmentation, sparse evidence and business constraints |
| Web/notification service | Supervisor convenience | Concise CLI and approval queue now; production delivery remains unfinished |

## 13. Known weaknesses

- The conservative rules found no public_01/02 winner. Inconclusive cleanup and imprecise holdout retirement can discard a small real benefit.
- QA detection was slow. Cluster/delta intervals are approximations, and first/repeat or pre/post incident comparisons can have selection and timing bias.
- Welcome interactions, new cohorts, caller exploration and call-time optimisation are cut. Rollback may wait for approval or new campaigns.
- Uncertain paid calls require review. Fixed tenant shares can strand credits; tenant-wide attention preferences are incomplete.
- Kestrel's 11:00/two-request preference, notification delivery, named approval identity and a watchdog are missing.
- Person/time evidence grows with calls. Retention, database failover and continuous-arrival SLOs need work.
- The backend crash and input anomaly are unexplained. Package snapshots are pinned, but base image tags can change. Indistinguishable world resets can evade detection.

## 14. If this went to production at Formi next month

1. Confirm signed policies and stricter client preferences. Add named approval identity, notifications and acknowledgement before rollout.
2. Add provider idempotency/result lookup, immutable world IDs, least-privilege access and tested backup/restore. Investigate the backend crash and input anomaly.
3. Shadow continuously arriving traffic. Add an external watchdog, backlog/decision SLOs and named page/ticket owners.
4. Calibrate detection delay/power, repeated callers, rare harm and the cost of inconclusive cleanup/holdout retirement on fresh data.
5. Measure sufficient-statistic transfer, WAL and retention. Partition only where those results justify it, keeping per-workflow writes and shared budgets consistent.
6. Put the audit/status queries behind a supervisor UI. Broader experiments can follow when traffic and approval budgets support them.