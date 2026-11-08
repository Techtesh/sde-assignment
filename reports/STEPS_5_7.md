# Added Steps 5–7: delivery evidence

Steps 5 and 6 and the local Step 7 work are complete. External submission is
pending reviewer identity, submission-form URL, deadline, author name and actual
hours. No reviewer access, form submission or public publication is claimed.
The user's original [work plan](../WorkPlan.md), including the added requirements,
remains a byte-for-byte prefix; completion notes are appended separately.

## What changed

- New experiments retain 10% control after a governed 90% promotion, with stored
  lift/version/time, matched daily and fixed 48-hour monitoring, and separate
  first/repeat exposure. Existing plans keep their declared rules.
- Prompt repair tries the supported previous prompt before paid suggestions,
  validates at n=500, always obtains approval, records supervisor attribution,
  and verifies/reopens the incident. Alerts are visible locally; no external
  notification delivery is claimed.
- Ingestion maintains typed campaign, conclusion and person evidence atomically.
  Learning avoids raw-call JSON queries. Unknown event types roll back the chunk.
- The concise status CLI reports lag, proposals, experiments, incidents, credits
  and actionable page/ticket suggestions. Exact-version audit queries disambiguate
  multiple changes at one simulated timestamp.
- The real launcher supports cProfile; the shared external harness supports five
  abrupt exits, restart comparisons, resource limits and fresh-checkout runs.

No new dependency or service was added. See the [submission](../SUBMISSION.md)
for scope, assumptions, six policy-checked stakeholder replies and running steps.

## Verification and version boundaries

The final focused PostgreSQL-backed suite passed **118 tests** on Windows
Python 3.14.2 (29.97s) and Linux Python 3.12.16 (32.70s). This includes an
interruption after a decay conclusion but before restore intent. The last
source correction, `4f2e65d`, retains that conclusion before consuming its
checkpoint; full scenario artifacts below predate this correction.

With `TEST_DATABASE_URL` pointing to the local development PostgreSQL instance,
the focused command is:

```bash
python -m pytest -q -p no:cacheprovider tests/test_controller.py tests/test_governance.py tests/test_incidents.py tests/test_experiment_statistics.py tests/test_experiments.py tests/test_observability.py tests/test_person_evidence.py tests/test_prompt_repair_v2.py tests/test_holdout_decay.py
```

| Evidence | Version | Result |
|---|---|---|
| [Five-point crash matrix](./steps567_crash_final.json) | `3d83779` | Mid-ingest, after advance, after intent, after POST and after apply all restart to exit 0 and match clean signatures |
| [Fresh checkout](./steps567_fresh_clone.json) | `3d83779` | Linux `run.sh` completes all eight public_01 days from a fresh local checkout |
| [Final public_02 run](./steps567_public02_final.json) | `3d83779` | All ten days complete, five credits, no duplicate application |
| [Profiled public_03 run](./steps567_load.json) | `f594647` | All five days and 9,737,475 events complete within combined 4-CPU/8-GiB application quotas |
| [Three-decision rehearsal](./REVIEW_REHEARSAL.md) | `f594647` | Executed exact-version audit queries for caller rotation, prompt repair and inconclusive cleanup |

The matrix compares committed evidence/counters, semantic audit decisions and
remote approvals/config history. Recovery-only audit transitions may differ.
It demonstrates these boundaries, not database failover or every instruction-level
crash. No live public candidate qualified for promotion; synthetic lifecycle
tests exercise promotion/decay mechanics.

## Outcomes and limits

| Scenario | Applied: neutral / beneficial / harmful | Interpretation |
|---|---|---|
| [public_01](./public_01.md) | 8 / 1 / 1 | An inconclusive KYC cleanup removes a true small benefit |
| [public_02](./public_02.md) | 13 / 2 / 0 | Two incident repairs; prompt onset-to-apply remains 27h30m |
| [public_03](./public_03.md) | 16 / 4 / 2 | Two harmful inconclusive KYC cleanups; ten inconclusive and two unfinished trials |

The [load report](./LOAD.md) records **7,537.7 live events/sec**, **90.79 MiB
peak controller RSS**, **6m29s/day average including bootstrap**, and about
**8.69 GiB** of database tables/indexes/TOAST. Cold start plus D0 takes **13m40s**;
the maximum advance-plus-loop bound is **25.434s**. Neither a cold-start nor a
six-second tail guarantee is met. Profiling overhead is included. The simulator
is outside the controller-plus-database resource budget.

Ten times the same ingestion volume alone projects to about 1,114s/day before
decisions; this is not tested capacity. Exact-time person evidence grows with
calls despite the much smaller cohort cube. Query/statistic transfer, WAL,
retention and ownership need measurement before adding workers.

Earlier unsuccessful evidence remains visible: an unresolved
[database backend crash](./LOAD_ATTEMPT.md), an invalid
[reference input comparison](./INPUT_ANOMALY.md), and the
[pre-epoch-fix incident run](./steps567_public02_before_epoch_fix.md).
The [original milestone delivery](./DELIVERY.md) and
[original load report](./MILESTONE5_LOAD.md) are historical snapshots, not the
current results.

## Review and external handoff

Use the [operating guide](../docs/OPERATIONS.md) to reproduce tests, crash cases,
profiling and audit queries. The rehearsal contains executed commands, retained
answers and the likely review questions. The [status example](./status_example.txt)
and [detailed JSON](./status_example.json) show the final incident-run view.

The repository must remain private. Reviewer access and form submission require
the missing recipient/form details; author name and actual hours must be supplied
honestly. These external items remain unchecked in the work plan.
