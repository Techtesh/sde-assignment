# Verification reports

Start with [PR review follow-up](./PR1_FOLLOWUP.md) for the latest fixes and
[Steps 5–7 delivery](./STEPS_5_7.md) for the completed implementation and evidence.
The [submission](../SUBMISSION.md) records scope and six stakeholder replies.

| Current scenario evidence | Interpretation |
|---|---|
| [public_01 grade](./public_01.md) | One beneficial and one harmful change; no promoted voice winner |
| [public_02 grade](./public_02.md) | Two beneficial incident repairs, no harmful changes; slow prompt detection |
| [public_03 grade](./public_03.md) and [profile](./LOAD.md) | Full load complete; cold-start and tail limits remain |
| [Crash matrix](./steps567_crash_final.json) | Five real abrupt boundaries match a clean run |
| [Fresh checkout](./steps567_fresh_clone.json) | Full public_01 through the Bash launcher |
| [Review rehearsal](./REVIEW_REHEARSAL.md) | Three executed audit queries with evidence and likely questions |
| [PR startup API check](./pr1_startup_api.json) | Three real worlds, six launches, resumable default identities and preserved evidence |

Each artifact records its source version. The full grades/load/matrix predate the
PR follow-up; new startup regression evidence does not replace those measurements.

Earlier stages are retained in [foundation](./FOUNDATION.md),
[governance](./GOVERNANCE.md), [incidents](./INCIDENTS.md),
[experiments](./EXPERIMENTS.md), and the original
[milestone delivery](./DELIVERY.md). Files prefixed `step3`, `step4`, `milestone5`
or labelled `before_epoch_fix`/`invalid_reference` are historical evidence.
The unresolved [backend crash](./LOAD_ATTEMPT.md) and
[input anomaly](./INPUT_ANOMALY.md) remain visible.
