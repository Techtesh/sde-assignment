# Incident response

[incidents.py](../controller/incidents.py) owns detection and repair progression.
[metrics.py](../controller/metrics.py) holds pure population/statistical rules; all config
writes remain inside [governance.py](../controller/governance.py). The controller reads no simulator
source, scenario truth, or run logs. LLM/validation response formats were verified through HTTP.

## Detection

Evaluate only completed hourly buckets. Fifteen-minute loop ticks reuse the same persisted window;
they do not count as independent confirmations. Require two consecutive positive hourly windows in
the same relevant epoch. Prompt/cohort changes reset QA persistence; unrelated voice
edits do not. Caller alarms retain their config epoch. Missing/negative windows break a streak. Persist counts, tests, subject,
cohort ID, episode start, and config version. Episode IDs and decisions are deterministic.

| Alarm | Minimum population | Comparison and threshold |
|---|---|---|
| Caller ID | 60 dials per live ID; 200 historical dials | Pickup down at least 3 percentage points versus its own same-hour/cohort history, and 2 points versus a supported current peer; both one-sided Fisher p <= 0.01 |
| Hallucination QA | 30 connected calls, at least 3 flags; 200 historical connected calls | Flags/connected elevated at least 2 points versus normal same-hour/cohort history, with one-sided Fisher p <= 0.01 |

Caller alternatives must have current exposure and history and must not themselves show a supported
decline. QA baseline includes the detector's usual false positives; a flag is not treated as proof
that one call hallucinated. Wilson intervals are available for rate uncertainty; decisions use
exact conditional count tests without adding a statistics dependency.

These are operational alarm rules, not experiment winner tests. Repeated testing, shared historical
baselines, and returning people prevent interpreting 0.01 as a whole-run false-positive guarantee.
Seeded tests cover 500 pairs of healthy caller-ID populations and 500 pairs of healthy QA populations.
The production false-alarm rate still needs broader calibration. Small populations can remain
undetected; historical cohort/time matching does not establish causality or adjust every lead feature.

## Caller-ID repair

Move weight from the degraded ID to the supported peer selected deterministically by observed
pickup, then ID as tie-breaker. Target the alarm's cohort. If default changes, materialize existing
inherited distributions on other cohorts so an unmeasured population is not changed accidentally.
Never overwrite an explicit unrelated override. The full shift goes through signed policy or human
approval; do not split a large change into small auto-applies to avoid permission.

After application, skip the partial application hour and measure complete subsequent hours.
Require 200 dials/60 connected calls for verification. A material supported engagement/guardrail
decline creates a separately governed rollback that preserves unrelated edits. Applied rollback
escalates the incident for review. A failed remedy/review hold is remembered across restarts and
unrelated config epochs instead of repeatedly trying the same failed subject.

## Prompt repair

```text
detected -> suggested -> validated -> ready -> proposed -> monitoring -> resolved
                                         |                     |
                              approval failure/re-evaluation    +-> next candidate / review
```

1. Record the latest observed prompt edit, actor, version/time and prior stored prompt.
   Attribution is temporal evidence, not proof of causation.
2. Validate the previous prompt first when it has 200 historical connected observations
   in the affected cohort; otherwise use the best-supported historical alternative.
   Buy LLM suggestions only after that candidate fails or is denied. Exclude unavailable,
   already-tried and originally unsafe prompts. This selects a hypothesis, not a winner.
3. Validate one candidate at a time on 500 synthetic conversations. Check response workflow, prompt,
   sample size, validation ID, and pass rate. Use the policy threshold, or the documented 0.97
   assumption if it is absent. Existing incidents retain their declared n=300.
4. The first passing candidate is proposed with validation evidence, exact diff, affected-lead estimate,
   historical dry run, reach score, and incident rationale. Validation measures safety, not engagement.
