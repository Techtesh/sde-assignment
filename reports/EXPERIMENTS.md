# Step 4 verification

Implemented fixed-checkpoint voice experiments, person-clustered inference, governed promotion,
retained control, safety stops, decay monitoring, and version-safe voice cleanup. Read
[EXPERIMENTS.md](../docs/EXPERIMENTS.md) for the declared rules and assumptions.

## Checks

```text
python -m pytest -q tests/test_controller.py tests/test_governance.py tests/test_incidents.py tests/test_experiment_statistics.py tests/test_experiments.py
93 passed
```

All database checks used real PostgreSQL, not a storage mock. Two additional independent
[live API audits](../tests/test_live_api.py), one per completed scenario, also pass. Each audit re-reads
HTTP event chunks, independently tallies outcomes, compares stored raw/config/KPI evidence, and
restarts the controller without new ingestion or changing simulator state: **95 passing checks total**.

Coverage includes fixed final decisions, no unauthorized-arm learning, campaign-pinned versions,
same-person covariance, non-inferiority, sparse/boundary cases, early safety stops, rejected promotion,
full restore, promoted-winner decay, queued incident priority, edit-preserving cleanup, timestamp forms,
lost responses, a fresh database session, and atomic aggregation/cursor rollback. The existing
`--sequential-testing` flag still rejects activation; no sequential winner test was introduced.

## Statistical calibration

Seeded simulation: 500 independent null replications, each with 600 people per arm and four perfectly
correlated calls per person. The person-clustered primary comparison reports 18/500 positive lower
bounds at nominal alpha 0.025 (3.6%; approximate 95% Wilson interval 2.29%-5.62%). The full decision
procedure, including minimum observed effect and guardrail evidence, reports **2/500 false winners**
(0.4%; approximate interval 0.11%-1.45%). The test allows binomial sampling uncertainty rather than
requiring an exact finite-simulation percentage.

A separate large-population known-lift case selects a winner with guardrail non-inferiority. Multiplying
each person's repeated calls by 100 leaves the clustered standard error unchanged. Lifecycle tests
then exercise real PostgreSQL and synthetic HTTP approval/application/decay responses. These are
controlled correctness checks, not proof of universal power or finite-sample false-positive control.

## Real public runs

No public-run candidate qualified for promotion. No statistical thresholds were weakened to force
a winner. The 72-hour horizon, 20% share, 8-point observed effect requirement, and tight 2-point
guardrails are conservative at this volume. One largest existing cohort is tested; no automatic
language partitioning was added to pursue hidden cohort effects.

| Result | public_01 | public_02 |
|---|---:|---:|
| Experiment records | 5 | 7 |
| Inconclusive after fixed checkpoint | 4 | 3 |
| Lost at checkpoint | 1 | 0 |
| Interrupted by edit/incident | 0 | 3 |
| Blocked permission | 0 | 1 |
| Promoted public winners | 0 | 0 |
| Credits used by entire controller | 0 | 6 |

The blocked public_02 trial was rejected before exposure. Interrupted trials do not pool subsequent
config epochs or count a rejected arm as learned evidence. Inconclusive trials restore the incumbent
through governance; they are not extended until significant.

### Public_01

[Full grade](./step4_public01.md): 10 applied changes (8 neutral, 1 beneficial, **1 harmful**), six approved
requests, zero expiries/lapses/conflicts, and zero credits. The harmful change was restoring the KYC
incumbent after an inconclusive trial: the grader knows its challenger had improved true engagement
by 1.4 points, but our evidence did not qualify it under the declared primary/guardrail rules. That
is a real cost of conservative inference, not a beneficial winner we claim to have discovered.

Separate aggregate reported changes: conclusion rate +0.4% relative, pickup -0.4%, engagement +1.1%.
These single-seed aggregate differences are not causal proof of experiment lift.

### Public_02

