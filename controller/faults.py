"""Opt-in abrupt exits for the recovery demonstration; unset during normal runs."""

import os


POINT = os.environ.get("CRASH_AT")
POINTS = ("after_advance", "mid_ingest", "after_intent", "after_post", "after_apply")
if POINT and POINT not in POINTS:
    raise ValueError(f"Unknown CRASH_AT: {POINT}")


def crash_at(point: str) -> None:
    if POINT == point:
        print(f"CRASH_AT={point}: exiting without cleanup", flush=True)
        os._exit(137)
