# Work plan

## Agreed decisions

- Build one Python controller process backed by PostgreSQL. Use `httpx`, the standard library, and one PostgreSQL driver; keep explicit SQL and small modules.
- Follow SOLID through responsibilities and testable boundaries, and Ponytail through the smallest complete implementation. No generic repository, dependency-injection framework, queue, vector store, or additional service.
- Access the simulator only through HTTP. Never import `sim`, read run directories, or parse scenario truth in controller code. Baseline/grade commands are external verification tools.
- Keep pickup (connected/dials), engagement (engaged/connected), and business outcome (concluded/uploaded) separate. Follow each workflow's primary KPI and guardrail.
- Keep decisions deterministic: same committed evidence, configuration, simulated time, and rule version produce the same decision. Persist ordering, experiment epochs, tie-break rules, and action intent.
- Use fixed evaluation checkpoints. `sequential_testing` defaults to `false`; reject `true` clearly until a sequential method is implemented and verified. Do not silently fall back.
- Retrieve evidence using SQL and render explanations from templates. The simulator's LLM may suggest prompt fixes; it never selects a winner or grants permission.
- Never change business-owned cadence, calling windows, or capacity.

## Scope and assumptions

Build reliable ingestion/history bootstrap, shared cohorts, caller-ID incident response, voice experiments, promotion/decay/rollback, validated prompt repair, governance, credit controls, audit, a consolidated CLI view, and operational measurements.

Start experimentation with voice only, one challenger and one active experiment per workflow. Greeting experimentation remains an extension pending a scope decision; measure both KPIs regardless of dimension. Defer call-time optimisation, per-person schedules, cross-client learning, and a web UI. Do not imply these are implemented in the submission.

Actual HTTP workflow policies are authoritative. Stakeholder claims about auto-apply must be checked against them. Start with existing/default cohorts; add language cohorts only if history supports useful sample sizes. Use the same cohort object and ID across detection, experimentation, and the supervisor view; preserve first-match ordering and default inheritance.

## Architecture

```text
Simulator HTTP -> ingest -> PostgreSQL -> learning -> durable intent
                                ^                       |
                                +--- governance <-------+
                                        |
                                simulator config writes
```

Responsibilities: `api` handles HTTP and safe retries; `store` owns transactions and queries; ingestion joins events and updates measurements; learning functions turn evidence into decisions; governance owns every configuration write; orchestration controls startup, tick ordering, and shutdown. Add modules as their behavior is built, not empty scaffolding.

Storage: workflow/policy snapshots, configuration history, leads and person IDs, ingested events/chunks, query-specific aggregate counters, experiment state, proposals, external actions, and audit records. Typed columns support joins/filtering; JSONB preserves payloads and evidence. Scope every record to the simulator run. Keep evidence sufficient for person-level analysis and the question: why did workflow X change at T, who approved it, and what happened afterward?

## Milestone 1: durable, observation-only foundation

1. Inspect HTTP schemas and run the baseline/naive example as verification when the local runtime permits. Never learn from hidden scenario fields.
2. Add the small HTTP client, PostgreSQL schema, ingestion, and command-line entry point. Document database startup and connection configuration; preserve `./run.sh <SIM_URL>`.
3. On startup, check simulator state, load workflow/config snapshots, discover history and event chunks, and drain outstanding data before advancing.
4. Stream NDJSON. Store lead features and join calls by lead ID. Batch writes; commit events, counters, and chunk completion together. Only newly inserted event IDs contribute to aggregates. Use separate discovery/checkpoints for history and live events because chunk numbering is global.
5. Each tick: drain ingestion, reconcile actions (when implemented), evaluate committed evidence, persist actions, process governance, record health, then advance 15 simulated minutes. Re-discover chunks after uncertain advance results rather than blindly retrying a time mutation.
6. On scenario completion, ingest final chunks before exiting. Fail clearly on malformed data or unknown state; never mark a partially ingested chunk complete.
7. Prove duplicate ingestion and transaction rollback/restart behavior against real PostgreSQL. Run an observation-only scenario and compare its outcome with baseline.

