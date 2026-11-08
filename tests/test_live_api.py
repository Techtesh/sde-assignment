"""Opt-in read/restart verification against a completed real simulator run."""

import json
import os
import subprocess
import sys
from collections import defaultdict

import httpx
import psycopg
import pytest


def test_step1_against_real_http_events_and_restart():
    url = os.environ.get("LIVE_SIM_URL")
    run_id = os.environ.get("LIVE_RUN_ID")
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not all((url, run_id, dsn)):
        pytest.skip("Set LIVE_SIM_URL, LIVE_RUN_ID and TEST_DATABASE_URL for the live API check")
    with httpx.Client(base_url=url, timeout=120) as client, psycopg.connect(dsn, autocommit=True) as db:
        def get(path, **params):
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()

        get("/health")
        state = get("/sim/state")
        assert state["finished"], "Verify a completed run, not an advancing world"
        workflows = get("/workflows")
        assert workflows
        for workflow in workflows:
            wid = workflow["workflow_id"]
            config = get(f"/workflows/{wid}/config")
            history = get(f"/workflows/{wid}/config/history")
            assert any(item["version"] == config["version"] for item in history)
            stored = db.execute(
                "SELECT snapshot FROM config_history WHERE run_id=%s AND workflow_id=%s AND version=%s",
                (run_id, wid, config["version"]),
            ).fetchone()
            assert stored[0]["config"] == config["config"]

        counts = defaultdict(lambda: [0, 0, 0, 0])
        event_count = lead_count = audit_count = 0
        maximum_id = 0
        chunk_count = 0
        for kind in ("history", "events"):
            for chunk in get("/events/chunks", kind=kind, after=-1):
                seen = 0
                with client.stream("GET", f"/events/chunks/{chunk['chunk']}") as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        seen += 1
                        maximum_id = max(maximum_id, event["event_id"])
                        if event["type"] == "call":
                            total = counts[(event["workflow_id"], kind == "history")]
                            total[0] += 1
                            total[1] += event["connected"]
                            total[2] += event["engaged"]
                            total[3] += (event.get("qa") or {}).get("hallucination_flag", False)
                        elif event["type"] == "lead":
                            lead_count += 1
                        else:
                            audit_count += 1
                assert seen == chunk["events"]
                assert db.execute(
                    "SELECT kind,event_count FROM ingested_chunks WHERE run_id=%s AND chunk=%s",
                    (run_id, chunk["chunk"]),
                ).fetchone() == (kind, seen)
                event_count += seen
                chunk_count += 1

        rows = db.execute(
            "SELECT workflow_id,history,sum(dials),sum(connected),sum(engaged),sum(hallucinations) "
            "FROM hourly_metrics WHERE run_id=%s AND dimension='all' "
            "GROUP BY workflow_id,history", (run_id,),
        ).fetchall()
        assert {(row[0], row[1]): list(row[2:]) for row in rows} == dict(counts)
        for table, expected in (("events", event_count), ("leads", lead_count), ("audit_log", audit_count)):
            # Table names are the fixed literals above, never external input.
            assert db.execute(f"SELECT count(*) FROM {table} WHERE run_id=%s", (run_id,)).fetchone()[0] == expected
        assert maximum_id == state["last_event_id"]
        assert chunk_count == state["chunks"]

        result = subprocess.run(
            [sys.executable, "-m", "controller", "--url", url, "--run-id", run_id, "--max-ticks", "0"],
            env={**os.environ, "DATABASE_URL": dsn}, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        tick = json.loads(result.stdout.splitlines()[0])
        assert tick["finished"] and tick["ingested_events"] == 0
        assert db.execute("SELECT count(*) FROM events WHERE run_id=%s", (run_id,)).fetchone()[0] == event_count
        assert get("/sim/state") == state
        print(json.dumps({"step1": "passed", "http_events_verified": event_count,
                          "chunks_verified": chunk_count, "workflow_count": len(workflows),
                          "restart_new_events": 0}))
