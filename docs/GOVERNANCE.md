# Governance client

[governance.py](../controller/governance.py) handles configuration writes for both incidents and experiments. [policy.py](../controller/policy.py) checks
cohorts, options, weights, permission and conflicting edits.

## Planning a change

An incident or experiment calls `Governance.plan()` with the proposed full configuration, decision ID, base
version, summary and evidence-backed rationale. The method reads current policy/configuration over
HTTP and computes proposal facts from the database. It saves the proposal without submitting it. A
changed base version causes an error. Callers must combine compatible changes before planning
because each workflow can have only one active proposal.

A run ID and decision ID determine the proposal hash. Repeating the same decision/configuration
returns the existing proposal; using that decision ID for another change fails. Retries reuse the
saved body. A new decision or re-proposal gets a new ID.

Validation checks supported options, cohorts, allocation weights and business-owned calling hours.
Automatic application also needs enabled policy, allowed dimensions and an acceptable
total-variation shift for every cohort. Shift calculations use normalized effective weights,
including defaults inherited by cohorts. Other valid changes need approval.

Prompt changes carry a validation-run ID. The simulator checks that the result belongs to the same
workflow/prompt and meets the safety threshold. Winner selection uses the statistical evaluator.

## Durable lifecycle

```text
planned -> submitted -> pending -> approved -> applying -> applied
              |           |          |
              +-- rejected / expired / lapsed / stale / blocked
```

Auto-apply follows `planned -> submitted -> applied`. Each proposal update and its `proposal_audit` entry commit together. The
initial record includes the request body and policy snapshot. Before an HTTP write, the client saves
the exact request. Later records hold the response or uncertainty. `superseded` retires an unapplied
local intent.

Before sending a request, the client checks remote configuration history and approvals. A matching
history entry establishes that the change applied, even if the response was lost or a supervisor
later edited it. A matching approval establishes submission. A duplicate-ID response triggers the
same checks. If the duplicate cannot be resolved, the proposal is blocked.

Network errors and 5xx responses stop that execution with the uncertain request saved. On restart,
the client checks remote records before retrying. It reuses the intent only when there is no remote
record and its base remains current. Other failures are recorded as stale, lapsed or blocked; a 402
does not trigger a blind retry. After scenario completion, reconciliation can update local records
but cannot send new writes.

## Supervisor edits and re-proposals

If the live base version changes, the proposal becomes stale. `repropose()` needs a fresh decision ID
and rationale. It reads current settings and reapplies the intended diff while keeping unrelated
supervisor edits. Changes to the same setting conflict. Allocation distributions and schedule
objects are checked as whole objects. Prompt validation evidence must be supplied again.

Expired, rejected and lapsed requests stay terminal. A caller can justify a new linked proposal,
which recomputes reach and the historical dry run. The learning code must reassess the evidence.
Governance cannot supply new statistical justification on its own.

## Attention and proposal facts

Routine requests wait for approver hours in Asia/Kolkata. Urgent requests can go outside those hours
only if their TTL survives the next window and maximum configured latency. Otherwise they stay
planned without using a request slot.

The rolling 24-hour count combines remote requests and uncertain local submissions, deduplicated by
proposal ID. When the limit exceeds one, routine work leaves a slot for incidents. Approved changes
must apply before `apply_by`; a missed window becomes lapsed.

`affected_leads` counts known, nonconcluded leads in active campaign lifespans whose effective settings
change. Future uploads are excluded; leads with no attempts left can make this an overestimate.
`impact_score` is affected leads divided by known active leads, or zero for an empty population. Urgency
is recorded separately.

A dry run reweights historical results for variants with observed exposure. Projected engagement is
projected engaged/dials divided by projected connected/dials. Missing exposure stays unknown. The
record includes the limits of historical comparisons and joint interactions.

## Audit from our own store

```sql
SELECT p.workflow_id, p.proposal_id, p.approval_id, p.route,
       p.body->>'change_summary' AS summary,
       p.body->>'rationale' AS rationale,
       a.ts, a.status, a.evidence
FROM proposals p JOIN proposal_audit a USING (run_id, proposal_id)
WHERE p.run_id = 'your-run' AND p.workflow_id = 'your-workflow'
ORDER BY a.ts, a.id;
```

The approved-state record includes the full API response and decision times. Application records
contain the response or matching config-history entry. The simulator supplies approval IDs, not
human names. Join subsequent calls by workflow, version and time to inspect what happened after the
change.

## Verify with real API calls

[test_governance_live.py](../tests/test_governance_live.py) needs a dedicated fresh simulator, or one advanced only to D0 10:00 with no prior changes
or approvals:

```text
python -m sim serve --scenario scenarios/public_02_incidents.yaml --run-dir runs/governance-fresh --port 8701
```

```powershell
$env:TEST_DATABASE_URL = 'postgresql://controller:controller@127.0.0.1:55432/controller'
$env:GOV_SIM_URL = 'http://127.0.0.1:8701'
python -m pytest -q -s tests/test_governance_live.py
```

The test reads policy/options and imports events over HTTP into an isolated PostgreSQL schema. It
exercises auto-apply and approval, discards a successful approval response, then recovers through a
new database session. It checks one submission and application per intent. These are protocol
checks; the full incident scenario is tested separately. The schema is dropped when the test ends.