## Milestone 2: governance and audit

- Persist exact proposal/action intent before network I/O. Retry safe reads with bounded backoff; reconcile uncertain writes rather than retrying all POSTs.
- Proposal lifecycle: planned -> submitted/pending -> approved -> applied; record rejection, expiry, lapse, and stale-base outcomes explicitly.
- Stable IDs identify retries of one action. Fresh evidence/re-proposal after expiry gets a fresh persisted attempt ID even if the desired config is unchanged. A duplicate response triggers remote reconciliation, not assumed success.
- Reconcile every non-final proposal on startup through approval/config APIs. Apply approvals promptly within their apply window.
- Supervisor edits interrupt dependent experiments and invalidate old full-config proposals. Re-read current config, retain the edit, recompute the intended diff, and obtain fresh permission.
- Auto-apply requires enabled policy, allowed changed dimensions, and valid total-variation shifts for every effective cohort distribution. Otherwise seek approval; distinguish invalid proposals from changes requiring permission.
- Respect approver hours, rolling request limits, TTL, and apply windows. Batch compatible changes and reserve scarce requests for incidents where feasible.
- Every proposal carries exact diff, base version, rationale linked to audit evidence, affected-lead estimate, historical dry run, and documented impact score. Report unsupported counterfactuals as unknown. Validation evidence is mandatory for prompt changes.

## Milestone 3: detection and incidents

- Metric queries return numerators, denominators, windows, and uncertainty. Require population sizes and sustained changes; overlapping ticks are not independent evidence.
- Compare caller IDs within comparable cohorts/hours and against their own history. Shift weight conservatively to supported alternatives, respecting cohort overrides and policy.
- Detect elevated hallucination flags over connected populations; account for noisy QA. Request fixes only when evidence warrants credit spending.
- Persist LLM/validation intent and responses. These endpoints do not document idempotency keys: ambiguous outcomes must be surfaced and bounded, not represented as exactly-once spending.
- Validate candidate safety within per-incident budgets and a shared reserve. Validation does not demonstrate engagement. Propose a supported fix and verify safety and engagement after application.
- Allocate attention/credit work deterministically across tenants so one workflow cannot consume the entire budget.

## Milestone 4: deterministic experiments and rollback

- Store cohort, incumbent/challenger, actual exposure, configuration epoch, start time, decision checkpoint, sample requirements, minimum useful lift, guardrail margin, and statistical rule version before the experiment starts.
- Use a small challenger share (20% is a candidate, not an assumed policy allowance). Starting a split itself requires governance. Count only observed exposure; account for campaign-pinned configurations and supervisor interruptions.
- Monitor safety every tick, but declare a winner only once at the predeclared final checkpoint. Insufficient evidence is inconclusive; do not repeatedly extend until significant.
- Use a declared primary-KPI improvement test and guardrail non-inferiority test. Account for repeated people/calls in analysis. Allocate error budgets across planned experiments/comparisons; add Holm correction where there are multiple challengers, rather than unnecessary machinery for one comparison.
- Predeclare separate population-based emergency-stop rules. Apply safety stops through governance too.
- Retain a small control share where permitted. Detect decay at declared monitoring windows and request a version-checked rollback. Do not overwrite unrelated supervisor edits.
- Validate the entire decision procedure under equal-rate simulations and known lifts, including correlated/repeated callers and guardrails. Estimate false-winner rates with uncertainty rather than requiring exactly <=5% in 1,000 random trials.
- Keep `sequential_testing=false`. Enabling the flag before a validated sequential evaluator exists is a configuration error. Later add it through a small evaluator function boundary, not a framework.

## Milestone 5: evidence and delivery

