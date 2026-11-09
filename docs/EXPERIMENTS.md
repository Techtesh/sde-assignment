# Voice experiments

[experiments.py](../controller/experiments.py) runs one voice trial per workflow. [statistics.py](../controller/statistics.py) evaluates the results; [store.py](../controller/store.py) saves
evidence and progress. Configuration changes go through governance. Experiments need no LLM call or
extra dependency.

## Scope and declared plan

Choose the existing cohort with the most historical dials, including `default`. Start only when it
has a single incumbent voice. An existing client mixture is left alone. Automatic language cohorts,
welcome-message tests and interactions are outside this version.

| Setting | Rule |
|---|---|
| Challenger | One available untried voice, stable ID order; no hardcoded successful IDs |
| Initial exposure | 20% challenger / 80% incumbent, only in the selected cohort |
| Start | First actually observed call with the authorized config version and cohort |
| Winner checkpoint | Exactly 72 simulated hours after that start |
| Primary minimum effect | Observed lift at least 8 percentage points, with lower confidence bound above zero |
| Guardrail | Lower confidence bound above the workflow's negative absolute drop margin |
| Population floor | At least 100 contributing people per arm for both metrics; planned primary sample target |
| Promotion | 90% challenger / 10% retained incumbent control, with permission |
| Safety | Scheduled hourly population checks; never an early winner decision |
| Decay | Matched daily windows plus fixed non-overlapping 48-hour checkpoints |

Before proposing a split, save the cohort, context, arms, allocation, objective, sample target,
checkpoint, alpha and rule version. The working 80%-power calculation uses the historical rate, an
8-point effect and 20/80 allocation, with a floor of 200 observations per arm.

With `z = z(1-alpha) + z(0.8)`, the challenger target is `z²*p*(1-p)/(lift²*(1-share))`. Divide by `share` for total N. The control
is expected to receive `(1-share)/share` times the challenger population. Both observed arms must clear the
saved target, so the control floor is conservative at 20/80. This estimates power for primary
positivity with independent binomial observations. Clustering, the minimum observed lift and the
guardrail can lower the chance of declaring a winner.

Eight points is a high absolute lift requirement. It misses smaller useful effects in these runs and
can lead to restoring the incumbent after a genuinely beneficial but inconclusive trial. It was kept
after grading. A replacement rule needs calibration for traffic, precision, cleanup cost and
guardrail power.

Start the 72-hour clock at the first observed call using the authorized version. This handles
approval delays and `next_campaign_only`: old pinned calls are excluded. An arm with no authorized exposure
supplies no evidence. At the checkpoint, sparse results are inconclusive. The test is never extended
until significant. Scenario-end work is marked `unfinished`, and trials are not started with less than
72 hours left.

## Statistical decision

Pickup is connected/dials. Engagement is engaged/connected. The workflow's primary KPI must improve;
the other KPI must pass non-inferiority against its policy margin. A positive primary lower bound
and the minimum observed lift are both required. The lower bound establishes improvement above zero;
it does not establish an 8-point minimum true effect. The guardrail needs positive evidence of
non-inferiority.

Group calls by stable person ID and arm. For ratio Y/N, each person contributes `(Y_person - observed_rate * N_person) / total_N`. Subtract
control contributions from challenger contributions, keeping covariance when a person appears in
both arms. Sum squared scores, apply G/(G-1), then calculate one-sided normal bounds at the saved
alpha.

Repeating calls from one person does not create more independent people. Empty, sparse,
boundary-rate and zero-variance cases stay inconclusive.

