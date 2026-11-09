# Operating the loop

Run `./run.sh <SIM_URL>` after installing [requirements-lock.txt](../requirements-lock.txt). Tests also need [requirements-dev.txt](../requirements-dev.txt). With no `DATABASE_URL`, the
launcher starts the project PostgreSQL container; direct commands use that same development URL but
do not start the database.

Startup prints a saved run ID for the simulator URL and reuses it on restart. Detected resets or
scenario changes get another namespace. If you set `SIM_RUN_ID`, keep it for restart and change it for
a new world. Setup and reset limits are in [CONTROLLER.md](./CONTROLLER.md).

Simulator health is retried for up to 60 seconds. Readiness messages go to stderr, so stdout can
still be read as JSON.

## Regression tests

Install [requirements-dev.txt](../requirements-dev.txt) and start the development PostgreSQL
service. On Windows:

```powershell
docker compose up -d --wait postgres
$env:TEST_DATABASE_URL = 'postgresql://controller:controller@127.0.0.1:55432/controller'
python -m pytest -q tests
```

On Linux, install the same test dependencies and run `python -m pytest -q tests` with
`TEST_DATABASE_URL` pointing to PostgreSQL reachable from that environment. Without this
variable, database tests skip. The two real-HTTP tests additionally need `LIVE_SIM_URL` /
`LIVE_RUN_ID` or `GOV_SIM_URL`; the governance check needs a dedicated fresh simulator and
changes its state. Windows skips the Linux Bash-launcher check.

Run Windows and Linux suites sequentially when they share a database. Per-test schemas
isolate tables, but run-ID and simulator-URL advisory locks span those schemas. Concurrent
suites can fail with an already-processing error even though their tables are separate.

The latest rerun passed 167 tests on Windows (three skipped) and 168 on Linux (two skipped).
[INGESTION.md](../reports/INGESTION.md) records the exact skips, saved evidence and remaining
full-scenario verification. Keep regression tests off the database during performance measurements.

## One supervisor view

```bash
export DATABASE_URL='postgresql://controller:controller@127.0.0.1:55432/controller'
python -m controller status --run-id mine01
```

The text view shows backlog, tick cost, proposals/hour, experiments, pending requests, incidents and
credits. `--json` adds cohorts, the last 24 complete simulated hours of pickup/engagement,
experiment plans/results, proposal ages and the last 20 changes. It works while the writer holds its
lock. The query uses a repeatable-read, read-only transaction and makes no simulator requests.

Health shows the last completed tick, wall age, stage timings and committed chunk checkpoints.
Backlog is measured against the last API state observed by the controller; it can be stale after the
process stops. Proposal creation and audit transitions have separate counts. The credit ledger
separates successful and uncertain charges.

Alerts are suggestions in the JSON; no message is sent. While a run is unfinished, a tick older than
120 wall seconds suggests checking the process, HTTP service and database before restarting with the
same ID. Prompt work awaiting approval/review is a page suggestion. So are approved requests within
30 simulated minutes of apply-by and three starts in five wall minutes without progress. Old
incidents (six simulated hours), credits below the six-credit reserve, caller incidents and ordinary
blocked experiments are ticket suggestions. Each has an inspection/recovery action. Finished runs do
not report stale-loop pages.

A slow initial bootstrap or paused development run needs operator context. Production needs an
external watchdog because a dead process cannot report its own failure.

For production, page on unsafe prompts, overdue approved safety changes, sustained backlog, failed
database access or a loop that misses its budget. Ticket low traffic, inconclusive trials,
policy-compliant rejections, low credit headroom and non-safety cleanup conflicts. These are
proposed operating rules; external routing is not implemented.

## Explain a change from our database

```bash
python -m controller audit --run-id mine01 --workflow ks_cancel \
  --end-time '2027-01-07T17:00:00+05:30'
```

