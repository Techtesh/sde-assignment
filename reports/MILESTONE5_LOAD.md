# public_03 load measurement

The completed result is recorded in [milestone5_load_public03.json](./milestone5_load_public03.json).
The first failed attempt is retained separately in [LOAD_ATTEMPT.md](./LOAD_ATTEMPT.md);
it is not included in successful-run throughput or day averages.

## Environment and method

Controller: Linux container, Python 3.12.16, one process, 3 CPU quota and 6 GiB RAM.
PostgreSQL 17.11: Linux container, 1 CPU quota and 2 GiB RAM. Extra container swap
is disabled. Thus application quotas total **4 CPUs / 8 GiB**, including the
database; they are limits on Docker Desktop's shared Linux VM, not dedicated
bare-metal cores. The VM advertises 16 CPUs / 15.58 GiB. The simulator runs outside
the application budget as an external HTTP service on the Windows host.

The harness starts a fresh public_03 world using the simulator CLI, waits for
HTTP health, then times the real `run.sh` in the Linux container. Source is
mounted read-only. No other tests/controllers use this PostgreSQL service during
the measurement. Lightweight checkpoint/resource observations are not a second
application workload. Setup/image build, simulator initialization, post-run audit
fingerprints and grading are outside the timer; **history bootstrap is inside**.

The API advertises 5,537,379 historical events in 23 chunks and five live days
(7,200 simulated minutes). The controller gets those numbers through HTTP, never
from scenario truth or simulator files. [verify_delivery.py](../scripts/verify_delivery.py)
is the external measurement harness; [OPERATIONS.md](../docs/OPERATIONS.md) gives
reproduction commands and the timing definitions.

## Completed measurements

The bootstrap commits 5,537,379 events in **465.567 seconds**, or **11,893.8
events/second**. First-loop proposal preparation takes another 73.767 seconds;
the first complete loop is **539.334 seconds** (8m59s).

Fresh run: `load03`, schema `load03_clean_efb216`, application commit
`7c20533ec44a66adc737f096dc958546cfd4f76e`. All five days finish with zero
backlog against the final HTTP state: stored count/max event ID and API last ID
are all 9,737,478; all 269 advertised chunks are committed.

| Measurement | Result |
|---|---:|
| Historical / live / total events | 5,537,379 / 4,200,099 / 9,737,478 |
| Live dials | 3,240,000 (648,000/day) |
| Live ingestion throughput | **11,747.2 events/sec** |
| Full wall time, including history and initial decisions | **1,729.883 sec** (28m50s) |
| Full wall time / five simulated days | **345.977 sec/day** (5m46s) |
| Largest live advance-plus-decision bound | **38.283 sec** |
| Controller peak RSS | **101.36 MiB** |
| Tables, indexes and TOAST in this schema | **7,852,056,576 bytes** (about 7.31 GiB) |
| Experiment person/arm rows | 943,089 |
| Credits spent | 0 |

| Simulated day | Live advance + loop seconds, excluding bootstrap |
|---|---:|
| D0 | 167.310 |
| D1 | 238.956 |
| D2 | 314.501 |
| D3 | 308.241 |
| D4 | 159.278 |

The overall average and every live-day total meet ten minutes/day. **Cold startup
plus D0 does not:** the recorded stages sum to 706.644 seconds, about **11m47s**,
before small launcher/logging overhead. An average is not evidence of a sub-ten-minute
cold first day. The longest live day is 5m15s. This distinction is a retained
limitation, rather than removing bootstrap from the headline timer.

| Stage totals across bootstrap + live work | Seconds |
|---|---:|
| Ingestion (inclusive) | 823.107 |
| Stream wait/decode, within ingestion | 32.831 |
| JSON parse, within ingestion | 81.722 |
| Remaining ingestion work, within ingestion | 708.564 |
| Decision work, including API/governance and statistics | 837.673 |
| Advance requests and following state reads | 66.830 |

Do not add the three ingestion subcategories to the inclusive ingestion total.
Live decision work is 763.906 seconds versus 357.540 seconds of live ingestion;
the decision path is the larger steady-state cost. Rounded stage sums omit small
recording/logging/startup costs captured by the full wall timer. The run records
12 experiments: ten inconclusive, one lost, one blocked; no winner promotion,
no incident records and no paid calls. This is a full controller measurement,
not an observation-only shortcut.

## What the measurement changed

The first attempt exposed redundant ingestion work: a large chunk sorted JSONB
to discover conflicting duplicates and could join against all earlier events
even when every ID was new. The final path checks narrow IDs first, compares
payloads only for duplicates, and skips prior-row comparison only when the actual
minimum input ID exceeds the committed maximum. Unique chunks avoid a redundant
DISTINCT sort. Overlapping/replayed IDs still take the full equality check;
same-chunk conflicts still roll back. The regression suite covers these paths.

The proposal reach query's recovered plan spent 2.279 of 7.425 seconds compiling
49 JIT functions. Controller sessions disable JIT to avoid repeated compilation
overhead. The observed backend crash was not reproduced and its cause remains
unresolved; successful rerun evidence cannot establish that a server defect is
fixed. No new dependency, partition, queue or worker was added.

## Interpretation and 10×

Wall time/day including bootstrap is the full timed controller duration divided
by five. Live day totals exclude the one-time bootstrap and show variability.
The maximum advance-plus-loop duration bounds the wall time from the start of
synchronous event generation to a completed decision in this simulator; it is
not a production p99. Simulated decisions still occur on 15-minute ticks.

Process peak RSS is measured with Linux `getrusage`; it excludes database memory
and container page cache. PostgreSQL's hard 2 GiB cap bounds its contribution;
its lifetime `memory.peak` includes earlier unrestricted tests and is not quoted
as a fresh-run measurement. The database table/index/TOAST footprint excludes
WAL, transient sort/COPY files and simulator storage. A quota is not a measured
RSS value, and an average is not a cold-start latency claim.

At 10×, first profile ingestion serialization/SQL/WAL and the materialized
active/concluded-lead sets used for proposal facts. Persisting concluded-lead
state transactionally can avoid repeatedly deriving it from all historical
calls. Retain raw evidence with time-based retention/partitions. Person-counter
transfer and inference also scale with distinct people; aggregate sufficient
cluster statistics closer to the database before shipping every row each look.
Then shard tenant/workflow ownership, retaining one writer/proposal stream per
workflow and atomic shared credit/attention reservations. These are proposed
next steps, not implemented or measured ten-times capacity. A vector store or
queue does not remove the observed SQL/retention costs.

At unchanged measured throughput, ten times live ingestion alone would require
about 715 seconds/day, before decision work. Thus this result does not support
a ten-times claim under the same ten-minute budget. The database also logged
frequent WAL checkpoints with its default `max_wal_size=1GB`; disk/WAL sizing
needs measurement alongside CPU and query plans before adding workers.
