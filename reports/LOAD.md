# Final profiled public_03 load run

Measured application: `f594647818faa6d8900131a40469ded7a3c6269c`, run `steps567_load`, schema `steps567_load_clean_2f139e`. See the [JSON summary](./steps567_load.json) and
[grade](./public_03.md). cProfile ran for the whole execution, and its overhead is included. Earlier unprofiled runs used different code. These measurements do not establish a controlled speedup.

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

Stored count, max event ID and API last ID all reached 9,737,475. Every advertised chunk committed
and all five days finished. Twelve trials ended as ten inconclusive and two unfinished; none was
promoted. There were no incidents. The grader counted 22 changes: 16 neutral, four beneficial and
two harmful. The harmful changes restored KYC incumbents after inconclusive trials.

## Bootstrap, day totals and target

History ingestion took 608.838 seconds and initial decisions another 7.258. The first loop took
616.096 seconds, included in total wall time.

| Simulated day | Live advance + loop seconds, excluding bootstrap |
|---|---:|
| D0 | 204.122 |
| D1 | 277.357 |
| D2 | 358.727 |
| D3 | 292.931 |
| D4 | 191.478 |

The mean and each live-day total meet ten minutes/day. Cold start plus D0 took 820.218 seconds
(13m40s), before small startup/logging costs, and missed it. Mean live ticks were 2.760 seconds but
the maximum was 25.434 seconds, so there is no six-second tail bound. A synchronous simulator also
leaves recovery from continuously arriving traffic untested.

| Stage, across bootstrap and live work | Seconds |
|---|---:|
| Inclusive ingestion | 1166.052 |
| Stream wait/decode, within ingestion | 35.299 |
| JSON parse, within ingestion | 116.240 |
| Remaining ingestion work, within ingestion | 1014.496 |
| Decision/API/statistics work | 709.585 |
| Advance + following state reads | 65.063 |

The three ingestion parts are already included in the total. Live ingestion took 557.214 seconds and
live decisions 702.327. Small startup, health and logging costs explain differences from full wall
time. `write_seconds` includes validation, serialization, discovery, COPY, SQL and commit.

## cProfile findings

The profile contains 896,866,062 calls. The raw file is `runs/steps567_load_clean_75d2d319/controller.prof` in ignored run storage; leading
functions are in the JSON summary. Inspect it with:

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

Parent and child cumulative times overlap. cProfile includes blocked I/O, so driver wait cannot
establish database CPU use. Initial decisions took less time than in the raw-JSON version, but code,
profiling and cache differences prevent attributing a precise speedup.

JSON parsing used about 10% of ingestion and 6% of full wall time. Faster parsing alone would leave
most write/wait and person-counter work. The run used no new parser dependency, queue or worker.

## Resource and measurement limits

The Linux controller used Python 3.12.16 with a 3-CPU/6-GiB quota. PostgreSQL 17.11 had 1 CPU/2 GiB.
Extra container swap was disabled. Total application limits were 4 CPUs/8 GiB on Docker Desktop's
shared 16-CPU/15.58-GiB VM. The external simulator ran on Windows, outside this budget.

Timing covers the Bash launcher and history bootstrap. Image/dependency setup, simulator
initialization, final fingerprints and grading are outside it. No other controller advanced or
database test wrote during measurement; read-only monitoring/rehearsal queries did run. Peak RSS
excludes PostgreSQL and page cache; PostgreSQL had a 2-GiB cap. The disk figure excludes WAL,
temporary COPY/sort files and simulator storage.

This profile measures f594647. A later fix saves safety/decay conclusions before consuming their
checkpoint; its final 118-test suite covers that crash path. It leaves the normal hot path
unchanged, but was not reprofiled here. The unresolved backend crash and input mismatch are described in [submission reliability](../SUBMISSION.md#9-reliability).

## Ten times the traffic

At this profiled throughput, 10× live ingestion alone projects to about 1,114 seconds/day before
decisions. It misses the ten-minute budget. Ten-times traffic was not run.

The cohort/hour cube has 8,791 keys; exact-time person evidence has 3,240,000 rows, equal to live
call count here. That part of the evidence grows with calls. Leads and raw events also grow.

Next measure serialization, WAL/index work and person-counter transfer/recalculation. Compute
cluster sufficient statistics nearer the database while keeping person covariance. Bound retention
and add time partitions where needed. Tenant/workflow sharding comes after that, with one
writer/proposal stream per workflow and atomic shared credit/attention budgets. Adding Redis or
vectors would leave the measured SQL and retention work.