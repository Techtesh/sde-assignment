# Controller: ingestion and governance

See [OPERATIONS.md](./OPERATIONS.md) for status, audit queries, crash tests and the Linux load run.

The controller reads historical and live events, checks for incidents, and processes approved
changes before advancing time. It stores workflow settings and decision records in PostgreSQL.
Pickup and engagement are measured separately.

It can rotate a degraded caller ID, validate a prompt repair and run a voice experiment. The details
are in [EXPERIMENTS.md](./EXPERIMENTS.md), [INCIDENTS.md](./INCIDENTS.md) and [GOVERNANCE.md](./GOVERNANCE.md). [SUBMISSION.md](../SUBMISSION.md#2-scope-decisions) lists the scope.

## Run

Install [requirements-lock.txt](../requirements-lock.txt), start the simulator as described in [SIMULATOR.md](./SIMULATOR.md), then run `./run.sh http://127.0.0.1:8700`.

When `DATABASE_URL` is unset, the launcher starts PostgreSQL 17 with Docker Compose. Direct CLI commands
use the same localhost development database, but you must start it yourself. Set `DATABASE_URL` to use
another database. The development service binds only to localhost.

Startup reports readiness on stderr and retries simulator health for up to 60 seconds, using short
HTTP timeouts. A wrong or auth-protected health URL fails immediately. If the server never becomes
ready, startup exits with a timeout message.

For Windows or an existing database:

```powershell
docker compose up -d --wait postgres
$env:DATABASE_URL = 'postgresql://controller:controller@127.0.0.1:55432/controller'
python -m controller --url http://127.0.0.1:8700 --run-id mine01
```

Without a run-ID flag, startup prints an ID and saves it against the simulator URL. Restart reuses
it, including after a lost advance response. A different scenario, backward time or event counter,
or a finished world becoming unfinished creates another namespace. Earlier evidence stays in the
database. A compatible old `default` run is adopted once. A session lock prevents two automatic
controllers from advancing the same URL.

`SIM_RUN_ID` or `--run-id` overrides that choice. Reuse an explicit ID on restart and change it for a
new world. Mismatched worlds and conflicting event contents cause an error.

The API has no unique world token. A reset that catches up beyond saved time and counters can look
like the old world; use a fresh explicit ID in that case. Status and audit use the printed ID and
read PostgreSQL without contacting the simulator.

Install [requirements-dev.txt](../requirements-dev.txt) to run tests. Pytest is kept out of runtime dependencies. The package lock was
checked on Linux/Python 3.12.16, and the controller suite also passes on Windows/Python 3.14.2.
Other Python/platform pairs have not been certified. Base image tags can still change.

`--max-ticks N` stops after N advances. With `--max-ticks 0`, the controller imports outstanding events and
reconciles proposals without advancing; approved changes can still apply. Add `--observe-only` to disable
configuration writes, paid calls and incident/experiment decisions. It still ingests evidence and
reconciles records.

Winner decisions use fixed checkpoints. Sequential testing has no CLI option.

## Recovery and storage

A PostgreSQL session lock allows one controller per run. Each chunk is streamed into a temporary
table with `COPY`. Unseen events, lead joins, counters, audit rows and the chunk checkpoint
commit in one transaction. A crash before commit leaves the chunk available to retry. Separate
history and live cursors handle their globally numbered chunks.

Duplicate checks compare IDs first. A chunk whose actual minimum ID is newer than the committed
maximum skips the old-event lookup. Overlapping IDs still get a full payload comparison, and
conflicting content rolls back the chunk. Unique chunks skip the extra DISTINCT sort. Controller
sessions disable JIT compilation. [LOAD.md](../reports/LOAD.md) records the measurements; [submission reliability](../SUBMISSION.md#9-reliability) describes the unresolved server crash.

The same transaction updates campaigns, concluded leads and person/voice counters at the exact event
time. Learning and reach queries use these tables. Raw events are kept for audit.

`qa_metrics` holds exact-time prompt/cohort counts for post-edit cumulative checks. It commits with
the chunk and has a one-time backfill marker for older runs. Detection windows save planned-look
results, including positive results waiting for incident creation.

Older runs build the derived tables once and commit an `evidence_ready` marker with them. An interrupted
backfill leaves no partial counters. Person/time rows can grow with call count; retention and
smaller sufficient statistics still need production work.

Raw events include person IDs and lead features. Hourly metrics group workflow, config version,
cohort and observed voice/caller-ID/prompt. The `all` dimension holds the workflow total
without double counting. Lead and call events go into `events`; campaign/config/approval events
also go into `audit_log`.

Reads make up to three attempts on transient failures. An uncertain time advance stops the process;
restart reads the current state and discovers outstanding chunks. Malformed events, missing lead
joins, bad counts and conflicting IDs roll back the chunk.

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

Database tests create isolated schemas in real PostgreSQL and skip when `TEST_DATABASE_URL` is absent. HTTP
and loop tests use controlled responses and do not need a running simulator.

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

This check reads every chunk over HTTP, compares event, lead, audit, KPI and hallucination counts
with PostgreSQL, then restarts the controller. It expects no duplicate ingestion or simulator-state
change.

[reports/README.md](../reports/README.md) indexes the final grades, load measurement and crash evidence. On Windows, `-X utf8` lets `python -m sim grade` write its
Unicode report without a simulator code change.
