# Final profiled public_03 load run

Measured application: `63d8c6ef546e810b859593336451d32b160c6ca4`, controller tree `e1fa57c374547592749eaf78b08d0e301e34ecf5`.
Run `steps567_load`, schema `steps567_load_clean_7b8269`. See the [JSON summary](./steps567_load.json)
and [grade](./public_03.md). This fresh run includes the cumulative QA detector and its exact-time
counters. cProfile covered the entire controller execution; its overhead is included.

## Measured result

| Measurement | Result |
|---|---:|
| Simulated days / ticks | 5 / 481 (480 advances) |
| History / live / total events | 5,537,379 / 4,200,096 / 9,737,475 |
| Live dials | 3,240,000 (648,000/day) |
| Live ingestion throughput | **7,382.3 events/sec** |
| Whole controller wall time | **2,005.933 sec** |
| Wall time per simulated day, including bootstrap | **401.187 sec/day** |
| Mean live advance-plus-loop time | **2,863.369 ms/tick** |
| Maximum advance-plus-loop bound | **24.858 sec** |
| Peak controller process RSS | **98.44 MiB** |
| Database tables/indexes/TOAST | **9,337,126,912 bytes** (8.70 GiB) |
| Exact-time person/voice rows | **3,240,000** |
| Exact-time QA rows | **7,120** |
| Experiment person/arm rows | **944,347** |
| Live workflow/version/cohort/hour keys | **824** |
| Credits spent | **0** |

Stored count, maximum event ID and API last ID all reached 9,737,475.
Every advertised chunk committed and all five days finished. Experiment statuses:
inconclusive: 10, unfinished: 2.
There were 0 qualified winners. The grader recorded 22 applied — neutral: 16, beneficial: 4, harmful: 2.
The harmful changes restored KYC incumbents after inconclusive trials; these are reported failures.
The 824 keys count live `hourly_metrics` rows with `dimension='all'`; per-variant rows are excluded.

## Bootstrap, day totals and target

History ingestion took 621.940 seconds and initial decisions another
6.872. The first loop took 628.812 seconds, included in wall time.

| Simulated day | Live advance + loop seconds, excluding bootstrap |
|---|---:|
| D0 | 202.081 |
| D1 | 285.859 |
| D2 | 377.150 |
| D3 | 314.019 |
| D4 | 195.308 |

The mean and each live-day total meet
ten minutes/day. Cold start plus D0 took 830.893 seconds (13.85 minutes),
missing that target before small startup/logging costs.
The maximum live tick was 24.858 seconds, so there is no
six-second tail bound. Continuously arriving traffic and backlog recovery were not tested.

| Stage, across bootstrap and live work | Seconds |
|---|---:|
| Inclusive ingestion | 1,190.884 |
| Stream wait/decode, within ingestion | 34.607 |
| JSON parse, within ingestion | 119.237 |
| Remaining ingestion work, within ingestion | 1,037.034 |
| Decision/API/statistics work | 746.524 |
| Advance + following state reads | 65.801 |

The ingestion parts are already included in its total. Live ingestion took 568.944
seconds and live decisions 739.652. Small startup, health and logging costs explain
differences from wall time. `write_seconds` includes validation, serialization, discovery, COPY,
SQL and commit.

## cProfile findings

The profile contains 897,627,253 calls. Its local raw file is
`runs/final_verify_b7441e2f/checkout/runs/steps567_load_clean_c6f5f36d/controller.prof` in ignored storage. Inspect it with:

```bash
python -m pstats runs/final_verify_b7441e2f/checkout/runs/steps567_load_clean_c6f5f36d/controller.prof
```

| Function | Internal seconds | Cumulative elapsed seconds |
|---|---:|---:|
| [Store.ingest](../controller/store.py#L190) | 23.875 | 1,187.191 |
| `psycopg.Connection.wait` | 1,116.656 | 1,166.264 |
| [ExperimentEngine.tick](../controller/experiments.py#L72) | 0.109 | 615.227 |
| [Store.collect_exposure](../controller/store.py#L613) | 0.049 | 455.011 |
| [SimulatorAPI.events](../controller/api.py#L47) | 25.598 | 175.376 |
| [event_row](../controller/store.py#L16) | 74.244 | 148.229 |
| [evaluate](../controller/statistics.py#L56) | 2.849 | 114.313 |
| [comparison](../controller/statistics.py#L11) | 87.565 | 111.452 |

Parent and child cumulative times overlap. cProfile includes blocked I/O, so driver wait cannot
establish database CPU use. JSON parsing used 10.0%
of ingestion and 5.9% of full wall time. Faster
parsing alone would leave most write/wait and person-counter work. This run does not establish
a controlled speedup over another implementation.

## Resource and measurement limits

The Linux controller had a 3-CPU/6-GiB quota. PostgreSQL 17.11 had 1 CPU/2 GiB. Extra container
swap was disabled: total application limits were 4 CPUs/8 GiB on shared Docker Desktop hardware.
The external simulator ran on Windows, outside this budget. Quotas do not reserve dedicated cores.

Timing covers the Bash launcher and history bootstrap. Image/dependency setup, simulator
initialization, final fingerprints and grading are outside it. Other controller/API/database tests
finished before this measurement or started after it; no competing verification work ran during it.
Monitoring read the controller log only. Peak RSS excludes PostgreSQL and page cache; the database
had a 2-GiB cap. Disk size excludes WAL, temporary COPY/sort files and simulator storage.

Database failover and continuous traffic remain untested. The unresolved backend crash and input
anomaly from development are described in [submission reliability](../SUBMISSION.md#9-reliability).

## Ten times the traffic

At the measured throughput, 10× live ingestion alone projects to 1,138
seconds/day before decisions. It misses the ten-minute budget. Ten-times traffic was not run.

The cohort/hour cube has 824 keys; exact-time person evidence has
3,240,000 rows and QA evidence 7,120.
Those tables, leads and raw events grow with calls or uploads.

Next measure serialization, WAL/index work and person-counter transfer/recalculation. Compute
cluster sufficient statistics nearer the database while keeping person covariance. Bound retention
and add time partitions where measurements justify them. Tenant/workflow sharding comes after
that, with one writer/proposal stream per workflow and atomic shared budgets. Redis or vectors
would leave the measured SQL and retention work.