[Full grade](./step4_public02.md): 13 applied changes (11 neutral, 2 beneficial, **0 harmful**), five
approved requests and one judgement rejection, zero expiries/lapses/conflicts, and six credits
(one LLM suggestion, one n=300 validation). Both caller-ID and prompt incidents resolve in our store.
The degraded ID's share is zero from the next day onward.

Kestrel: conclusion rate 0.288 (+16.4% relative), pickup 0.202 (+9.8%), engagement 0.496 (+4.1%).
Hallucinated calls are 79 versus 330 baseline. Prompt time-to-fix is 300 simulated minutes. The
improvement is principally incident repair; no experiment winner was promoted. Effects on other
workflows or overall aggregates are not claimed as isolated causal treatment effects.

## Integration findings fixed

- Auto-applied config history returned a simulated-minute offset while other records may use ISO
  timestamps. Conversion uses API `ts`/`sim_minute`, not hardcoded simulator origin. The first exploratory
  run resumed from its persisted state after this fix; final reports use fresh worlds.
- Approval latency equal to an entire workday exposed a scheduling stall. Latency now elapses once,
  then the decision is moved into approver hours for TTL feasibility. A regression covers this policy.
- A prompt repair initially compared morning historical pickup with afternoon live pickup, generating
  unnecessary candidate switches. Monitoring now preserves the pre-repair live population and uses
  conservative bounds on a matched historical clock-hour ratio, per cohort. The final run resolves
  using six credits; earlier exploratory runs are not the reported results.
- Incident preemption retires a pending non-urgent experiment without adopting its unapproved voice
  change. Cleanup preserves prompt/caller/schedule edits and voice edits in other cohorts. Routine
  inconclusive cleanup is non-urgent, retaining the reserved incident attention slot.

## Reproduce

Start PostgreSQL and configure `DATABASE_URL` as in [CONTROLLER.md](../docs/CONTROLLER.md).
Use fresh run directories/IDs for a new world. The measured simulator commands were:

```text
python -m sim serve --scenario scenarios/public_01_dev.yaml --run-dir runs/step4_01_verified --port 8709
python -m sim serve --scenario scenarios/public_02_incidents.yaml --run-dir runs/step4_02_matched --port 8711
```

Run the matching controllers in separate terminals:

```text
python -m controller --url http://127.0.0.1:8709 --run-id step4_01_verified
python -m controller --url http://127.0.0.1:8711 --run-id step4_02_matched
```

The baselines are unchanged public_01/public_02 no-op runs from earlier milestones. Grade with:

```text
python -X utf8 -m sim grade --run runs/step4_01_verified --baseline runs/base_foundation01 --out reports/step4_public01.md
python -X utf8 -m sim grade --run runs/step4_02_matched --baseline runs/base_step3_02_verified --out reports/step4_public02.md
```

For each completed run, set `TEST_DATABASE_URL`, `LIVE_SIM_URL`, and `LIVE_RUN_ID`, then run
`python -m pytest -q tests/test_live_api.py`. Neither controller nor live audit reads scenario truth
or simulator run logs. External grading is the documented evaluation tool.

## Limits and remaining work

- Public promotion/decay is not demonstrated because no candidate qualified. The known-effect
  lifecycle tests cover those branches, including fresh post-promotion windows and permissioned rollback.
- The 8-point requirement and 72-hour window can miss smaller useful effects. Guardrail power is often
  limiting; insufficient evidence is intentionally inconclusive. Broader calibration and automatic
  language-cohort design would be separate changes, not threshold tuning to public hidden truth.
- Normal clustered intervals assume sufficiently many independent people. Call-level randomization,
  carryover, changing populations, and finite-sample calibration need further production evaluation.
- Old campaign-pinned allocations persist until campaigns expire, even after authorized cleanup.
  Denied/failed cleanup requires operator review; the client cannot bypass its permission boundary.
- Load-scenario measurement, the consolidated supervisor command, a full process-kill demonstration,
  and the completed submission remain step 5. Local development runtimes are not target-machine benchmarks.
