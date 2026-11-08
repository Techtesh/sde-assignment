# Step 1 API gate and step 2 governance verification

## Step 1: passed before implementing step 2

The opt-in [live API check](../tests/test_live_api.py) used the completed public_01 simulator
on port 8700 and the controller's `foundation01` PostgreSQL run. It independently read:

- `/health`, `/sim/state`, `/workflows`, each current config and config history;
- history/live chunk lists and all 393 NDJSON chunks;
- all 297,024 events, tallying call outcomes independently of controller helpers.

Raw event, lead, audit, and separate KPI/hallucination totals match PostgreSQL. Config snapshots
match the API. Restarting the controller ingests zero new events, leaves row counts unchanged,
and leaves the simulator's state unchanged. Initial live check: **1 passed in 4.00 seconds**.
The same check also passes after governance integration.

## Step 2: passed

Implemented in [governance.py](../controller/governance.py), [policy.py](../controller/policy.py),
and the existing [store](../controller/store.py), with persistent proposal/audit tables.
The loop now reconciles pending governance work before advancing time. No optimisation strategy
generates proposals yet, so an empty proposal queue remains observation-only.

Final regression run:

```text
python -m pytest -q tests/test_controller.py tests/test_governance.py tests/test_live_api.py
47 passed in 8.27s
```

This includes 16 controller tests, 30 governance tests, and the step 1 live API check. Real PostgreSQL
tests ran with `TEST_DATABASE_URL`; the live check used `LIVE_SIM_URL`/`LIVE_RUN_ID`. No included tests
were skipped. Covered failure cases include:

- Lost submission, auto-apply, and apply responses; request failure before reaching the remote.
- Intent committed before network calls and restart reconciliation before retries.
- Duplicate proposal IDs, including an unresolvable duplicate that blocks instead of retrying forever.
- Supervisor edits, stale approvals, conflict-aware explicit re-proposal, and fresh proposal IDs.
- Rejection, expiration, lapse, missed apply windows, approver hours, and reserved incident attention.
- API-visible external requests counted alongside uncertain local requests for fatigue limits.
- Invalid options/weights, effective cohort inheritance, normalized total-variation shifts, prompt evidence.
- 402/403/409/410/422 handling and uncertain 5xx outcomes.
- No new writes once the simulator finishes; fixed-checkpoint/sequential-flag behavior remains unchanged.

## Fresh simulator API smoke test

The [live governance test](../tests/test_governance_live.py) used a separate public_02 simulator
on port 8701 and an isolated real PostgreSQL schema. It obtained policies and options only through
HTTP and imported history/live evidence through HTTP.

```text
python -m pytest -q -s tests/test_governance_live.py
{"step2": "passed", "auto_apply_count": 1, "approval_apply_count": 1,
 "lost_response_reconciled": true, "duplicate_requests": 0,
 "duplicate_applications": 0, "credits_used": 0}
1 passed in 18.48s
```

The client deliberately discarded one successful `/approvals` response after the real server accepted
it. A new PostgreSQL connection/controller session recovered the pending approval, waited for the
simulated human decision, and applied it. Approval lists and config history prove one request and
one application per intent. The separate auto-apply path also produced exactly one config change.
These are two additional protocol-test changes, not learned winners or an optimisation result.
The test schema is dropped afterward; the test assertions/output are the retained verification.

Total new verification: **48 passing checks**, across the regression and dedicated live API runs.

The first live attempt exposed an expensive affected-lead query after loading history. Its shared
event subsets are now materialized once. The final real-API run completed in 18.48 seconds; this is
protocol-test duration, not a load-scenario throughput benchmark.

## Reproduce and inspect

See [controller setup](../docs/CONTROLLER.md) for database configuration and step 1 verification,
and [governance guide](../docs/GOVERNANCE.md) for the fresh simulator command, test environment,
state-machine behavior, proposal facts, and audit query.

## Limits

No incident detector, experiment engine, automatic statistical re-evaluation, or credit-consuming
prompt repair has been built yet. Compatible changes are batched by the caller into a full proposed
configuration; the client does not synthesize or merge independent decisions. Re-proposal deliberately
requires fresh caller intent. The full public_02 scenario evaluation and public_03 load benchmark remain
for later milestones. The simulator does not expose named approvers; we retain its approval IDs,
decision timestamps, and complete responses without inventing an identity.