The cluster/delta approximation assumes enough independent people and stable random assignment. It
accounts for repeated observations within a person, but the simulator assigns voices per call. The
estimate therefore concerns that call-level allocation, not a lifetime treatment assigned to a
person. The method does not give an exact finite-sample error guarantee. References: [ratio delta methods](https://docs.statsig.com/experiments/statistical-methods/methodologies/delta-method) and
[cluster covariance](https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_cluster.html).

Trial i uses alpha `0.05 / (i * (i+1))` over the workflow's recorded trials, including changed contexts. These
terms sum to at most 0.05. There is one challenger, so no simultaneous-arm Holm correction is
needed. Both primary improvement and guardrail non-inferiority must pass. The budget is nominal and
per workflow; it has not been proved as a finite-sample, platform-wide bound.

## Safety and decay

Only the fixed checkpoint can declare a winner. Hourly safety checks can stop a harmful arm earlier.
Each scheduled look has a separate budget term, saved progress prevents extra looks on restart, and
two KPIs share a nominal 0.01 budget: `0.01 / (i*(i+1)*k*(k+1)*2)`. Decay has a separate budget of the same form. A
large enough zero-success challenger population against a supported control also triggers an
operational stop.

Calls made after the final checkpoint while promotion awaits approval are checked for safety
separately; the winner result stays frozen. After promotion, monitoring begins with actual
promoted-version exposure. Each fresh 24-hour window compares winner and holdout calls from the same
period. Low traffic can leave the comparison inconclusive.

New `clustered-fixed-v2` plans save winner share and decay rules before exposure. Application records the
reference lift, version and time. Existing v1 plans keep their 80/20 split and original monitoring
rules on restart.

Daily checks use all, first and repeat exposure. First means a person's first call to that arm in
this experiment, including the trial; later calls are repeats. First plus repeat reconstruct all
outcomes. Person/time counters keep first-event outcomes even when calls share a timestamp.

Earlier outcomes affect who receives another call. The first/repeat split can reveal fatigue, but
clustered errors do not remove that selection bias.

Request rollback after two adequately sampled consecutive days below half the promotion lift. At
fixed non-overlapping 48-hour checkpoints, retire the winner if its primary lower bound is at or
below zero. That rule requires 200 primary observations, 100 people per arm and defined uncertainty
for both KPIs. A sparse holdout waits. Losing evidence of benefit can retire a small positive
effect; it does not prove decay.

Primary deterioration of at least 2 points or guardrail harm can also request rollback. The harm
budget is split across all/first/repeat and both KPIs. These retirement checks are separate from
winner-selection error control. All rollbacks still need permission. With campaign-pinned settings,
the change reaches future campaigns while old allocations last until their campaigns expire.

## Lifecycle, edits, and recovery

```text
planned -> running -> promoting -> monitoring -> restoring
              |                         |
              +---- inconclusive/lost --+

terminal: inconclusive / lost / interrupted / rolled_back / blocked / unfinished
```

Split, promotion and cleanup each have a saved proposal. Rejection, expiry, lapse and a stale base
provide no experimental evidence. A rejected promotion starts cleanup of the trial. Routine
inconclusive cleanup waits like other non-urgent work and leaves the incident slot free. Safety
stops and decay rollbacks are urgent.

A supervisor edit, objective change or incident repair interrupts the epoch. Results are kept
separate by configuration version. Cleanup restores only experiment-owned voice settings and keeps
unrelated prompt/caller/schedule changes and other cohorts' voice edits. A supervisor change to the
tested voice is recorded as a conflict. Failed or denied cleanup needs operator review.

Incidents take priority. Queued exploration can be superseded without adding its unapproved voice
change to a repair. An applied split is cleaned up after the urgent request is reconciled.
Compatible caller/prompt repairs can be batched. Proposal links, preemption and intent commit
together before configuration writes.

`experiment_people` holds per-person/arm counts by phase. `experiment_windows` records how far each phase has been
counted. The counts and cursor commit together so replay cannot add a range twice. Raw events remain
available for audit. Trial/promotion versions, earlier decisions and phase state are saved.
Application times can be API ISO timestamps or simulated-minute offsets derived from API time; no D0
timestamp is hardcoded. Restart reuses the saved checkpoint, result and budgets.

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

`--observe-only` disables experiment work. Winner decisions use fixed checkpoints; there is no
sequential-testing CLI option. [Statistical tests](../tests/test_experiment_statistics.py) cover null/known-lift cases; [lifecycle tests](../tests/test_experiments.py) cover promotion and rollback. Public outcomes are in [the submission](../SUBMISSION.md#11-results).