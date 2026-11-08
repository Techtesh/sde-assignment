# Controller: ingestion and governance

For the consolidated supervisor view, audit command, alerts, process-exit evidence,
and Linux load reproduction, see [OPERATIONS.md](./OPERATIONS.md).

The controller ingests history/live events, detects population-based incidents, and reconciles
governed repairs before advancing time. It stores workflow/config snapshots, records decisions,
and reports pickup and engagement separately. It can rotate degraded caller IDs and obtain,
validate, propose, and monitor prompt repairs within a credit budget. It also runs governed voice
experiments with fixed checkpoints, guardrail evidence, promotion, and decay rollback. Read
[EXPERIMENTS.md](./EXPERIMENTS.md) for statistical/lifecycle rules,
[INCIDENTS.md](./INCIDENTS.md) for detector rules and credit/recovery
limits, [GOVERNANCE.md](./GOVERNANCE.md) for permissions, and [WorkPlan.md](../WorkPlan.md) for scope.

## Run

Install [requirements.txt](../requirements.txt), start the simulator using the commands in
[SIMULATOR.md](./SIMULATOR.md), then run `./run.sh http://127.0.0.1:8700`.
The launcher starts the project's PostgreSQL 17 container if `DATABASE_URL` is unset.
Docker Compose is required for that default; an external PostgreSQL database avoids Docker.
The local database uses development credentials and binds only to localhost.

For Windows or an existing database:

```powershell
docker compose up -d --wait postgres
$env:DATABASE_URL = 'postgresql://controller:controller@127.0.0.1:55432/controller'
python -m controller --url http://127.0.0.1:8700 --run-id mine01
```

Use the **same run ID** to restart a controller against the same running simulator.
Use a **fresh run ID** when starting a new simulator world. `SIM_RUN_ID` sets the launcher's
run ID; its default is `default`. Backward simulated time, a changed scenario, conflicting
event contents, and a decreasing event counter fail rather than corrupting existing evidence.
The simulator API has no unique world ID; matching restarted worlds cannot always be distinguished,
so assigning a fresh run ID is the operator's responsibility.

`--max-ticks N` stops after N advances for development. `--max-ticks 0` imports outstanding
history/events and reconciles existing proposals without advancing time; approved changes can
still apply while the scenario is running. Restart without this option to finish the scenario.
`--sequential-testing` is reserved and currently fails explicitly; its default is false.
`--observe-only` disables incident/experiment work, configuration writes, and paid calls while retaining
ingestion and read-only governance reconciliation. Use it for an explicit no-op comparison.

## Recovery and storage

Only one controller may hold a run's PostgreSQL session advisory lock. Ingestion streams one
chunk into a temporary table with `COPY`, inserts only unseen event IDs, and updates leads,
hourly metrics, audit records, and chunk completion in one transaction. A failed stream or
process exit before commit leaves the chunk unprocessed. A committed chunk can be skipped
on restart. Separate history/live chunk cursors avoid skipping globally numbered chunks.

Ingestion checks narrow IDs before comparing duplicate payloads. It skips the prior-event
comparison only when every actual input ID is newer than the committed maximum; overlaps still
receive the full equality check. Unique chunks avoid DISTINCT sorting. Controller database sessions
disable JIT compilation; the measured load findings and unresolved server crash are recorded in
[LOAD.md](../reports/LOAD.md) and [LOAD_ATTEMPT.md](../reports/LOAD_ATTEMPT.md).

Raw events preserve person IDs and lead features for future clustered analysis. Hourly metrics
retain workflow, config version, cohort, and observed voice/caller-ID/prompt dimensions;
the `all` dimension is the unduplicated workflow total. Lead and call events are stored in
`events`; campaign/config/approval events additionally appear in `audit_log`.

Reads retry transient failures up to three attempts. Time advances are never blindly retried:
an uncertain mutation stops the process, and startup reads current state and discovers chunks.
Malformed data, missing lead joins, bad counts, and conflicting event IDs roll back the chunk.

Example queries (substitute the run ID):

```sql
SELECT workflow_id, ts, kind, actor, evidence
FROM audit_log WHERE run_id = 'mine01'
ORDER BY ts, event_id;

SELECT workflow_id, history, sum(dials) AS dials,
       sum(connected)::numeric / NULLIF(sum(dials), 0) AS pickup_rate,
       sum(engaged)::numeric / NULLIF(sum(connected), 0) AS engagement_rate
FROM hourly_metrics WHERE run_id = 'mine01' AND dimension = 'all'
GROUP BY workflow_id, history ORDER BY workflow_id, history;
```

## Verify

```powershell
$env:TEST_DATABASE_URL = 'postgresql://controller:controller@127.0.0.1:55432/controller'
python -m pytest -q tests/test_controller.py
```

Database tests use isolated schemas and require real PostgreSQL; they skip explicitly if
`TEST_DATABASE_URL` is absent. HTTP and loop tests do not require a running simulator.

Run the governance regression checks with the same real database:

```powershell
python -m pytest -q tests/test_controller.py tests/test_governance.py tests/test_incidents.py tests/test_experiment_statistics.py tests/test_experiments.py
```

To independently check an already completed observation-only run through HTTP:

```powershell
$env:LIVE_SIM_URL = 'http://127.0.0.1:8700'
$env:LIVE_RUN_ID = 'foundation01'
python -m pytest -q -s tests/test_live_api.py
```

This re-reads every chunk through HTTP, compares event/lead/audit/KPI counts with PostgreSQL,
and restarts the controller to verify zero duplicate ingestion and unchanged simulator state.

Completed foundation results and reproduction commands are in
[reports/FOUNDATION.md](../reports/FOUNDATION.md). On Windows, pass `-X utf8` when running
`python -m sim grade` so the simulator can write its Unicode report without changing its code.
