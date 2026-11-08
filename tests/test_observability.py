import json
import os
import subprocess
import sys

import psycopg
import pytest

from controller.observability import audit, status
from test_controller import TS, chunk, open_store, sample_events


def test_views_work_while_writer_holds_lock_and_do_not_modify_evidence(database):
    with open_store(database) as store:
        store.observe_state({"ts": "2027-01-04T11:00:00+05:30", "scenario": "test",
                             "last_event_id": 3, "finished": False, "credits_remaining": 20})
        store.ingest(chunk(kind="events"), sample_events())
        store.record_tick({"ts": TS, "loop_seconds": 0.1})
        store.record_tick({"ts": TS, "loop_seconds": 0.2})
        with psycopg.connect(database, autocommit=True) as reader, reader.transaction():
            reader.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            view = status(reader, "test")
            assert view["health"]["event_backlog_at_last_observation"] == 0
            assert view["health"]["last_tick"]["metrics"]["loop_seconds"] == 0.2
            assert view["recent_changes"][0]["actor"] == "supervisor"
            answer = audit(reader, "test", "wf", "2027-01-04T10:00:00+05:30")
            assert answer["change"]["evidence"]["version"] == 2
            assert answer["proposal"] is None
            assert answer["after"]["dials"] == 0
        assert store.db.execute("SELECT count(*) FROM loop_ticks").fetchone()[0] == 1
        assert store.db.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 1
        with pytest.raises(ValueError, match="Unknown run"):
            status(store.db, "absent")
        with pytest.raises(ValueError, match="timezone"):
            audit(store.db, "test", "wf", "2027-01-04T10:00:00")


def test_status_cli_requires_no_url_and_does_not_acquire_writer_lock(database):
    with open_store(database) as store:
        store.observe_state({"ts": TS, "scenario": "test", "last_event_id": 9})
        result = subprocess.run([sys.executable, "-m", "controller", "status", "--json", "--run-id", "test"],
                                env={**os.environ, "DATABASE_URL": database}, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["health"]["event_backlog_at_last_observation"] == 9


def test_stale_loop_and_prompt_review_are_actionable_and_finished_run_is_quiet(database):
    with open_store(database) as store:
        state = {"ts": TS, "scenario": "test", "last_event_id": 0, "finished": False}
        store.observe_state(state)
        store.record_tick({"ts": TS})
        store.db.execute("UPDATE loop_ticks SET recorded_at=clock_timestamp()-interval '3 minutes'")
        store.save_incident("unsafe", {"workflow_id": "wf", "tenant_id": "tenant"}, "prompt_version", TS, {})
        store.update_incident("unsafe", "needs_review", TS, {"reason": "Paid result uncertain"})
        view = status(store.db, "test")
        assert len(view["alerts"]) == 2
        assert all(alert["severity"] == "page" and alert["action"] for alert in view["alerts"])
        store.observe_state({**state, "finished": True})
        assert status(store.db, "test")["alerts"] == []


@pytest.mark.parametrize("changed_at,expected", [("09:30", 1), ("09:00", 2)])
def test_audit_counts_only_actual_new_epoch_complete_hours(database, changed_at, expected):
    events = sample_events()
    events[2]["ts"] = f"2027-01-04T{changed_at}:00+05:30"
    for event_id, timestamp, version in (
        (4, "2027-01-04T09:45:00+05:30", 2),  # Partial application hour excluded.
        (5, "2027-01-04T10:15:00+05:30", 2),
        (6, "2027-01-04T10:30:00+05:30", 1),  # Campaign-pinned old epoch excluded.
        (7, "2027-01-04T11:00:00+05:30", 2),  # Not yet a completed hour.
    ):
        events.append({**events[1], "event_id": event_id, "ts": timestamp, "config_version": version})
    with open_store(database) as store:
        store.observe_state({"ts": "2027-01-04T11:15:00+05:30", "scenario": "test", "last_event_id": 7})
        store.ingest(chunk(kind="events", count=len(events)), events)
        answer = audit(store.db, "test", "wf", f"2027-01-04T{changed_at}:00+05:30")
        assert answer["after"]["dials"] == expected
        assert answer["after"]["connected"] == expected
        assert answer["after"]["hallucinations"] == expected


def test_credit_reserve_crash_loop_and_chunk_lag_are_visible(database):
    from controller.observability import status_text
    with open_store(database) as store:
        store.observe_state({"ts":TS,"scenario":"test","last_event_id":9,"chunks":3,"finished":False,"credits_remaining":4})
        for _ in range(3):
            store.db.execute("INSERT INTO loop_starts(run_id,sim_ts) VALUES (%s,%s)",(store.run_id,TS))
        view=status(store.db,"test")
        assert view["health"]["chunk_backlog_at_last_observation"]==3
        assert any("starts" in alert["reason"] and alert["severity"]=="page" for alert in view["alerts"])
        assert any("reserve" in alert["reason"] and alert["severity"]=="ticket" for alert in view["alerts"])
        assert "Backlog: 3 chunks" in status_text(view)
