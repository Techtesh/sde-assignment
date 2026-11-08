# PR #1 review follow-up

The supplied review describes an older commit and did not execute the code.
Findings were checked against `518d72f` before changes. This report records the
current disposition without rewriting the original review or commit history.

## Findings

| Finding | Disposition |
|---|---|
| B1: implicit `default` collides across worlds | Fixed. Persist an automatic identity per HTTP URL, reuse it on restart, and isolate observed resets/scenario changes. Old evidence remains; compatible legacy `default` is adopted. Explicit IDs retain strict checks. |
| B2: missing allocation factor in sample planning | The existing return value is an arm target, not total N. Its formula is correct for that interpretation. Documented the derivation and tested implied one-sided primary positivity power at 10/90, 20/80 and 50/50. |
| B2: eight-point lift is conservative | Retained as a predeclared rule, with its low-power/cleanup costs explicit. It is not a claim that smaller gains are worthless. Changing it after public grading would require a new declared design and prospective calibration. |
| B3: 90/10 and decay plan not implemented | Already fixed by `89c55ef`: new plans use 90/10, daily half-lift and fixed 48-hour checks, with first/repeat exposure. Legacy plans preserve their original rules. |
| B4: approver-hours and TTL checks | Both are needed: one gates submission now, one checks future decision feasibility. Reused one timezone-normalized instant; added closing-boundary, exact-TTL and UTC-equivalence checks. Local/remote request IDs deduplicate across offsets. |
| B5: `concluded` means engaged-per-dial | Renamed to `engaged_per_dial`; pickup and conditional engagement remain separate. No metric behavior changed. |
| B5: literals and CLI size | Statistical policy values are recorded in plans/docs and restart unchanged. No generic settings layer or CLI refactor was needed to correct the findings. |
| B6: dependencies and evidence clutter | Added a tested runtime package lock and separate pinned test requirements; Docker uses the runtime lock without pytest. Added this reports index; retained requested recovery evidence, user work notes and functional simulator launch tasks. |
| B7: memory and retention | Compose now declares the measured PostgreSQL 1-CPU/2-GiB/no-extra-swap cap. The load harness still limits the controller to 3 CPUs/6 GiB. Host launcher execution is not resource-limited. Raw evidence is retained for review; automatic destructive retention is outside this assignment. |
| Public repository | Changed to private using the explicitly approved GitHub API operation, then verified `private: true`. No reviewer access or form submission is implied. |
| Personal fields | Author name and actual hours are `[TODO]` in the submission and relevant status documents, as requested. No values were inferred. |
| Commit/authorship concerns | Original history and AI-assistance disclosure retained. An AI percentage cannot be established from writing style. The executed three-decision rehearsal and question answers are already available. |

## Startup behavior

Automatic identities are a persisted deterministic URL-hash/generation namespace,
not a fresh random ID on every process start. Registration commits before any
controller mutation. A session lock protects automatic selection for the endpoint;
the existing run lock protects its evidence/actions. An advance whose response is
lost can therefore resume the same namespace instead of issuing fresh proposal IDs.

The public API has no immutable world token. An indistinguishable reset that has
caught up beyond saved counters/time cannot always be recognized. Use a fresh
explicit `SIM_RUN_ID` for that case. No evidence volume is wiped to get another
scenario running.

## Sample planning interpretation

For challenger share `s`, total independent-binomial planning N is
`z²*p*(1-p)/(lift²*s*(1-s))`; multiplying by `s` gives the stored challenger target.
Both observed arms must clear that target; the larger control population also
clears a conservative floor. The final decision happens at the fixed 72-hour
checkpoint and uses actual clustered uncertainty. The plan target does not
trigger an earlier winner evaluation.

The approximation concerns primary positivity, not power for the joint winner
rule. Requiring observed lift at least the planning effect and a guardrail bound
can substantially reduce winner probability. The unchanged eight-point rule and
the documented harmful inconclusive cleanups remain material limitations.

## Verification

Source fixes: `725affb`. Dependency/resource changes: `3bc8cbc`.

| Executed check | Result |
|---|---|
| Windows / Python 3.14.2 / real PostgreSQL | **136 passed, 1 skipped in 34.68s**; the skipped check requires Linux Bash |
| Linux / Python 3.12.16 / locked packages / real PostgreSQL | **137 passed in 39.49s**, including the real Bash launcher |
| Fresh Docker runtime build | Succeeded; `pip check` reports no broken requirements; pytest absent before installing development requirements |
| Compose configuration and running database cap | Valid; 1 CPU, 2,147,483,648 bytes memory and total memory+swap, matching the declared 2-GiB/no-extra-swap cap |
| Repository metadata after visibility change | GitHub API and connector both confirm **private** |
| [Real simulator API startup check](./pr1_startup_api.json) | Six controller launches across public_01, public_02 and a fresh public_02 on one URL/database; three distinct namespaces, stable restart IDs, complete event counts and prior evidence preserved |

Run the focused suite with [requirements-dev.txt](../requirements-dev.txt) and
`TEST_DATABASE_URL` set. Append `tests/test_run_identity.py` to the focused command
in [STEPS_5_7.md](./STEPS_5_7.md).
The suite must run one platform at a time against the shared database: session
advisory locks intentionally use the same synthetic run IDs across tests.
An initial concurrent Windows/Linux invocation collided on those locks and was
not counted as passing evidence. A new HTTP test fixture's missing credit field
was corrected before the final runs.

The new Linux-only test invokes the real `run.sh` without run-ID flags against a
controlled HTTP server: forced exit 137 after advance, restart, finished rerun,
second scenario and same-scenario fresh world. Other tests use real PostgreSQL
to check namespace persistence, legacy adoption, endpoint exclusion and preservation
of old runs. The existing grade/profile artifacts retain their original versions;
they are not presented as new load measurements for this patch.

The separate real-simulator check uses `--observe-only --max-ticks 0`, then
externally advances 15 minutes and launches again without a run-ID flag. It
does not read simulator run files or scenario truth. Its JSON records the exact
source commit, namespaces, times and event counts. This is startup/resume
verification, not another full scenario outcome or capacity benchmark.

## Remaining handoff

- Author name: [TODO]. Actual hours: [TODO].
- Reviewer identity, submission form and deadline: [TODO].
- External notification/watchdog delivery, calibrated faster QA detection,
  retention and database failover remain documented production follow-up.

The unresolved database/input anomalies are retained in the
[reports index](./README.md). No history rewrite, evidence deletion or broader
experiment scope was used to make this follow-up look complete.