- Focus tests on duplicate ingestion, mid-transaction failure, ambiguous network results, approvals and supervisor conflicts, experiment timing, guardrails, and credit limits.
- Run public_01 and public_02 end to end; generate baseline comparisons and grade reports without feeding hidden truth back into controller logic.
- Measure public_03 events/sec, ingest/decision lag, peak memory, and wall time per simulated day on the stated machine envelope. Target less than 10 minutes/day. Measure database work before adding partitioning, parallel workers, or another system.
- Demonstrate kill/restart during ingestion and external-action handling, then correct completion with no duplicate application or lost approvals.
- Provide one CLI view for experiments, pending approvals, changes, incidents, ingest lag, decision counts, and credits. Audit queries must work from the controller's own database.
- Complete [SUBMISSION_TEMPLATE.md](./SUBMISSION_TEMPLATE.md) as `SUBMISSION.md`, retain every heading, address all six stakeholder memos, and record cuts, actual results, weaknesses, and production follow-up.
- Keep small, honest commits at working milestones; never commit credentials or generated run state.

## Implementation status

- [x] Assignment, simulator contract, stakeholder memos, starter code, and user notes reviewed.
- [x] PostgreSQL, deterministic decisions, and fixed-checkpoint defaults agreed.
- [x] Work plan recorded.
- [x] Milestone 1: durable observation-only controller, verified against public_01 baseline.
- [x] Milestone 2: durable governance and audit, verified through real API calls and recovery tests.
- [x] Milestone 3: incident detection, governed repair, credit controls, and post-apply verification.
- [x] Milestone 4: fixed-checkpoint voice experiments, person-clustered selection, governed promotion/decay rollback.
- [x] Milestone 5: measured evidence and submission.

Time budget: approximately 15-16 hours total, with about four reserved for verification and documentation. If time tightens, reduce cohort sophistication before reducing governance or recovery guarantees.

### First implementation results

- Added the observation-only controller, PostgreSQL 17 Compose service, transactional streamed ingestion, separate KPI aggregates, restart protection, launcher, and [operating guide](./docs/CONTROLLER.md).
- 16 focused tests pass, including real PostgreSQL duplicate/replay handling, rollback after aggregate updates, abrupt process exit during COPY and restart, world reset checks, final-event draining, malformed evidence, HTTP retry boundaries, and reserved sequential flag behavior.
- public_01 completed all eight simulated days. PostgreSQL contains 297,024 events and 393 completed chunks. All workflow outcome deltas against baseline are exactly zero, as expected for observation-only operation; no config writes or credits were used.
- Restarting the finished run ingests zero events and exits cleanly. Linux Bash syntax passes, and shell scripts are pinned to LF endings.
- This is foundation evidence, not a load benchmark or evidence for governance/learning that has not been built. See [verification notes](./reports/FOUNDATION.md) and [grade report](./reports/foundation_public01.md).

### Step 1 API gate and step 2 results

- Independently re-read all 297,024 events in 393 chunks through HTTP. Compared raw event, lead, audit, pickup, engagement, and hallucination counts against PostgreSQL. Verified workflow config snapshots and a zero-ingestion restart without advancing or changing simulator state.
- Added deterministic proposal IDs, immutable durable intent, append-only proposal audit, config validation, shared cohort matching, effective-distribution policy checks, approval timing/fatigue, reconciliation, and safe application.
- Supervisor changes make old proposals stale. Explicit re-proposal requires a new decision/rationale, recomputes proposal facts, preserves unrelated edits, and rejects conflicting edits. Callers batch compatible changes before planning; statistical re-evaluation belongs to the later learning layer.
- Ran 47 regression/live-foundation checks successfully (46 focused controller/governance tests plus the step 1 live API check). A separate fresh real-API governance check also passed in 18.48 seconds: one auto-apply, one approval-based application, an intentionally lost successful response, a new database session, and no duplicate submission/application or credit spending.
- The real API test exposed a slow post-load affected-lead query. Materializing its event subsets prevents per-lead rescans; the final smoke test completes without the previous stall.
- See [governance operating guide](./docs/GOVERNANCE.md) and [verification report](./reports/GOVERNANCE.md). This does not claim full public_02 incident response, statistical learning, or load-scenario performance.

