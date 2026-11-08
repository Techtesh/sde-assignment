# Voice experiments

[experiments.py](../controller/experiments.py) controls one prospective voice experiment per workflow.
[statistics.py](../controller/statistics.py) implements pure fixed-look inference. SQL persistence is in
[store.py](../controller/store.py); all config mutations still go through governance. No new dependency
or LLM call is required.

## Scope and declared plan

Use one existing cohort with the largest historical dial population, including `default`. Its current
voice distribution must have one incumbent. Do not overwrite a client's existing voice mixture to
start a test. Automatic language-cohort creation, welcome-message tests, and interactions are deferred.

| Setting | Rule |
|---|---|
| Challenger | One available untried voice, stable ID order; no hardcoded successful IDs |
| Initial exposure | 20% challenger / 80% incumbent, only in the selected cohort |
| Start | First actually observed call with the authorized config version and cohort |
| Winner checkpoint | Exactly 72 simulated hours after that start |
| Primary minimum effect | Observed lift at least 8 percentage points, with lower confidence bound above zero |
| Guardrail | Lower confidence bound above the workflow's negative absolute drop margin |
| Population floor | At least 100 contributing people per arm for both metrics; planned primary sample target |
| Promotion | 80% challenger / 20% retained incumbent control, with permission |
| Safety | Scheduled hourly population checks; never an early winner decision |
| Decay | Fresh 24-hour post-promotion windows against retained concurrent control |

Before sending the split proposal, persist the cohort, context, arms, shares, KPI/guardrail, sample
target, stopping/start rules, alpha, and rule version. The primary sample target is a working 80%-power
calculation from historical rate, 8-point effect, and 20/80 split, with a floor of 200 observations per
arm. It does not guarantee power under clustered calls; final measured uncertainty is decisive.

The start rule handles approval latency and `next_campaign_only`: old campaign calls are excluded until
the permitted epoch actually appears. An unapproved or never-exposed arm provides no learning evidence.
The chosen horizon is outcome-independent. Insufficient data at the checkpoint is **inconclusive**;
it is not extended until significance. At scenario finish, incomplete work is recorded as `unfinished`
without an early winner or a late config write. Avoid starting trials with less than 72 hours remaining.

## Statistical decision

Pickup is connected/dials; engagement is engaged/connected. Never blend them. Use the workflow's primary
KPI for improvement and its other KPI for non-inferiority. Improvement must pass both its minimum
observed effect and positive lower bound. That lower bound establishes improvement above zero, not
an 8-point guaranteed effect. Guardrail evidence is mandatory; absence of significant harm is not enough.

Group actual exposure by stable person ID and arm. For a ratio Y/N, a person's residual contribution
is `(Y_person - observed_rate * N_person) / total_N`. Subtract incumbent contributions from challenger
contributions, retaining covariance when the same person appears in both arms. Sum squared person scores
with G/(G-1) correction for the variance, then use one-sided normal bounds at the declared alpha.
Repeated people/campaigns do not masquerade as independent calls. Empty, sparse, boundary-rate, or
zero-variance cases remain inconclusive rather than producing zero-width confidence.

This is asymptotic cluster/delta-method inference, not an exact finite-sample guarantee. It assumes
independent people and stable prospective random assignment; returning people are handled within clusters.
The simulator assigns voices per call. This estimates rates under that call-level allocation, not a
person-randomized lifetime treatment effect. See the primary references on
[ratio delta methods](https://docs.statsig.com/experiments/statistical-methods/methodologies/delta-method) and
[cluster covariance](https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_cluster.html).

Trial i spends alpha `0.05 / (i * (i+1))` across the workflow's entire recorded trial history, including
changed contexts. These sum to at most 0.05. Testing one challenger at a time avoids simultaneous-arm
comparisons requiring Holm. Primary improvement and guardrail non-inferiority form an intersection rule.
This is a nominal per-workflow family budget, not a platform-wide or proven finite-sample bound.

## Safety and decay

Only a fixed final checkpoint can declare a winner. Early safety looks may stop a materially bad arm.
Each scheduled look has its own spending term; repeat ticks and restarts cannot create extra looks.
Across trials and two KPIs, hourly safety uses a separate nominal 0.01 budget with per-test alpha
`0.01 / (i*(i+1)*k*(k+1)*2)`. Decay windows have a separate budget of the same form. A sufficiently large
zero-success challenger population versus a supported control also triggers a declared operational stop;
it is not evidence for a winner.

While promotion waits for approval, measure a separate post-checkpoint phase for safety without changing
the frozen winner result. After promotion, start decay windows only when the promoted config is actually
observed. Each fresh 24-hour window compares the winner to its retained control, rather than averaging
old success into recent deterioration. Low-volume monitoring can be inconclusive.

Significant primary degradation (at least 2 points during decay) or guardrail harm requests rollback.
Permission still applies. For campaign-pinned configs, cleanup/rollback affects future campaigns; old
campaign exposure remains pinned until the business-owned campaign expires.

## Lifecycle, edits, and recovery

```text
planned -> running -> promoting -> monitoring -> restoring
              |                         |
              +---- inconclusive/lost --+

terminal: inconclusive / lost / interrupted / rolled_back / blocked / unfinished
```

The split, promotion, and cleanup are separate persisted proposals. Human rejection, expiry, lapse,
or stale bases never count as experimental evidence. Rejected promotion retires the completed split
through a cleanup proposal. Routine inconclusive cleanup is non-urgent and respects the reserved
incident-request slot; material safety stops and decay rollbacks are urgent.

Supervisor edits, objective changes, and incident repairs interrupt the current epoch. Never pool calls
across config versions. Cleanup changes only experiment-owned voice settings and preserves unrelated
prompt/caller/schedule changes and voice edits in other cohorts. A supervisor edit to the tested voice
itself is retained and recorded as a cleanup conflict. Failed/denied cleanup requires operator review.

Incident repairs take priority. A pending non-urgent experiment is superseded without adding its voice
change to a prompt repair. An already applied split is cleaned up separately after the urgent proposal
has reconciled. Compatible urgent caller/prompt repairs can still batch. Experiment preemption/links
and proposal intent commit atomically before external config writes.

`experiment_people` stores per-person/arm counts by phase. `experiment_windows` is their committed time
cursor. Each closed range is accumulated once in the same transaction as its cursor; replaying a tick
does not add calls twice. Raw events remain the audit source. Trial and promotion config versions are
recorded separately, and append-only experiment audit retains every earlier epoch/decision. Application
timestamps accept either API ISO timestamps or simulated-minute offsets (derived from API time, not
hardcoded D0). A restart preserves all phase state, fixed results, and testing budgets.

## Audit and validation

```sql
SELECT workflow_id, status, data->'plan' AS plan,
       data->>'started_at' AS started, data->>'checkpoint' AS checkpoint,
       data->'evaluation' AS decision
FROM experiments WHERE run_id='your-run' ORDER BY created_at;

SELECT e.workflow_id, a.ts, a.status, a.evidence
FROM experiments e JOIN experiment_audit a USING (run_id,experiment_id)
WHERE e.run_id='your-run' ORDER BY a.ts,a.id;

SELECT experiment_id,phase,voice,count(DISTINCT person_id),
       sum(dials),sum(connected),sum(engaged)
FROM experiment_people WHERE run_id='your-run' GROUP BY experiment_id,phase,voice;
```

The `--observe-only` switch disables new experiment work. `--sequential-testing` remains false by
default and rejects activation while its evaluator is deferred. See [verification](../reports/EXPERIMENTS.md)
for known-lift/null calibration, lifecycle tests, actual public outcomes, and limitations.
