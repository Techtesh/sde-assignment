# Final profiled public_03 load run

Application measured: `f594647818faa6d8900131a40469ded7a3c6269c`; run `steps567_load`;
retained schema `steps567_load_clean_2f139e`. [Machine-readable evidence](./steps567_load.json)
and [grade](./public_03.md). This is a **fully profiled** run: cProfile overhead
is included. [MILESTONE5_LOAD.md](./MILESTONE5_LOAD.md) preserves the earlier,
different unprofiled implementation; this is not a controlled speedup comparison.

## Measured result

| Measurement | Result |
|---|---:|
| Simulated days / ticks | 5 / 481 (480 advances) |
| History / live / total events | 5,537,379 / 4,200,096 / 9,737,475 |
| Live dials | 3,240,000 (648,000/day) |
| Live ingestion throughput | **7,537.7 events/sec** |
| Whole controller wall time | **1,943.207 sec** (32m23s) |
| Wall time per simulated day, including bootstrap | **388.641 sec/day** (6m29s) |
| Mean live advance-plus-loop time | **2,759.615 ms/tick** |
| Maximum advance-plus-loop bound | **25.434 sec** (25,434 ms) |
| Peak controller process RSS | **90.79 MiB** |
| Database tables/indexes/TOAST | **9,332,457,472 bytes** (about 8.69 GiB) |
| Exact-time person/voice rows | **3,240,000** |
| Experiment person/arm rows | **944,347** |
| Cohort/hour metric keys | **8,791** |
| Credits spent | **0** |

The final stored event count, max event ID and API last event ID are all
9,737,475; all advertised chunks are committed. All five days finish. Twelve
experiments end as ten inconclusive and two unfinished; no public winner is
promoted and no incident is raised. The grade records 22 changes: 16 neutral,
four beneficial and two harmful. The harmful changes restore KYC incumbents
after inconclusive trials; passing throughput is not proof of beneficial learning.

## Bootstrap, day totals and target

Historical ingestion takes **608.838 seconds**; initial decisions add 7.258 seconds.
The first complete loop is **616.096 seconds**. This initial work is included
in the headline timer, not removed to improve the average.

| Simulated day | Live advance + loop seconds, excluding bootstrap |
|---|---:|
| D0 | 204.122 |
| D1 | 277.357 |
| D2 | 358.727 |
| D3 | 292.931 |
| D4 | 191.478 |

The overall average and all live-day totals meet ten minutes/day. **Cold start
plus D0 does not**: recorded stages total **820.218 seconds** (13m40s), before
small startup/logging overhead. Nor is there a six-second tail guarantee: mean
live ticks are 2.760 seconds but the maximum is 25.434 seconds. A paused synchronous
simulator is not evidence of backlog recovery under continuously arriving traffic.

| Stage, across bootstrap and live work | Seconds |
|---|---:|
| Inclusive ingestion | 1166.052 |
| Stream wait/decode, within ingestion | 35.299 |
| JSON parse, within ingestion | 116.240 |
| Remaining ingestion work, within ingestion | 1014.496 |
| Decision/API/statistics work | 709.585 |
| Advance + following state reads | 65.063 |

The three ingestion subcategories are included in ingestion; do not add them
again. Live ingestion is 557.214 seconds; live decisions are 702.327 seconds.
Rounded stage sums omit small startup/health-recording/logging costs present in
full wall time. `write_seconds` includes validation, serialization, discovery,
COPY, SQL and commit, not only physical disk writes.

## cProfile findings

The profile accounts for **896,866,062 calls**. Raw data remains at
`runs/steps567_load_clean_75d2d319/controller.prof` in ignored local run storage;
leading functions are also preserved in the report JSON. To inspect it:

```bash
python -m pstats runs/steps567_load_clean_75d2d319/controller.prof
```

| Function | Cumulative elapsed seconds |
|---|---:|
| Store.ingest | 1162.357 |
| Driver wait (internal 1057.395 sec) | 1107.165 |
| ExperimentEngine.tick | 584.721 |
| Store.collect_exposure | 424.841 |
| event_row validation/adaptation | 150.401 |
| evaluate | 114.227 |
| comparison | 111.467 |
| Governance.proposal_facts | 13.749 |

Cumulative times overlap parent/child calls. Default cProfile elapsed time includes
blocked I/O; driver wait is not proof of database CPU utilization. The initial
decision phase is much smaller than the earlier raw-JSON implementation, but
version, profiling and cache differences prevent claiming a controlled speedup.

JSON parse is about 10% of ingestion and 6% of full wall time. A faster parser
alone cannot remove the measured wait/write and person-counter costs. No new
parser dependency, queue or worker was added merely because it was a suggested fix.

## Resource and measurement limits

Controller: Linux/Python 3.12.16, 3 CPU quota, 6 GiB memory. PostgreSQL 17.11:
1 CPU quota, 2 GiB memory. Additional container swap is disabled. The application
budget totals **4 CPUs / 8 GiB** on Docker Desktop's shared 16-CPU/15.58-GiB VM;
these are quotas, not dedicated bare-metal cores. The simulator is an external
HTTP service on the Windows host, outside the application budget.

Timing includes the real Bash launcher and history bootstrap. Image/dependency
setup, simulator initialization, post-run evidence fingerprints and grading are
outside it. No other advancing controllers or database test writes ran during
measurement; lightweight read-only monitoring/rehearsal queries were made. Peak
RSS excludes database memory and container cache; the database has a hard 2-GiB
cap. Footprint excludes WAL, transient COPY/sort files and simulator storage.

The profiled application is f594647. A later stop/checkpoint ordering correction
changes durability at safety/decay stops, retains the normal hot path, and is
covered separately by the final 118-test suite; this full profile predates it.
The earlier unresolved backend crash and invalid reference input are retained in
[LOAD_ATTEMPT.md](./LOAD_ATTEMPT.md) and [INPUT_ANOMALY.md](./INPUT_ANOMALY.md).

## Ten times the traffic

At unchanged profiled throughput, 10× live ingestion alone projects to about
**1,114 seconds/day**, before decisions. It therefore cannot meet the same
ten-minute budget without changes; this is a projection, not a tested capacity.

The ordinary cohort/hour cube has 8,791 keys, while exact-time person evidence
has 3,240,000 rows, equal to live call count here. The claim that all aggregates
stay small as events increase is false for the evidence needed by clustered and
first/repeat analysis. Leads and raw evidence also grow with traffic.

First profile/reduce serialization, WAL/index work and the transfer/recalculation
of person counters. Compute sufficient cluster statistics nearer the database;
retain person covariance. Add bounded time-based retention/partitions. Only then
shard tenant/workflow ownership, preserving one writer/proposal stream per workflow
and atomic shared credit/attention reservations. Redis/vector storage does not
remove these costs, and PostgreSQL is already the chosen store.