### Step 3 results

- Added deterministic completed-hour detection with two consecutive confirmations, shared cohort IDs, exact population tests, supported caller-ID alternatives, and known-history/LLM prompt candidates.
- Added persisted incident/action audit, n=300 validation, global reserve/per-incident/tenant spending limits, durable fair attention, safe paid-call uncertainty handling, and review holds across unrelated config epochs.
- Every repair and rollback goes through governance. Prepared proposals now require their source base version. Urgent requests are held when TTL cannot survive approver availability. Compatible queued caller repairs can be batched into prompt repairs atomically.
- Added post-apply recovery checks and per-cohort guardrail checks. Validation is not engagement evidence, and verification is observational rather than a formal non-inferiority claim.
- Public_01 completes with zero changes, zero credits, and outcomes identical to baseline. Public_02 completes with two applied changes, both graded beneficial, no expired/lapsed/conflicting approvals, and six credits spent. Both recorded incidents resolve after observed recovery.
- Kestrel public_02 conclusion rate improves 15.2% relative to baseline, pickup 9.6%, engagement 3.6%; hallucinated calls fall from 330 to 89. Prompt time-to-fix is 1,365 simulated minutes, including the overnight approver wait; this remains a weakness.
- Verification covers 66 focused tests plus one independent live API/restart check (67 total). See [incident guide](./docs/INCIDENTS.md), [verification report](./reports/INCIDENTS.md), [public_01 grade](./reports/step3_public01.md), and [public_02 grade](./reports/step3_public02.md).
- Next: voice experiments, deterministic fixed-checkpoint winner selection, decay and rollback; load evidence and final submission still remain.

### Step 4 results

- Added one prospective voice challenger in one existing cohort per workflow: 20% trial exposure, a fixed 72-hour checkpoint after actual authorized exposure, declared sample/effect requirements, and separate primary/guardrail decisions. No early winner or extension until significance.
- Added person-clustered ratio inference, per-workflow testing-budget spending across trials, and explicit guardrail non-inferiority. Actual exposure is isolated by config version, cohort, phase, and stable person ID. Atomic person counters/window cursors survive replay and restart.
- Added governed 80% winner promotion with 20% control, hourly population safety stops, fresh daily decay windows, and voice-only cleanup/rollback that preserves unrelated supervisor edits. Incident repairs supersede pending trials without importing unapproved experiment settings.
- Fixed two integration findings: API applied times can be minute offsets, and a full-workday approval latency could deadlock submission. Also replaced mismatched historical/live incident guardrail comparisons with conservative pre/post clock-hour adjustment; the final combined run resolves both incidents using six credits.
- 93 focused regression/statistical/lifecycle checks pass, plus two independent HTTP/event/restart audits (95 checks total). The seeded correlated-null calibration records 2 full-procedure false winners in 500 replications; this is finite-sample evidence, not a production guarantee.
- Both public scenarios complete. No voice candidate qualified for promotion under the declared rules. Public_01 has four inconclusive trials and one loss; one restoration of a truly beneficial but inconclusive trial is graded harmful. Public_02 has interrupted/blocked/inconclusive trials, two beneficial incident repairs, and no harmful applied changes in the final run.
- Promotion and decay are exercised with known-effect synthetic HTTP/real-PostgreSQL tests; the public runs do not demonstrate a live promoted-winner decay episode. Automatic language-cohort creation and welcome-message experiments remain cut.
- See [experiment guide](./docs/EXPERIMENTS.md), [verification report](./reports/EXPERIMENTS.md), [public_01 grade](./reports/step4_public01.md), and [public_02 grade](./reports/step4_public02.md). Milestone 5 evidence and delivery are recorded in [DELIVERY.md](./reports/DELIVERY.md).

## Step 5 

1. Promotion with a holdout

