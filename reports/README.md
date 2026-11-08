# Review evidence

These files support the deliverables in the assignment README. Design, scope,
stakeholder replies and audit examples are in [SUBMISSION.md](../SUBMISSION.md).

| File | Purpose |
|---|---|
| [public_01.md](./public_01.md) | Final development-scenario grade |
| [public_02.md](./public_02.md) | Final incident-scenario grade |
| [public_03.md](./public_03.md) | Final load-scenario grade |
| [LOAD.md](./LOAD.md) | Resource limits, stage timings, memory, database size, profile and 10× analysis |
| [steps567_load.json](./steps567_load.json) | Measured load data and cProfile summary supporting those numbers |
| [steps567_crash_final.json](./steps567_crash_final.json) | Five forced exits and completed restarts, each matching the clean run |
| [steps567_workflow_policies.json](./steps567_workflow_policies.json) | HTTP policy snapshot used to check the stakeholder claims |

The crash matrix and public_01/public_02 runs used `3d83779`; the profiled public_03
run used `f594647`. They predate the later checkpoint-ordering and CLI fixes.
The submission records the separate regression checks; these reports have not
been relabelled as runs of newer code.

[OPERATIONS.md](../docs/OPERATIONS.md) gives reproduction commands. Earlier runs
and development reports are available in Git history. Unresolved failures and
three audit examples are summarized in the submission.
