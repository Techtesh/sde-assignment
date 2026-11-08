# Three decisions to explain from our store

These commands were executed against retained verification schemas. They use
controller records only. Full answers are linked below and indexed by
[rehearsal_cases.json](./rehearsal_cases.json). Set `DATABASE_URL` to the local
verification database. The API exposes approval IDs, not a named human identity.

## 1. Caller-ID rotation: a supported operational repair

```bash
export PGOPTIONS='-csearch_path=steps567_finalinc_clean_b96a70'
python -m controller audit --run-id steps567_finalinc --workflow ks_cancel \
  --at '2027-01-06T14:00:00+05:30' --version 3
```

[Actual answer](./rehearsal_caller_rotation.json): D2 connected 23/205 (11.2%),
versus D1's 63/195 (32.3%) and its own matched history 770/2,805 (27.5%).
Both exact one-sided p-values are below 0.01 (peer 1.94e-7, history 3.21e-8).
There were two completed-hour confirmations; one bad call was insufficient.
The change moved the affected cohort's D2 weight to a supported current peer.
Approval **apr_00003** authorized configuration **3**.

Version 3 has no call exposure: an experiment cleanup became version 4 in the
same minute while retaining the caller repair. This is why the query needs
`--version` and why a zero version-3 counter is not evidence that the repair
never ran. The linked incident verifies later effective caller settings:
400 dials, 71 connected, 37 engaged, zero flags in 15:00–16:00 IST, with
no detected material guardrail harm. That is observational recovery, not formal
non-inferiority or isolated causal lift.

## 2. Hallucination repair: permission and the remaining delay

```bash
export PGOPTIONS='-csearch_path=steps567_finalinc_clean_b96a70'
python -m controller audit --run-id steps567_finalinc --workflow ks_cancel \
  --at '2027-01-08T15:00:00+05:30' --version 10
```

[Actual answer](./rehearsal_prompt_repair.json): the recorded supervisor edit
installed P2 at D3 11:30, version 6; the previous observed prompt was P1,
version 5. The final confirming window has 7 flags/93 connected versus
32/1,608 historical connected: excess 5.54 percentage points, Fisher p=0.004245.
The incident validates the supported previous prompt at **n=500**, costing
**five credits**, with **val_00001**. No LLM suggestion is bought. Its proposal
explicitly says it reverses a supervisor edit; **apr_00007** authorizes version 10.

The next complete-hour version-10 exposure is 1,600 dials, 286 connected,
154 engaged, five flags. Incident verification uses the narrower post-apply
window: 1,200 dials, 214 connected, 122 engaged, four flags. It records recovery
and no detected material harm, not proof that validation guarantees engagement.

The weakness is real: onset-to-apply is **1,650 simulated minutes (27h30m)**.
Detection-to-apply is 120 minutes; most delay preceded the two qualifying windows.
The persisted windows explain it: D3 11:00 has p=0.00034, but the next window
has p=0.055; later positive hours are also followed by nonqualifying ones.
Even p=0.010089 does not pass the declared 0.01 threshold. D4 finally has two
successive positive hours. We fixed unrelated voice edits resetting the streak,
but did not weaken thresholds after inspecting hidden grade truth. A wider
prospectively calibrated window is future work; a rapid-response SLA is not met.

## 3. Inconclusive voice cleanup: the harmful trade-off

```bash
export PGOPTIONS='-csearch_path=steps567_finaldev_clean_67f3af'
python -m controller audit --run-id steps567_finaldev --workflow nw_kyc \
  --at '2027-01-08T13:00:00+05:30' --version 3
```

[Actual answer](./rehearsal_inconclusive_cleanup.json), with
[frozen evaluation](./rehearsal_cleanup_evaluation.json): primary pickup was
829/3,391 for control and 217/833 for challenger. Estimated difference is
+1.60 points, with bounds -1.73 to +4.93 points at the declared alpha 0.025.
The observed effect is below the eight-point minimum and its lower bound is
not positive. Engagement guardrail difference is +2.32 points, but its lower
bound is -4.94 points, failing the two-point non-inferiority margin.

The test is **inconclusive**, not a winner and not proof that the challenger
does nothing. The fixed plan restores the incumbent through **apr_00005**.
The grader labels that restoration harmful because it removes a true small
engagement benefit that the primary/guardrail rule did not establish. Do not
hide this cost or describe the cleanup as an empirically superior treatment.
Campaign pinning delays new-version exposure until the next day. Its first
complete hours show 237 dials, 69 connected, 44 engaged, zero flags; that
descriptive sample does not justify a causal comparison with the trial.

## Questions to practise

| Question | Answer to defend |
|---|---|
| Why this test/correction? | Rates have random denominators and repeated people. Person-clustered ratio uncertainty retains within-person covariance. One challenger, one final checkpoint, and per-workflow trial spending avoid unplanned repeated winner looks. Operational alarm/retirement rules have separate limitations. |
| What if the approver rejects it? | Never apply it. A prompt incident with fresh evidence moves to another candidate with a new intent ID, bounded credit/request limits and validation. Expired/lapsed/stale decisions cannot become permission. |
| Supervisor edits during apply? | Re-read the base, reconcile remote history first, preserve unrelated changes and invalidate stale full configs. Conflicting ownership requires review; a paid unknown result is not bought again. |
| What breaks at 10×? | Use the measured profile/throughput, include person/time-counter cardinality and WAL, then reduce decision-transfer/query cost and partition ownership. Do not claim a small cohort cube bounds the person evidence table. |
| What did you cut? | Welcome interactions, new cohort formation, person-level timing, caller exploration, cross-client transfer and a web/notification service. Permission, audit and restart evidence were retained. |
| Another week? | Calibrate detection power/delay prospectively, test continuously arriving traffic, investigate the database/input anomalies, add provider idempotency/identity/notifications, and prove database recovery. |

No live promoted-winner decay is claimed where no public candidate qualified.
Synthetic lifecycle checks exercise 90/10 promotion, two-day retirement, repeat
fatigue and governed rollback; these are mechanism tests, not public outcome lift.