When an experiment declares a winner, move the cohort’s allocation to about 90% winner and 10% old control. The 10% is your yardstick for everything that follows.
Send the change through decide_route. Auto-apply it where policy allows, and propose it where it doesn’t.
Promote only in the cohorts where the evidence is, and don’t spread a win to cohorts you didn’t test.
Store the lift you measured at promotion time, plus the config version and the timestamp.

2. Decay watch

Each tick, compute the winner-minus-holdout difference per day since promotion, using the same days for both so day effects cancel.
Roll back if the lift has been under half of the promotion lift for two consecutive days, with a minimum sample, or if it’s no longer distinguishable from zero.
The holdout is small, so use one-sided tests on 1 to 2 day windows.
Check first-exposure and repeat-exposure calls separately, because returning people are where fatigue shows up.
A rollback restores the previous allocation. It goes through the same router and takes a request slot ahead of exploration.

3. Hallucination incident flow

Detect. Per workflow and prompt_version, take the rate of hallucination_flag among connected calls and run a binomial test against the history baseline. Require a minimum call count and persistence over several ticks, because the detector is noisy in both directions.
Attribute. Look in config history for a recent prompt_version change and note who made it. Log it in the audit entry.
Pick a candidate. The first candidate is the previous prompt, since you already know its flag rate and engagement from your own data. Spend 3 credits on suggest-fixes only if that isn’t enough, and keep only suggestions that appear in the workflow’s options.
Validate. Check the credit ledger, then run a validation of around n=500 (5 credits). Compare pass_rate to the policy threshold, or to your documented assumption if the policy has none. If it fails, try the next candidate.
Propose. Prompt changes always go through approval with evidence.validation_run_id. Send it right away at incident priority. Say plainly in change_summary that it reverses a supervisor edit.
While waiting, keep watching, raise an alert to the client’s supervisor, and don’t try to get around the approver. If the request is rejected or expires, move to the next candidate.
Verify after applying. Check the flag rate over the next few hundred calls, then close the incident with the time-to-fix recorded. If it didn’t improve, reopen.

4. Check. Run public_02. Read the grade report for incident timing, harm ratings, and how fast you moved off fading variants. Re-run public_01 as a regression check. Commit.

## Step 6 
1. Kill and restart test

Add an env var CRASH_AT to the controller. It calls os._exit(137) at named points: after advance, mid-ingest, after the intent row is saved, after the POST but before recording it, and after apply but before recording it.
Write tests/crash_test.py to run a scenario once per crash point. Each run restarts the controller after the kill and lets it finish.
Compare with a clean run: no duplicate proposals or applies in the simulator’s /approvals and config history, and the same audit decisions and final config history. The sim waits for you and the logic is deterministic, so these should match. If they don’t, find out why.
Keep the output. Kabir wants to see the test, not a promise.

2. Loop health view

Add python -m controller status, printing one screen: ingest lag (chunks behind), decisions per hour, wall time of the last tick, credits used per workflow against its ledger, pending proposals and their age, and open incidents.
Define a few alerts, each with a message that says what to look at. Examples:
Ingest stalled for N ticks.
An approved proposal close to its apply_by.
An incident open longer than X.
Credits under the reserve.
A crash loop.
Mark each as page or ticket. Anything that can wait until morning doesn’t page.

3. Load run on public_03

Run it limited to 4 CPUs and 8 GB, for example in Docker with --cpus 4 --memory 8g.
A simulated day is 96 ticks, so the target is about 6 seconds per tick, ingest and decisions included.
Time each stage separately: advance, fetch, parse, store write, decide. Use cProfile and record peak memory.
The usual fixes are orjson, one transaction per chunk, accumulating counters in a dict and upserting once, no per-event SQL, and only the indexes you query. Decision queries should read the aggregate table and never raw events.
Record events per second, milliseconds per tick, peak memory, and database size.

