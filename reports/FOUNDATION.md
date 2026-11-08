# Observation-only foundation verification

This is milestone 1 evidence, not a claim that the learning controller is complete.
The baseline and controller are run on public_01 through the documented simulator CLI/HTTP API.
See [WorkPlan.md](../WorkPlan.md) for remaining capabilities.

## Results

- Runtime: Windows host, configured Python 3.14.2, PostgreSQL 17 in Docker.
- `python -m pytest -q tests/test_controller.py`: **16 passed**, with `TEST_DATABASE_URL`
  pointing to the real local PostgreSQL service. No database tests were skipped.
- Eight simulated days completed. Persisted: **297,024 events**, last event ID 297,024,
  **393 completed chunks**.
- The initial 187,400-event history import took 11.872 seconds, about 15.8k events/second.
  This local history measurement is **not** a public_03 benchmark or a claim about the target hardware.
- A restart after one tick resumed without replaying history. A restart after completion
  ingested zero new events and exited successfully.
- An abrupt subprocess exit during COPY left no committed events or chunk marker; restarting
  ingested the chunk successfully. A separate failure injected at checkpoint insertion rolled
  back raw events, leads, aggregates, and audit rows together.
- Linux `bash -n` passes on the LF-normalized launcher. The tracked executable bit is retained.
- Editor diagnostics report no errors in the new Python implementation and tests.

Live call counts from the controller's own database (`dimension = 'all'`, excluding history):

| Workflow | Dials | Connected | Engaged |
|---|---:|---:|---:|
| ks_cancel | 38,400 | 9,150 | 4,491 |
| nw_kyc | 16,000 | 3,872 | 2,287 |
| nw_renewal | 28,800 | 7,588 | 4,140 |

[Grade output](./foundation_public01.md): all primary, guardrail, and conclusion-rate deltas
are zero against baseline. Zero proposals, configuration changes, validation runs, and LLM calls;
credits used: zero. That is the expected result for an observation-only controller.

## Reproduce

```text
python -m sim baseline --scenario scenarios/public_01_dev.yaml --run-dir runs/base_foundation01
python -m sim serve --scenario scenarios/public_01_dev.yaml --run-dir runs/foundation01
```

With the database configured as documented in [CONTROLLER.md](../docs/CONTROLLER.md):

```text
python -m controller --url http://127.0.0.1:8700 --run-id foundation01 --max-ticks 1
python -m controller --url http://127.0.0.1:8700 --run-id foundation01
python -X utf8 -m sim grade --run runs/foundation01 --baseline runs/base_foundation01 --out reports/foundation_public01.md
```

Use fresh simulator run directories and a fresh database run ID for a new world. The UTF-8 option
avoids the simulator report writer's Windows default-encoding issue without modifying simulator code.

## Remaining verification

Governance/action recovery, learning/incident behavior, public_02 outcomes, public_03 throughput/memory/lag,
and a Linux end-to-end launcher execution remain for later milestones. Only launcher syntax was checked
under Linux; the end-to-end controller run used the configured Windows interpreter. The naive controller's
source was reviewed but it was not executed as part of this verification.
