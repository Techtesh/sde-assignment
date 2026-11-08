# Governance client

The implementation in [governance.py](../controller/governance.py) is the single route to
configuration writes. [policy.py](../controller/policy.py) contains shared cohort matching,
config validation, effective distributions, policy routing, and conflict-aware rebasing.
The incident and experiment engines supply proposals; their state machines share this governance boundary.

## Planning a change

Detectors/experiments call `Governance.plan()` with a full proposed configuration,
a stable decision ID, the `base_version` used to prepare it, a summary, and a rationale identifying
their population evidence. A base mismatch fails instead of blessing a stale full configuration. Fetching
current workflow/config/state and computing proposal facts happen through HTTP and our database.
The method persists the proposal without sending it. Callers batch compatible changes into
that full configuration; a workflow may have only one active proposal.

The same decision ID and configuration return the same proposal ID. Reusing a decision ID
for a different intent fails. IDs are deterministic hashes of run ID and decision ID. The stored
body is immutable across retries. New decisions, including re-proposals, require new IDs.

Validation rejects unsupported dimensions/options, invalid distributions/cohorts, and schedule
entries outside business-owned hours. Auto-apply additionally requires enabled policy, all changed
dimensions allowed, and per-cohort total-variation shifts within policy. Cohort distributions inherit
from default; normalized weights are used for shift calculations. Otherwise a valid change goes
through approval. Prompt changes require a validation-run ID; the simulator verifies that evidence
belongs to the same prompt/workflow and meets its safety threshold. No LLM chooses a winner.

## Durable lifecycle

```text
planned -> submitted -> pending -> approved -> applying -> applied
              |           |          |
              +-- rejected / expired / lapsed / stale / blocked
```

Auto-apply follows `planned -> submitted -> applied`. Every state change appends evidence to
`proposal_audit` in the same transaction as the proposal update. Planned evidence includes the exact
body and governing policy snapshot. Request intent is committed before sending HTTP; errors and
uncertain outcomes remain recorded. `superseded` is available to retire an unapplied intent locally.

Every tick and restart checks remote configuration history and approval records **before** sending.
A remote history entry matching our proposal proves application even if its response was lost or a
supervisor subsequently edited the configuration. A matching remote approval proves submission.
A duplicate-ID response triggers reconciliation, never assumed approval. An unresolvable duplicate
is blocked rather than submitted repeatedly.

Network failures and 5xx stop the current execution with uncertain intent preserved. Restart discovers
what happened, then retries the same intent only if no remote record exists and the base is still
current. Other errors are retained as stale/lapsed/blocked outcomes; 402 is not retried blindly.
The loop may reconcile records after scenario completion, but does not send new writes then.

## Supervisor edits and re-proposals

A changed base version makes a pending intent stale. It is never applied over the new configuration.
`repropose()` requires an explicit fresh decision ID and rationale from the caller. It re-reads current
configuration and replays only the intended diff, preserving unrelated supervisor edits. A conflicting
change to the same setting fails and requires a new decision. Allocation distributions and schedule
objects are atomic for conflict detection. Prompt evidence must be supplied again.

Expired, rejected, and lapsed proposals are terminal; the client does not silently resubmit them. A
new proposal recomputes affected-lead counts, historical replay, and reach score and links its parent.
The later learning layer must re-evaluate statistical justification; governance cannot invent fresh
experiment evidence. Automatic experiment interruption will be added with the experiment engine.

## Attention and proposal facts

Non-urgent requests wait until approver hours in Asia/Kolkata. Urgent requests may be submitted
outside hours only when their TTL can survive the next approver window and configured maximum
latency; otherwise intent remains planned without consuming a request. The approver still decides
on its own schedule. Rolling 24-hour request limits
include both API-visible requests and locally uncertain submissions, deduplicated by proposal ID.
Where the limit exceeds one, non-urgent work leaves one request slot for incidents. Approved changes
are applied promptly before `apply_by`; an already missed window is recorded as lapsed.

`affected_leads` estimates known nonconcluded leads within campaign lifespan whose effective settings
change. It excludes future uploads and can overestimate leads with no attempts remaining. The
impact score is **reach**: affected / known active leads, or zero with no known active leads. It is not
an expected improvement or a probability of success; urgency is tracked separately.

Dry runs replay observed historical rates for supported variants. Engagement is computed as projected
engaged/dials divided by projected connected/dials. Missing exposure yields an unknown estimate.
The record explicitly states observational/confounding and interaction limits; it does not fabricate
counterfactual lift, validation results, or experiment winners.

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

Approved-state evidence preserves the full approval response and decision timestamps; application
evidence records the response or matching config-history entry. The simulator exposes approval IDs
and decision times, rather than a named human identity. We preserve what the API supplies.
Join later call events/metrics by workflow, config version, and time to inspect post-change outcomes.

## Verify with real API calls

The opt-in test [test_governance_live.py](../tests/test_governance_live.py) requires a dedicated
fresh simulator, or one warmed only to D0 10:00 with no prior configuration changes/approvals:

```text
python -m sim serve --scenario scenarios/public_02_incidents.yaml --run-dir runs/governance-fresh --port 8701
```

```powershell
$env:TEST_DATABASE_URL = 'postgresql://controller:controller@127.0.0.1:55432/controller'
$env:GOV_SIM_URL = 'http://127.0.0.1:8701'
python -m pytest -q -s tests/test_governance_live.py
```

The test chooses routes/options from HTTP-visible policies, imports evidence into an isolated real
PostgreSQL schema, exercises auto-apply and human approval, intentionally loses an accepted approval
response, opens a new database session, and proves one submission/application. Test mutations are
protocol checks, not optimisation claims. They are not the full public_02 incident-response evaluation.
The test schema is dropped afterward; its assertions and output are the verification evidence.
