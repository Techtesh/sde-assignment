# First load attempt: failed, retained

Run ID `load03`, schema `load03_clean_86aaf0`, external harness directory
`runs/load03_clean_9a45878b`. The controller used implementation commit `18e3e82`
with 3 CPU/6 GiB limits; PostgreSQL used 1 CPU/2 GiB. The simulator was external.

This is **not** a completed load benchmark. All 5,537,379 advertised history
events in 23 chunks committed, but no full controller tick completed. Around
13 minutes after controller startup, the first experiment's affected-lead query
lost its database connection. PostgreSQL 17.11 logged its backend dying with
signal 11 (segmentation fault), terminated its other sessions and recovered
automatically from WAL. Docker reported `OOMKilled=false`. No experiment or
proposal row survived the failed transaction. The harness then stopped its world.

Selected database log, 2026-11-08 UTC:

```text
10:47:48.277 server process (PID 51816) was terminated by signal 11: Segmentation fault
Failed process was running: WITH active AS MATERIALIZED (...) ... SELECT l.features,count(*) ...
10:47:48.278 terminating any other active server processes
10:47:53.573 database system is ready to accept connections
```

The same retained query subsequently succeeded with JIT off (6.767 seconds) and
on (6.625 seconds). An `EXPLAIN ANALYZE` also succeeded: 7.425 seconds, including
2.279 seconds compiling 49 JIT functions. See
[load_reach_query_plan.json](./load_reach_query_plan.json). **The backend crash's
root cause was not isolated; these results do not prove JIT caused it.** Production
follow-up needs a server core dump/reproducer and database investigation.

The final controller disables JIT in its own PostgreSQL sessions to remove
repeated compilation overhead; it does not change the shared server's global
configuration. PostgreSQL documents that compilation can cost more than it saves
for short queries, and that `jit=off` prevents it at plan/execution time:
[official JIT guidance](https://www.postgresql.org/docs/17/jit-decision.html).
This is a measured performance choice and defensive runtime setting, not a claim
to have fixed a PostgreSQL defect.

An independent ingestion finding was reproducible during this attempt: large
chunks sorted JSONB for duplicate checks and could join against all prior events,
with sampled statements taking over 13 seconds and spilling temporary buffers.
The final ingestion path first checks narrow IDs, compares payloads only when
IDs repeat, skips prior-event comparison only when the actual minimum input ID
exceeds the committed maximum, and skips redundant DISTINCT for a unique chunk.
Identical repeats still deduplicate and conflicting repeats still roll back.
Two focused tests add same-chunk identical/conflicting cases; existing cross-chunk,
transaction and abrupt-exit tests remain applicable. No event-ID set or raw-event
list is retained in Python, and no dependency/service was added.

The fresh completed rerun and its resource/timing limits are reported in
[LOAD.md](./LOAD.md). No before/after speedup is claimed from this failed world.
