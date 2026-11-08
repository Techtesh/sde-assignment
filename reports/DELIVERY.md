# Milestone 5 delivery evidence

Measured 2026-11-08. New runs use run IDs `delivery01` and `delivery02`, rather
than reusing an earlier world's identity. The loop/statistical policies are
unchanged from milestone 4. Approval choices and resulting exposure can differ
between run identities. Earlier reports remain available, including the harmful
inconclusive cleanup in [EXPERIMENTS.md](./EXPERIMENTS.md).

## Automated checks

The original delivery suite passed on Linux/Python 3.12 with real PostgreSQL:

```text
python -m pytest -q -p no:cacheprovider tests/test_controller.py tests/test_governance.py tests/test_incidents.py tests/test_experiment_statistics.py tests/test_experiments.py tests/test_observability.py
98 passed in 29.26s
```

The 93 earlier checks cover ingestion/replay, PostgreSQL transactions, uncertain
governed writes, permission conflicts, experiment inference/timing/exposure,
guardrails, credit bounds and synthetic promotion/decay. Five new checks cover
read-only views alongside an active writer, CLI invocation without a simulator URL,
persisted tick replacement, alert suggestions, and complete-hour/new-epoch audit
counts with IST boundaries. Tests use isolated database schemas. The full
simulation's own tests are outside the controller's verification scope.

The load-driven ingestion change adds two same-chunk duplicate cases. The updated
**100-check focused suite passes on Linux/Python 3.12.16 in 20.76 seconds**, with
real PostgreSQL, and on Windows/Python 3.14 in 19.40 seconds.

## End-to-end public results

Both final worlds ran through the real Linux Bash launcher with PostgreSQL, from
initial history through scenario completion. The external harness used the
simulator CLI only to start/grade worlds and HTTP to inspect outcomes. It never
fed hidden grade information back into the controller.

| Final run | public_01 | public_02 |
|---|---:|---:|
| Simulated days | 8 | 10 |
| Raw events in our store | 297,037 | 324,326 |
| Completed chunks | 393 | 493 |
| Voice experiments | 5 | 6 |
| Inconclusive | 4 | 3 |
| Interrupted | 0 | 3 |
| Rejected before exposure | 1 | 0 |
| Qualified public promotions | 0 | 0 |
| Config changes applied | 8 | 13 |
| Graded beneficial / harmful | 0 / 0 | 2 / 0 |
| Approval requests | 5 | 7 |
| Approved / rejected | 4 / 1 | 7 / 0 |
| Expired / lapsed / apply conflicts | 0 / 0 / 0 | 0 / 0 / 0 |
| Credits used | 0 | 6 |

Full grader outputs: [public_01.md](./public_01.md), [public_02.md](./public_02.md).
The aggregate conclusion-rate changes are +1.5% and +5.3% relative to their
no-op baselines. These single-world aggregate deltas are not randomized causal
estimates. The evidence supports two incident repairs, rather than a discovered
voice winner. The conservative rules intentionally allow an inconclusive result.

## Public_02 timeline from our audit

All times below are Asia/Kolkata. D0 is 2027-01-04 in this observed run.

| Time | Evidence/action |
|---|---|
| D2 10:00 | Grader records caller-ID incident onset; this is external evaluation, not detector input |
| D2 12:00 | Our store records two-hour caller signal and governed repair proposal |
| D2 14:15 | Approved caller-ID repair applies; old voice trial is interrupted/cleaned up |
| D2 16:00 | Caller recovery verified: 400 dials, 71 connected, 37 engaged, zero QA flags |
| D3 11:30 | Supervisor changes prompt to P2; config epoch interrupts dependent trial |
| D3 16:00 | Two completed-hour QA signals; suggestion request succeeds (3 credits) |
| D3 16:15 | Candidate validation succeeds on n=300 (3 credits) |
| D3 16:30 | Validated repair proposal is ready/submitted |
| D3 18:30 | Approval `apr_00006` permits prompt repair; version 8 applies |
| D3 21:00 | Recovery verified on 19:00–21:00 exposure: 800 dials, 164 connected, 71 engaged, two flags |

The final prompt time-to-fix is **420 simulated minutes**, not the five-hour
number from the earlier milestone-four world. Both incidents resolve in our
store. The bad caller ID receives no exposure from D3 onward; D2's flagged-ID
share is 0.212. Kestrel's final conclusion rate is 0.286 (+15.5% relative), pickup
0.202 (+9.6%), engagement 0.494 (+3.7%); hallucinated calls are 97 versus 330 baseline.
Post-apply guardrails record "no detected material harm", not formal non-inferiority.

## Real audit answer

The retained schema is `delivery02_clean_7dd399`. With `DATABASE_URL` pointing
to the verification database:

```bash
export PGOPTIONS='-csearch_path=delivery02_clean_7dd399'
python -m controller audit --run-id delivery02 --workflow ks_cancel \
  --at '2027-01-07T18:30:00+05:30'
```

Selected real fields (full output in [audit_example.json](./audit_example.json)):