4. Ten times the load. Scale your measured numbers and name what breaks first. Single-threaded parsing is probably first, with the store write rate close behind. The aggregate table grows with the number of distinct keys, not with events, so it should hold up. The leads table grows with leads. State the fix for each, for example parse in worker processes per workflow, or move to Postgres. Credits and approver limits don’t scale with events at all.

5. Check. Run all three scenarios and save the grade reports to reports/. Commit.

## Step 7 

1. SUBMISSION.md. Follow the template. Keep these sections short:

What you built.
What you cut and why. This is the part scored for scope.
Assumptions.
Design choices with the reason: the statistical test, the policy router, and the storage decision.
Results for each scenario, with your own interpretation. Don’t tune to one scenario.
What you’d build next.
How to run it.

2. Stakeholder replies. For each memo write a short reply with four parts: what they asked, what you accept, what you push back on and why, and what you built. Check each claim against the workflow policies from GET /workflows, because the README says some claims don’t match. Where a stakeholder is wrong, say what you checked and ask what they would give up instead. Use the Kabir reply from before as the model. I only saw that memo, so I can’t say anything about the others.

3. Repo cleanup. Check these before you submit:

reports/ and run.sh are present.
The README says how to run it, and no secrets are in git.
A fresh clone into a temp directory runs run.sh on public_01 from scratch.

4. Review rehearsal. Pick three decisions from your own audit store, for example a promotion, a rollback or caller ID rotation, and a hallucination fix. Practice explaining each using only the audit rows: what data, what threshold, what you ruled out, who approved. Be ready to run the one query that shows a decision live. Prepare answers for the questions you’re most likely to get:

Why this test and this correction?
What if the approver rejects it?
What if a supervisor edits during an apply?
What breaks at 10 times the load?
What did you cut and why?
What would you do with another week?

5. Submit. Give your reviewer access to the private repo using the email on the form, submit the form, and confirm the deadline.

If you’re behind, cut in this order: dry-run sophistication, number of alerts, decay-rule refinements, then the number of experiments you run. Don’t cut the audit log, the crash test, or the policy router.

## Added-step execution (2026-11-08)

The Step 5–7 requirements above are retained verbatim. This records implementation and verification separately.

- [x] Step 5 code: 90/10 promotion; persisted reference lift/version/time; daily and fixed 48-hour retirement checks; separate first/repeat populations.
- [x] Step 5 code: prior-prompt-first repair, n=500 validation, mandatory approval, supervisor attribution/alerts, bounded fallback and time-to-fix records.
- [x] Regression suite: 118 focused tests pass on Windows and Linux, including exact-version audit, approval-deadline recovery and interrupted decay-stop intent.
- [x] Step 5 real public_01/public_02 verification: 1 harmful inconclusive cleanup in public_01; 2 beneficial repairs, 0 harmful changes and 5 credits in public_02. Detection delay remains a weakness.
- [x] Step 6 code: reusable crash script, concise status plus detailed JSON, actionable page/ticket suggestions, cProfile support.
- [x] Decision evidence: campaign/conclusion state and exact-time person counters updated with ingestion; one-time atomic backfill for old runs; no raw-call JSON queries in learning.
- [x] Step 6 final crash matrix, profiled public_03 run, all three grades, and measured 10× discussion. All five recovery cases match; the load average is 6m29s/day including bootstrap, while cold start plus D0 is 13m40s.
- [x] Step 7 local work: final submission, six policy-checked replies, fresh-clone run, and three-decision rehearsal. See [delivery evidence](./reports/STEPS_5_7.md) for version boundaries, results and retained failures.
- [ ] Step 7 external submission: reviewer email, form URL, deadline, author name and actual hours are still required from the user.

Choices: existing declared experiment shares/rules and incident validation/budgets remain unchanged on restart. New incident budgets are 18 credits (old records retain 12), preserving the six-credit reserve. A lost significance test retires insufficiently supported benefit at a fixed checkpoint; it is not described as proof of harm. QA persistence follows prompt/cohort changes, not unrelated voice edits. Unknown event types fail the chunk transaction.
