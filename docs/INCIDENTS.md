# Incident response

[incidents.py](../controller/incidents.py) detects incidents and manages repairs. [metrics.py](../controller/metrics.py) implements the population tests;
[governance.py](../controller/governance.py) handles configuration writes. The controller uses HTTP and its own database. It does not
read simulator source, hidden scenario data or run logs. Paid-endpoint response formats were checked
over HTTP.

## Detection

Caller-ID alarms still need two consecutive positive completed hours. Re-reading a bucket on
fifteen-minute ticks is not another confirmation. Missing or negative hours reset that streak.

After an observed prompt/cohort edit, QA counts calls cumulatively from the exact `config_changed`
timestamp. It checks at 1, 2, 4 and 8 hours, without needing consecutive positive hours. Exact-time
`qa_metrics` counters include only the current prompt and versions at or after the edit. Old pinned
campaigns are excluded; voice-only edits keep the anchor. History uses the same local clock
interval, including partial hours.

The early looks spend 0.004, 0.002, 0.001 and 0.001. Daily follow-ups at 24*d hours spend
`0.002/(d*(d+1))`, so an overnight or sparse edit stays under observation after eight hours.
Divide each amount across all configured cohorts plus default. The total is at most 0.01 for one
workflow/change epoch. Save the schedule, cohort set, counts, p-value, cutoff and result. An
unsupported look still consumes its slot. Restart neither retests it with newer data nor loses a
saved positive decision before incident creation.

Prompts with no observed edit keep the hourly fallback. That fallback and fresh-evidence checks
for retrying a denied repair are operational rules outside the post-edit discovery budget.
Existing incidents keep their repair state.

| Alarm | Minimum population | Comparison and threshold |
|---|---|---|
| Caller ID | 60 dials per live ID; 200 historical dials | Pickup down at least 3 percentage points versus its own same-hour/cohort history, and 2 points versus a supported current peer; both one-sided Fisher p <= 0.01 |
| Hallucination QA | 30 connected calls, at least 3 flags; 200 historical connected calls | Flags/connected elevated at least 2 points versus clock-matched cohort history; p must pass the saved look/cohort cutoff after an edit, or 0.01 in the hourly fallback |

A replacement caller ID needs both current exposure and history, without a supported decline of its
own. QA comparisons include the detector's usual false positives: a flag alone cannot establish that
a call hallucinated. Wilson intervals describe rate uncertainty, while decisions use exact
conditional count tests. No statistics dependency was added.

Alpha splitting uses the [Bonferroni inequality](https://online.stat.psu.edu/stat505/Lesson05):
if individual p-values are valid, the probability of any false rejection is at most the sum of
their levels. Nested looks can share observations. That does not make correlated calls or a
shifting historical mix independent binomial samples. This budget is nominal, per epoch, not a
production or whole-run guarantee. Tests cover healthy caller/QA populations and the whole early-look
rule. Small incidents can stay inconclusive. Off-hours edits need enough observed calls, and daily
follow-ups can be slow.

## Caller-ID repair

Move the affected cohort's weight from the degraded ID to a supported peer. Choose by observed
pickup, then ID for ties. When changing default, copy other cohorts' inherited distributions into
explicit overrides first. Existing unrelated overrides stay unchanged. The full shift goes through
policy or approval; it is never split into smaller changes to evade permission.

Skip the partial application hour, then verify over complete hours with at least 200 dials and 60
connected calls. A supported material engagement/guardrail decline creates a separate rollback
request that preserves unrelated edits. After rollback, the incident needs review. Failed remedies
and review holds survive restart and unrelated version changes so the same subject is not tried
repeatedly.

## Prompt repair

```text
detected -> suggested -> validated -> ready -> proposed -> monitoring -> resolved
                                         |                     |
                              approval failure/re-evaluation    +-> next candidate / review
```

1. Record the latest observed prompt edit, actor, version, time and previous stored prompt. The timing suggests a candidate cause; it does not establish one.
2. Try the previous prompt first if it has 200 historical connected observations in the affected cohort. Otherwise choose the best-supported historical alternative. Buy LLM suggestions only after that candidate fails or is denied. Filter unavailable, tried and originally unsafe prompts.
3. Validate candidates one at a time on 500 synthetic conversations. Check workflow, prompt, sample size, validation ID and pass rate. Use policy's threshold, or the documented 0.97 default. Existing incidents keep n=300.
4. Propose the first passing candidate with its validation result, diff, reach estimate, historical dry run and incident rationale. Validation tests safety; engagement still needs live evidence.
5. After approved application, measure QA and engagement on real calls. Check adequately sampled cohorts separately so a large cohort cannot hide harm in a smaller one. Compare pre/post live guardrails using conservative bounds on historical clock-hour ratios. This reduces morning/afternoon and existing caller-mix effects; missing matched references are reported. Require a one-sided Fisher p <= 0.05 and a 2-point observed QA reduction. Caller recovery uses the corresponding pickup comparison.
6. If safety does not improve or engagement materially worsens with enough evidence, try another candidate within budget. A known unsafe prompt is never restored just to recover engagement.

Verification reports no detected material harm when its checks pass. It does not establish
non-inferiority. Historical references, timing and selection can still confound these comparisons;
sparse or unknown populations stay unresolved. New supervisor edits supersede dependent work.

An urgent prompt repair can replace queued exploration and include a compatible caller-ID repair.
Save the replacement intent, retired proposals and incident links in one transaction. Reconcile any
uncertain submitted/applying write before proceeding.

Rejected, expired, lapsed or stale repairs get at most two fresh proposals, each needing current
alarm evidence, a new decision ID and a valid base. Rejected/expired prompt candidates are skipped
rather than purchased again. Every prompt change needs approval. Its summary states when it reverses
a recorded supervisor edit. The saved supervisor alert appears in status and the proposal queue; it
is not delivered externally. Detection-to-apply and detection-to-verified times are recorded. Failed
verification increments the reopen count.

## Credits, fairness, and ambiguous outcomes

- Keep 6 credits in reserve. New incidents may spend at most 18 credits: a previous-prompt validation, one suggestion and two more validations. Existing incidents keep 12.
- A suggestion costs 3 credits; n=500 validation costs 5. Buy suggestions only if at least one validation also fits above the reserve and within the tenant share.
- Divide initial spendable credits equally across API-visible tenants. Uncertain calls count against quotas. Unused shares are not borrowed.
- Make at most one new paid call per tick. Use saved tenant action order with stable ties so restart does not reset priority. Caller-ID repair spends no credits.
- Save paid-action intent before HTTP and successful results before changing phase. Restart can reuse a stored result.
- Transport, 5xx or parsing failures can leave a charge uncertain. The paid API has no result lookup or documented idempotency key. Save the action, emit `incident_needs_review` and stop retrying it. A new config epoch cannot bypass the hold. Known 4xx failures are also surfaced without a retry loop.

`needs_review` means a person must resolve the incident. It stays open while other workflows continue.

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

See [the final grades](../reports/README.md) and [incident tests](../tests/test_incidents.py) for results and failure cases. [Voice experiments](./EXPERIMENTS.md) run after incident handling
and keep separate epochs. [Crash evidence](../reports/steps567_crash_final.json) and [load measurements](../reports/LOAD.md) cover end-to-end checks. Only fixed-checkpoint winner
decisions are exposed; sequential testing is not implemented.