5. After permission/application, measure QA and engagement on real observed populations. Check
   adequately sampled cohorts individually; a large cohort cannot hide a smaller cohort's harm.
   Guardrail monitoring compares the pre-repair live population with post-repair observations,
   using conservative confidence bounds around the historical clock-hour ratio. This avoids
   attributing normal morning/afternoon changes or an existing caller mix to the prompt repair.
   Insufficient matched reference data is reported explicitly.
   Compare QA reduction with pre-repair evidence using a one-sided Fisher test at 0.05 and a minimum
   2-point observed reduction. Caller recovery uses the analogous pickup test.
6. If engagement materially degrades or safety fails to improve after enough observations, try the next
   candidate within budget. Never restore a prompt already known to hallucinate merely to recover engagement.

Verification records say **no detected material harm**, not proven non-inferiority. Comparisons are
observational, including a historical reference and temporal/selection confounding. Unknown or sparse
populations are not claimed safe. New supervisor edits supersede dependent work instead of being undone.

Higher-priority prompt repairs can replace queued work and batch a compatible pending caller-ID repair.
Replacement intent, proposal retirement, and incident links are committed together before any config write.
An uncertain submitted/applying write must reconcile first. Rejected/expired/lapsed/stale repairs receive
at most two new proposals and require fresh current alarm evidence, a new decision ID, and a valid base.
Rejected/expired prompt repairs move to the next candidate instead of rebuying the rejected
one. Every prompt change requires approval, including policies that would permit automatic changes.
The summary explicitly identifies reversal of a recorded supervisor edit. A durable supervisor
alert is visible in status and the proposal queue; no external message delivery is claimed.
Verification records detection-to-apply and detection-to-verified times; failed verification
increments the reopen counter before trying another candidate.

## Credits, fairness, and ambiguous outcomes

- Global reserve: **6 credits**; new incidents have an **18-credit** ceiling, enough for a
  previous-prompt validation, one suggestion and two further validations. Existing incidents keep 12.
- Suggestion cost: 3; validation cost: 5 for n=500. Do not start suggestions unless at least one validation
  can also be funded above the reserve and within the tenant share.
- Divide the initial spendable budget equally across API-visible tenants. Uncertain calls count as spent
  for quotas. Unused shares are not borrowed in this minimal implementation.
- At most one new paid call per loop tick. Schedule tenants by their durable last action ID, with stable
  ties, so restarts or a busy tenant cannot reset attention. History-supported caller repair spends no credits.
- Commit external-action intent **before** HTTP. Store successful responses before progressing phases;
  restart can reuse a stored response without buying it again.
- The paid API has no documented idempotency/retrieval mechanism. A transport, 5xx, or parse failure may
  have spent credits: retain the uncertain action, emit `incident_needs_review`, and do not blindly retry it.
  The same held subject cannot bypass this by moving to a new config epoch. Known 4xx failures are also
  surfaced, not retried in a tight loop.

`needs_review` is an explicit human escalation, not a claim that the incident was automatically fixed.
This is how exhausted/uncertain repairs stop safely while other workflows keep running.

## Audit

```sql
SELECT i.workflow_id, i.kind, a.ts, a.status, a.evidence
FROM incidents i JOIN incident_audit a USING (run_id, incident_id)
WHERE i.run_id = 'your-run'
ORDER BY a.ts, a.id;

SELECT p.workflow_id, p.approval_id, p.body->>'rationale' AS reason,
       a.ts, a.status, a.evidence
FROM proposals p JOIN proposal_audit a USING (run_id, proposal_id)
WHERE p.run_id = 'your-run'
ORDER BY a.ts, a.id;

SELECT tenant_id, incident_id, kind, cost, status, request, response
FROM external_actions WHERE run_id = 'your-run' ORDER BY id;
```

See [step 3 verification](../reports/INCIDENTS.md) and the public scenario reports for measured outcomes.
[Voice experiments](./EXPERIMENTS.md) now run after incident handling, with incident priority and
separate epochs. See [delivery evidence](../reports/DELIVERY.md) and
[load measurements](../reports/LOAD.md) for the completed verification. The
`sequential_testing` option remains false and rejects activation until implemented.
