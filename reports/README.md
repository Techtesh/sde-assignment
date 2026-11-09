# Review evidence

The scenario grades, full load profile, crash matrix and policy snapshot were regenerated
on 2026-11-09 from a fresh checkout of
`63d8c6ef546e810b859593336451d32b160c6ca4`. The controller Git tree is `e1fa57c374547592749eaf78b08d0e301e34ecf5`;
the SHA-256 over controller source/SQL, with LF line endings, is
`0ec34f8e51b4c039079c05ede3ca325d9670105e5b764cf1a7e74a2741eb3285`. The final documentation and live-test assertion changes
left that measured controller tree unchanged. The later staging-table reuse optimization has
separate replay measurements and regression results in [INGESTION.md](./INGESTION.md).
The full grades/profile, live API checks and five-case crash matrix have not been rerun after
that optimization. Their files retain the original source provenance.

Design, scope, stakeholder replies and audit examples are in [SUBMISSION.md](../SUBMISSION.md).

| File | Purpose |
|---|---|
| [public_01.md](./public_01.md) | Fresh development-scenario grade |
| [public_02.md](./public_02.md) | Fresh incident-scenario grade |
| [public_03.md](./public_03.md) | Fresh load-scenario grade |
| [LOAD.md](./LOAD.md) | Resource limits, bootstrap/live timings, memory, database size and profile |
| [steps567_load.json](./steps567_load.json) | Load measurements, profile summary and completion fingerprints |
| [steps567_crash_final.json](./steps567_crash_final.json) | Clean run plus five forced exits, all matching after restart |
| [steps567_workflow_policies.json](./steps567_workflow_policies.json) | HTTP workflow/policy snapshot from the fresh public_02 run |
| [INGESTION.md](./INGESTION.md) | Later staging-table reuse, replay measurements, latest test results and remaining verification |

Fresh no-op baselines were generated for all three scenarios. All scenario runs used the Linux
Bash launcher from the fresh checkout. The public_02 prompt repair took 345 simulated minutes
(5h45m), with two beneficial changes, no harmful changes and five credits spent.

The latest full PostgreSQL regression rerun passed 168 tests on Linux (two opt-in live
checks skipped) and 167 on Windows (those two plus one Linux-only check skipped).
The suites ran sequentially and their logs are in `runs/suite_rerun_20261109_162725`.
During the earlier scenario verification, two additional real-HTTP tests passed:
governance/lost-response recovery, and a complete event recount followed by restart.
The latter now selects the tick record after the startup identity message. These API tests ran
after the isolated load measurement. The crash matrix also compares cumulative QA counters and
saved detection windows, as well as decisions and remote approvals/config history.

The measured public_02 schema is `steps567_finalinc_clean_f9ef0b`; public_01 is `steps567_finaldev_clean_d96275`;
public_03 is `steps567_load_clean_7b8269`. Local logs and profiles remain in ignored
`runs/final_verify_b7441e2f`. [OPERATIONS.md](../docs/OPERATIONS.md) gives reproduction
commands. The submission records the remaining limits and three checked audit examples.
