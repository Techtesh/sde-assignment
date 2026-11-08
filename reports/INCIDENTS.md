# Step 3 verification

Implemented population alarms, caller-ID rotation, validated prompt repair, credit limits, and
post-apply monitoring. No simulator source/scenario truth was used by controller code. All controller
observations and mutations use HTTP; the documented baseline/grade CLI is external verification.
See [operating rules and limitations](../docs/INCIDENTS.md).

## Automated checks

```text
python -m pytest -q tests/test_controller.py tests/test_governance.py tests/test_incidents.py tests/test_live_api.py
67 passed
```

With real PostgreSQL enabled, this is 66 focused checks plus one independent live API check on the
completed public_02 run. No included database/live check is skipped. The live check re-reads all chunks,
compares raw event/lead/audit and separate KPI/QA counts with our database, and proves a zero-ingestion
restart without changing simulator state.

Covered: population floors, exact-test reference values, 500 healthy caller-ID population pairs,
500 healthy QA population pairs, completed-hour hysteresis, gaps, cohort overrides, human approval,
post-apply recovery, per-cohort harm hidden by pooled averages, governed rollback, stale base/races,
supervisor edits, credit reserves/tenant fairness/incident caps, uncertain charges, cached successful
responses, and review holds across config epochs. These seeded tests do not establish a production
whole-run false-positive rate. Editor diagnostics also report no errors in the implementation/tests.

## Healthy scenario

[public_01 grade](./step3_public01.md): eight days complete with **zero config changes, zero proposals,
zero credits, and identical outcomes to baseline**. Enabling the incident engine did not create repairs
on this healthy run.

## Incident scenario

[public_02 grade](./step3_public02.md): ten days complete. **Two changes applied, both beneficial**,
with two approved requests, no expiries/lapses/conflicts, and peak one request per workflow per 24 hours.
There are no unresolved incidents in this measured run.

| Kestrel KPI | Final rate | Relative change vs baseline |
|---|---:|---:|
| Leads concluded / uploaded | 0.285 | +15.2% |
| Pickup | 0.201 | +9.6% |
| Engagement among connected | 0.493 | +3.6% |

The grader reports **89 hallucinated calls versus 330 at baseline**. Other workflows were not changed;
their small KPI differences are not claimed as causal gains from this controller. Pickup, engagement,
and the business outcome remain separate quantities.

The degraded ID's share falls to 15.6% on its incident day (before permission/application), then 0% on
subsequent days. The prompt repair restores a historically observed alternative after safety validation;
neither an LLM nor validation pass-rate ranking selects an experiment winner.

## Timeline from our own store

Dates below are simulator dates; D0 is 2027-01-04. These are `incident_audit`/`proposal_audit` records,
not the simulator's logs.

| Incident | Detected | Proposed | Submitted | Applied | Recovery recorded |
|---|---|---|---|---|---|
| Caller-ID degradation | Jan 6 12:00 | Jan 6 12:00 | Jan 6 12:00 | Jan 6 12:45, apr_00001 | Jan 6 14:00 |
| Hallucination flags | Jan 7 19:00 | Jan 7 19:30 | Jan 8 00:15 | Jan 8 10:15, apr_00002 | Jan 8 14:00 |

The caller alarm follows two completed hourly populations. Post-apply evidence: 400 dials,
96 connected, 50 engaged. Prompt evidence after application: 1,200 dials, 269 connected,
127 engaged, 3 QA flags. Records explicitly say no detected material harm, not proven non-inferiority.

The prompt incident began Jan 7 11:30 according to the external grader; time-to-fix is **1,365 minutes
(22h45m)**. Detection took until 19:00, after the approver's window. The proposed request waited until
its 12-hour TTL could survive the next approver window. This avoids expiry but does not satisfy a fast
incident-response SLO. More powerful population aggregation and a client-authorized emergency policy
are follow-up work; bypassing governance is not an option.

Actual credit ledger:

| Time | Action | Cost | Result |
|---|---|---:|---|
| Jan 7 19:00 | Suggest fixes | 3 | succeeded |
| Jan 7 19:15 | Validate n=300 | 3 | succeeded |

Total **6/200 credits**, one LLM call, one validation run. Caller-ID repair uses no credits.
The separate endpoint-format probe used a different simulator world and is excluded from these numbers.

Query used to inspect permission/application:

```sql
SELECT p.body->>'change_summary' AS change, p.approval_id,
       p.created_at, p.submitted_at,
       min(a.ts) FILTER (WHERE a.status='applied') AS applied_at
FROM proposals p JOIN proposal_audit a USING (run_id,proposal_id)
WHERE p.run_id='step3_02_verified'
GROUP BY p.proposal_id,p.body,p.approval_id,p.created_at,p.submitted_at
ORDER BY p.created_at;
```

## Reproduce

Install requirements and start PostgreSQL as in [CONTROLLER.md](../docs/CONTROLLER.md).
Use fresh directories/run IDs for fresh simulator worlds:

```text
python -m sim baseline --scenario scenarios/public_02_incidents.yaml --run-dir runs/base_step3_02_verified
python -m sim serve --scenario scenarios/public_02_incidents.yaml --run-dir runs/step3_02_verified --port 8705
python -m controller --url http://127.0.0.1:8705 --run-id step3_02_verified
python -X utf8 -m sim grade --run runs/step3_02_verified --baseline runs/base_step3_02_verified --out reports/step3_public02.md
```

Set `DATABASE_URL` for the controller and `TEST_DATABASE_URL` for database tests. The independent live
check uses `LIVE_SIM_URL=http://127.0.0.1:8705` and `LIVE_RUN_ID=step3_02_verified` after completion.
The analogous healthy run uses public_01, port 8706, and the `step3_01_verified` run ID/directory.

## Limits and remaining work

Population tests are operational heuristics with correlated people/shared baselines and repeated looks;
neither the nominal p-values nor the observed grader lift establish a universal causal guarantee.
Verification uses observational historical references, so time/lead-mix effects remain possible.
Small populations and changed cohort definitions require caution. Uncertain paid calls deliberately
require review because this API cannot retrieve their result idempotently. Equal tenant quotas do not
borrow unused budget. The simulator supplies approval IDs/timestamps, not named approvers.

Voice experiments, formal winner selection/decay, public_03 load testing, full process-kill evidence
around incident actions, and the final submission remain later milestones. Existing abrupt-exit ingestion
and lost-write/paid-response recovery checks pass, but are not a substitute for that full final demonstration.