The command finds the latest change at or before the supplied time. `--at` is still accepted.
Results include the actor, config version, proposal rationale, permission route, approval records,
incident and call outcomes from complete hours in the following 24 hours. Calls pinned to an older
config and later versions are excluded. Those outcomes describe exposure after the change; other
changes can still confound a causal comparison.

Use `--version N` when changes share a timestamp. In the rehearsal, that distinguishes caller repair
from experiment cleanup in the same minute. The API gives an approval ID/status, not a human name.
Raw events record the person, lead, variant and config version heard.

For a verification schema, set `PGOPTIONS='-csearch_path=<schema in report JSON>'` with the database URL. Schemas isolate test runs;
application records are also scoped by run ID.

## Recovery demonstration

[crash_test.py](../tests/crash_test.py) uses [verify_delivery.py](../scripts/verify_delivery.py) to start fresh simulator worlds and inspect them over HTTP. It neither
imports simulator code nor reads scenario truth. Each case keeps its own PostgreSQL schema. Clean
and crash cases use the same run ID so proposal IDs can be compared.

```bash
python tests/crash_test.py --scenario scenarios/public_01_dev.yaml \
  --label recovery01 --out reports/crash_recovery.json
```

The crash points are `mid_ingest`, `after_advance`, `after_intent`, `after_post` and `after_apply`. Each calls
`os._exit(137)`; the harness restarts with the flag removed. The ingest stop is during COPY before
commit. The intent stop follows the saved request. The last two follow remote success but precede
local acknowledgement. Keep `CRASH_AT` unset outside tests. Unknown values fail.

Every restarted run must finish with the same event fingerprint, checkpoints, counters, proposals,
experiments, incidents, config/approval events and remote history as the clean run. Duplicate remote
proposal IDs fail the check. Additional recovery transitions in the local proposal audit are
allowed.

This covers process exits. Database/disk loss and network partitions need separate tests. Paid APIs
lack result lookup/idempotency; uncertain paid calls stay on review hold rather than being purchased
again.

## Linux load reproduction

Build [Dockerfile](../Dockerfile) with `docker build -t formi-controller:milestone5 .`. The `--linux` harness runs the Bash launcher in that image with
source mounted read-only. The simulator stays outside the container. Docker Desktop uses `host.docker.internal`;
native Linux uses host networking.

```bash
docker compose up -d --wait postgres
docker update --cpus 1 --memory 2g --memory-swap 2g <postgres-container>
python scripts/verify_delivery.py --scenario scenarios/public_03_load.yaml \
  --label load03 --linux --profile --out reports/load_public03.json
```

The controller gets 3 CPUs/6 GiB and PostgreSQL 1 CPU/2 GiB, including page cache. Matching
memory-swap to memory prevents extra container swap. Total application limits are 4 CPUs/8 GiB; the
external simulator is outside that budget. Docker quotas do not reserve dedicated host cores.

The timer covers launcher startup and history bootstrap through controller completion.
Database/image setup, dependency downloads, simulator initialization, final fingerprints and grading
are outside it.

`--profile` writes cProfile data to the run's `controller.prof` and puts the leading functions in the JSON
report. The launcher also accepts `CONTROLLER_PROFILE=/writable/path/controller.prof`. The Linux harness mounts a separate writable evidence
directory. Profile overhead is included in wall time. cProfile elapsed time includes I/O waits and
cannot identify database CPU use by itself.

Tick timings separate HTTP stream wait/decode, JSON parsing, remaining ingestion work, decisions and
the preceding advance. `write_seconds` includes discovery, validation, serialization, COPY, SQL and
commit. Decision time includes governance/API requests. Linux `peak_rss_mib` measures the controller
process, excluding database memory and page cache.

The maximum advance-plus-loop time bounds event-to-decision wall time in this synchronous simulator.
It is not a production latency distribution. Decisions occur every 15 simulated minutes after the
backlog is drained. Config events created by a decision are normally ingested next tick.

Keep other controllers and database tests off the measurement service during a benchmark. [LOAD.md](../reports/LOAD.md)
records the measured allocation, stage costs, bootstrap and live-day totals.