```text
actor: controller_approved
config version: 8
event ID: 240051
proposal ID: 2eeb329011a86dfeb997a6695f28320e178abe8a9f0a350c58698666fdf7430c
approval ID: apr_00006
change: Repair elevated hallucination flags
incident: 7c9213f82b9d425a0c18d85b5d00065f09bf37f735f3b6b84e2f5f669ddc3bac
latest alarm: 5 flags / 71 connected; historical normal: 14 / 1,190
one-sided Fisher p: 0.0030773330685603313
excess QA flags: 0.05865782932891467
next complete-hour version-8 exposure: 800 dials / 164 connected / 71 engaged / 2 flags
pickup: 0.205; engagement: 0.4329268292682927
```

The result links the exact diff, validation evidence, policy route, recorded
approval decision and subsequent outcomes. The API provides the approval ID,
not a human name. Version 9 supersedes this exposure later, so later-version
calls are not attributed to version 8. This is an observed post-change result,
not isolated treatment lift.

The companion command `python -m controller status --run-id delivery02` returns
[status_example.json](./status_example.json). At completion: no pending proposals,
no open incidents, event backlog zero, history chunk 0 plus live chunks 1–492,
and 194 credits remaining. Its credit ledger assigns six successful credits
to Kestrel. The historical wall age of this finished run is not a stale-loop page.

## Abrupt exits and restart

[verify_delivery.py](../scripts/verify_delivery.py) exits the controller with code
137, without cleanup, at five named boundaries. Each case uses a fresh public_01
world and isolated retained PostgreSQL schema, with the same run ID as the clean
case. It then restarts normally and compares committed evidence and remote state.

Machine-readable results are in [crash_recovery.json](./crash_recovery.json).
All five forced exits returned 137; all five normal restarts returned zero and
matched the clean completed run:

| Case | Restart-to-finish seconds | Raw events | Matches clean |
|---|---:|---:|---|
| Clean reference | 136.498 | 297,037 | Reference |
| Mid-ingest | 126.886 | 297,037 | Yes |
| After advance | 124.318 | 297,037 | Yes |
| After durable intent | 107.448 | 297,037 | Yes |
| After accepted approval POST | 91.225 | 297,037 | Yes |
| After remote apply | 121.249 | 297,037 | Yes |

Restart times begin at different simulated minutes and include their remaining
bootstrap/work; they are not comparative speed measurements.
The five-point matrix above used `18e3e82`. After the load-driven ingestion
change, a **fresh checkout of `7c20533`** ran the Linux launcher, exited 137
mid-ingestion, restarted to exit zero, and matched that clean reference's entire
business-evidence signature and remote state. See
[crash_recovery_final.json](./crash_recovery_final.json); retained schema
`delivery01_final_mid_d352b8`, checkout `runs/delivery_checkout_7c20533`.
The four network/intent boundaries are unchanged by this ingestion optimization;
their real matrix evidence is retained, rather than relabelled as a new run.
Every completed crash case must match the clean run's event fingerprint, chunks,
metrics, proposals, experiment state/person counters, incidents and config-change
audit, plus remote approval records and configuration history. Repeated remote
proposal IDs are rejected. Additional recovery transition records are allowed.
This verifies process recovery around real HTTP/database writes; it does not
simulate loss of the database or disk, or claim automatic recovery of ambiguous
paid results. Incident tests cover the durable review hold for that API limitation.

## Scale and limits

[LOAD.md](./LOAD.md) records the separate public_03 benchmark. It runs after the
other database tests so shared verification work does not contaminate the load
numbers. Controller plus PostgreSQL cgroup budgets total four CPUs/eight GiB;
the simulator is external. No partitioning, extra workers or new dependency was
added before measuring.

The completed fresh run stores 9,737,478 events over five live days. Live ingestion
is 11,747.2 events/sec, peak controller RSS is 101.36 MiB, and maximum measured
advance-plus-decision bound is 38.283 seconds. Full wall time averages 345.977
seconds/day, including bootstrap. Every live-day total is below ten minutes;
**cold start plus D0 is about 11m47s and misses that target**. The report preserves
both the passing average and this startup limitation.

The first load attempt failed after committing history when PostgreSQL reported
a backend segmentation fault during proposal reach calculation. The server recovered;
the cause was not isolated. [LOAD_ATTEMPT.md](./LOAD_ATTEMPT.md) preserves that
failure and the subsequent query plan. Session JIT compilation is disabled and
redundant chunk work is removed in the measured rerun; this does not establish
that the PostgreSQL defect was identified or fixed.

No public winner was promoted. Live promoted-winner decay remains unproven by
these public worlds, although the controlled lifecycle checks exercise it.
The user-authored WIP section of [WorkPlan.md](../WorkPlan.md) remains unchanged.

The first implementation commit records the already-developed milestones together;
it does not manufacture earlier history. `7c20533` records the measured ingestion
optimization. A clean checkout of `18e3e82` passes Linux Bash syntax/import checks;
the clean `7c20533` checkout completes the full eight-day world after an abrupt
exit. Application source is mounted read-only during Linux verification.
