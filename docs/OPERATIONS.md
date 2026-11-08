# Operating the loop

The required entry point remains `./run.sh <SIM_URL>`. Install
[requirements.txt](../requirements.txt) first. The launcher uses the project's
PostgreSQL container unless `DATABASE_URL` points to an existing database.
Set `SIM_RUN_ID` for each new simulator world; reuse it on controller restart.
See [CONTROLLER.md](./CONTROLLER.md) for setup and restart constraints.

## One supervisor view

```bash
export DATABASE_URL='postgresql://controller:controller@127.0.0.1:55432/controller'
python -m controller status --run-id mine01
```

The default is a concise text view of backlog, tick duration, proposals/hour,
experiments, pending requests, incidents and credits. Add `--json` for the detailed
view containing shared cohort definitions, pickup/engagement by
workflow/cohort over the last 24 complete simulated hours, experiment plans and
results, pending proposals and their age, the last 20 changes, open incidents,
credits by workflow/status, and loop health. It works while the controller holds
its writer lock. It opens a repeatable-read, read-only transaction, does not
contact the simulator, and cannot advance time or apply a change.

Health includes the latest completed tick, its wall-clock age, stage timings,
committed chunk checkpoints, and the event backlog against the **last observed**
API state. This is not a live remote-backlog measurement when the controller has
stopped. New proposals/hour and audit transitions/hour have separate counts;
reconciling an approval is not a new statistical decision. Credit totals include
uncertain actions separately because their actual remote charge may be unknown.

The JSON includes actionable alert suggestions; it does not send pages or messages.
While unfinished, a tick older than 120 wall seconds suggests checking the process,
HTTP service and database, then restarting with the same ID. A prompt incident
requiring approval/review suggests a page; a caller incident or blocked experiment suggests
a ticket. Approved work within 30 simulated minutes of apply-by and three starts in
five wall minutes without simulated progress suggest pages. Incidents older than six
simulated hours and credits below the six-credit reserve suggest tickets. Each alert
includes the next inspection/reconciliation action. Finished runs do not emit stale-loop alerts. Initial bootstrap and an
intentionally paused development run need operator context. Production needs a
separate watchdog because a dead controller cannot report its own death.

Page in production for unsafe live prompts requiring intervention, overdue approved
safety changes, a sustained ingest backlog, failed database access, or a loop that
cannot complete its budget. Ticket low traffic, inconclusive tests, approver
rejections within policy, dwindling credit headroom, and non-safety cleanup conflicts.
These additional production policies are recommendations, not implemented routing.

## Explain a change from our database

```bash
python -m controller audit --run-id mine01 --workflow ks_cancel \
  --at '2027-01-07T17:00:00+05:30'
```

The command selects the latest recorded change at or before that time. It returns
the config-change event/actor, exact proposal and rationale, permission route,
approval ID and recorded decision events, proposal transitions, associated incident,
and new-version call outcomes over complete hours in the following 24 hours.
Later config versions and campaign-pinned old versions are excluded. The result is
observational: it does not attribute all subsequent changes to this treatment.
If multiple changes share that timestamp, add `--version N` to select the exact
configuration change. The rehearsal uses this to distinguish an approved caller
repair from an automatic experiment cleanup applied in the same simulated minute.
The API exposes approval IDs/status, not the human approver's name. Raw call events
also preserve which person/lead heard which variant and config version.

For verification schemas, set `PGOPTIONS='-csearch_path=<schema in report JSON>'`
alongside the normal database URL. PostgreSQL's schema is an external test-isolation
mechanism; the application still scopes every record by run ID.

## Recovery demonstration

[crash_test.py](../tests/crash_test.py) runs the matrix through the shared external
[verify_delivery.py](../scripts/verify_delivery.py) harness. It launches
the simulator CLI and accesses its world through HTTP. It never imports simulator
code or parses scenario truth. Each case gets a fresh world and retained database
schema. The clean and crash cases share a run ID to keep deterministic IDs comparable.

```bash
python tests/crash_test.py --scenario scenarios/public_01_dev.yaml \
  --label recovery01 --out reports/crash_recovery.json
```

The five `CRASH_AT` values are `mid_ingest`, `after_advance`, `after_intent`,
`after_post`, and `after_apply`. The controller calls `os._exit(137)` without
cleanup, then the harness restarts it with the flag removed. `mid_ingest` exits
during COPY, before the chunk transaction commits. `after_intent` exits after
the durable request state is saved. The last two exit after a successful remote
approval submission/config write but before the local acknowledgment is saved.
Leave `CRASH_AT` unset in normal operation; unknown values fail explicitly.

Each restarted world must finish and match the clean run's raw event fingerprint,
chunk checkpoints, metric counters, proposals, experiments/person counters,
incidents, config/approval events, remote approvals and configuration history.
Assertions reject repeated proposal IDs in remote applications or approval requests.
Extra recovery transitions in the append-only proposal audit are allowed and retained.
This demonstrates process exits, not a PostgreSQL disk-loss/network-partition test.
Paid suggestion/validation APIs have no documented idempotency mechanism: uncertain
results are held for review, as covered by incident tests, rather than charged again.

## Linux load reproduction

Build [Dockerfile](../Dockerfile) with `docker build -t formi-controller:milestone5 .`.
The harness's `--linux` option runs the real Bash launcher in that image, with
the repository mounted read-only. The simulator remains an external HTTP service.
On Docker Desktop, the container uses `host.docker.internal`; on native Linux,
the harness uses host networking to reach its localhost simulator/database.

```bash
docker compose up -d --wait postgres
docker update --cpus 1 --memory 2g --memory-swap 2g <postgres-container>
python scripts/verify_delivery.py --scenario scenarios/public_03_load.yaml \
  --label load03 --linux --profile --out reports/load_public03.json
```

Controller limit: 3 CPUs/6 GiB. PostgreSQL limit: 1 CPU/2 GiB, including its
page cache. Set memory-swap equal to memory to disallow additional container swap.
The application budget totals 4 CPUs/8 GiB; the external simulator
is outside that budget. These are cgroup limits, not dedicated bare-metal cores.
The harness measures wall time around controller execution, including bootstrap
and launcher startup. Simulator initialization, final comparison queries, grading,
image build, dependency downloads and database startup are outside that timer.

`--profile` captures standard-library cProfile in the run's `controller.prof` and
records its leading functions in the report JSON. The real launcher accepts
`CONTROLLER_PROFILE=/writable/path/controller.prof`; the Linux harness supplies a
separate writable evidence mount while source stays read-only. Profile overhead
is included in that run's timings. Default cProfile elapsed times include blocked
I/O; they are not a measurement of pure CPU time or database backend CPU.

Tick fields separate streamed HTTP wait/decode, JSON parse, residual ingestion
work, decisions and the preceding advance. `write_seconds` is the ingestion
remainder after stream wait/parse: it includes chunk discovery, Python validation,
serialization, COPY, SQL and commit, rather than pure disk time. Decision time
includes permission/API reads and writes. Linux `peak_rss_mib` is process peak RSS,
not the database/container page cache. The advance-plus-loop maximum is a conservative
wall-time event-to-decision bound under this synchronous simulator, not a production
latency distribution. In simulated time, decisions occur every 15 minutes; the
ingestion backlog is drained before learning. New config events created during a
decision are normally ingested at the next tick.

Never compare throughput from a run sharing the database with other tests as if
it were an isolated benchmark. Read [LOAD.md](../reports/LOAD.md) for the actual
hardware allocation, measured stage costs, bootstrap and steady-state results.
