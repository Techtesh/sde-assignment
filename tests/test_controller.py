import copy
import json
import os
import subprocess
import sys
from contextlib import contextmanager

import httpx
import psycopg
import pytest
from psycopg import sql

from controller.__main__ import run
from controller.api import SimulatorAPI
from controller.store import Store, event_row


TS = "2027-01-04T09:00:00+05:30"


def sample_events():
    return [
        {"event_id": 1, "type": "lead", "ts": TS, "workflow_id": "wf",
         "lead_id": "l1", "person_id": "p1", "campaign_id": "c1", "features": {"lang": "hi"}},
        {"event_id": 2, "type": "call", "ts": TS, "workflow_id": "wf", "lead_id": "l1",
         "person_id": "p1", "config_version": 1, "cohort_id": "default",
         "variant": {"voice": "V1", "welcome_message": "W1", "caller_id": "D1", "prompt_version": "P1"},
         "connected": True, "engaged": False, "qa": {"hallucination_flag": True}},
        {"event_id": 3, "type": "config_changed", "ts": TS, "workflow_id": "wf",
         "actor": "supervisor", "version": 2, "changed_dims": ["prompt_version"]},
    ]


def chunk(number=0, kind="history", count=3):
    return {"chunk": number, "kind": kind, "events": count}


@contextmanager
def open_store(dsn, run_id="test"):
    with psycopg.connect(dsn, autocommit=True) as connection:
        yield Store(connection, run_id, "http://simulator")


def table_count(store, name):
    return store.db.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))).fetchone()[0]


def test_chunk_replay_and_duplicate_event_ids_do_not_double_count(database):
    with open_store(database) as store:
        assert store.ingest(chunk(), sample_events()) == 3
        assert store.ingest(chunk(), iter(())) == 0
        assert store.ingest(chunk(number=1), sample_events()) == 0
        assert table_count(store, "events") == 3
        assert table_count(store, "leads") == 1
        assert table_count(store, "audit_log") == 1
        assert store.last_chunk("history") == 1
        assert store.last_chunk("events") == -1
        assert store.summary() == [{
            "workflow_id": "wf", "history": True, "dials": 1, "connected": 1,
            "engaged": 0, "pickup_rate": 1.0, "engagement_rate": 0.0,
        }]


def test_error_after_counter_updates_rolls_back_everything(database):
    with open_store(database) as store:
        store.db.execute("""
            CREATE FUNCTION reject_chunk() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'simulated failure before commit'; END $$;
            CREATE TRIGGER fail_checkpoint BEFORE INSERT ON ingested_chunks
            FOR EACH ROW EXECUTE FUNCTION reject_chunk();
        """)
        with pytest.raises(psycopg.Error, match="simulated failure"):
            store.ingest(chunk(), sample_events())
        for name in ("events", "leads", "hourly_metrics", "audit_log", "ingested_chunks"):
            assert table_count(store, name) == 0
        store.db.execute("DROP TRIGGER fail_checkpoint ON ingested_chunks")
        assert store.ingest(chunk(), sample_events()) == 3


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_ids_inside_new_chunk_are_checked_before_insert(database, conflicting):
    events = sample_events()
    duplicate = copy.deepcopy(events[1])
    duplicate["engaged"] = conflicting
    events.append(duplicate)
    with open_store(database) as store:
        if conflicting:
            with pytest.raises(ValueError, match="Conflicting event_id"):
                store.ingest(chunk(count=4), events)
            assert table_count(store, "events") == 0
            assert store.last_chunk("history") == -1
        else:
            assert store.ingest(chunk(count=4), events) == 3
            assert store.summary()[0]["dials"] == 1


def test_process_crash_mid_stream_can_restart(database):
    script = """
import json, os, psycopg
from controller.store import Store
with psycopg.connect(os.environ['CRASH_TEST_DSN'], autocommit=True) as db:
    store = Store(db, 'crash', 'http://simulator')
    def broken_stream():
        yield json.loads(os.environ['CRASH_TEST_EVENT'])
        os._exit(9)
    store.ingest({'chunk': 0, 'kind': 'history', 'events': 3}, broken_stream())
"""
    env = {**os.environ, "CRASH_TEST_DSN": database, "CRASH_TEST_EVENT": json.dumps(sample_events()[0])}
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, timeout=20)
    assert result.returncode == 9, result.stderr.decode()
    with open_store(database, "crash") as store:
        assert table_count(store, "events") == 0
        assert store.last_chunk("history") == -1
        assert store.ingest(chunk(), sample_events()) == 3


def test_stream_error_and_bad_count_leave_chunk_unprocessed(database):
    with open_store(database) as store:
        def interrupted():
            yield sample_events()[0]
            raise httpx.ReadError("stream lost")
        with pytest.raises(httpx.ReadError):
            store.ingest(chunk(), interrupted())
        with pytest.raises(ValueError, match="expected 3 events"):
            store.ingest(chunk(), sample_events()[:1])
        assert table_count(store, "events") == 0
        assert store.last_chunk("history") == -1


def test_missing_lead_and_conflicting_ids_fail_without_checkpoint(database):
    with open_store(database) as store:
        with pytest.raises(ValueError, match="no matching lead"):
            store.ingest(chunk(count=1), [sample_events()[1]])
        store.ingest(chunk(), sample_events())
        changed = copy.deepcopy(sample_events())
        changed[1]["engaged"] = True
        with pytest.raises(ValueError, match="Conflicting event_id"):
            store.ingest(chunk(number=1), changed)
        assert store.last_chunk("history") == 0


def test_restart_preserves_progress_and_rejects_concurrent_controller(database):
    with open_store(database) as store:
        store.ingest(chunk(), sample_events())
        with pytest.raises(RuntimeError, match="already processing"):
            with open_store(database):
                pass
    with open_store(database) as restarted:
        assert restarted.last_chunk("history") == 0
        assert restarted.ingest(chunk(), sample_events()) == 0


def test_world_reset_is_rejected(database):
    state = {"ts": TS, "scenario": "test", "last_event_id": 3}
    with open_store(database) as store:
        store.observe_state(state)
        with pytest.raises(ValueError, match="time moved backward"):
            store.observe_state({**state, "ts": "2027-01-04T08:00:00+05:30"})
        with pytest.raises(ValueError, match="world changed"):
            store.observe_state({**state, "last_event_id": 1})


def test_read_retries_but_advance_never_retries(monkeypatch):
    monkeypatch.setattr("controller.api.time.sleep", lambda _: None)
    requests = []
    def handler(request):
        requests.append(request.method)
        if request.method == "GET" and len(requests) > 1:
            return httpx.Response(200, json={"ok": True})
        raise httpx.ReadError("lost response")
    with httpx.Client(base_url="http://simulator", transport=httpx.MockTransport(handler)) as client:
        api = SimulatorAPI(client)
        assert api.get("/health") == {"ok": True}
        with pytest.raises(httpx.ReadError):
            api.advance()
    assert requests == ["GET", "GET", "POST"]


def test_non_finished_conflict_is_not_swallowed():
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"finished": False})
        return httpx.Response(409, json={"detail": "another conflict"})
    with httpx.Client(base_url="http://simulator", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            SimulatorAPI(client).advance()


def test_final_advance_events_are_drained_before_exit(database):
    advanced = False
    trace = []
    def handler(request):
        nonlocal advanced
        trace.append((request.method, request.url.path))
        if request.url.path == "/health":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/sim/state":
            return httpx.Response(200, json={
                "ts": TS, "scenario": "test", "last_event_id": 3 if advanced else 0,
                "finished": advanced, "credits_remaining": 10,
            })
        if request.url.path == "/workflows":
            return httpx.Response(200, json=[])
        if request.url.path == "/sim/advance":
            advanced = True
            return httpx.Response(200, json={"finished": True})
        if request.url.path == "/events/chunks":
            live = request.url.params["kind"] == "events"
            return httpx.Response(200, json=[chunk(kind="events")] if advanced and live else [])
        if request.url.path == "/events/chunks/0":
            return httpx.Response(200, text="\n".join(json.dumps(e) for e in sample_events()))
        raise AssertionError(request.url)
    with open_store(database) as store:
        with httpx.Client(base_url="http://simulator", transport=httpx.MockTransport(handler)) as client:
            run(SimulatorAPI(client), store)
        assert store.summary()[0]["history"] is False
        assert store.summary()[0]["dials"] == 1
        advance_at = trace.index(("POST", "/sim/advance"))
        assert ("GET", "/events/chunks") in trace[:advance_at]
        assert trace.count(("POST", "/sim/advance")) == 1


def test_unimplemented_sequential_option_is_not_exposed():
    result = subprocess.run(
        [sys.executable, "-m", "controller", "--url", "http://simulator", "--sequential-testing"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2
    assert "unrecognized arguments: --sequential-testing" in result.stderr


@pytest.mark.parametrize("change", [
    {"connected": "false"}, {"connected": False, "engaged": True},
    {"ts": "2027-01-04T09:00:00"}, {"variant": {"voice": "V1"}},
    {"qa": {"hallucination_flag": "false"}},
])
def test_invalid_call_evidence_is_rejected(change):
    event = {**sample_events()[1], **change}
    with pytest.raises(ValueError):
        event_row("test", 0, True, event)


def test_misspelled_event_type_rolls_back_instead_of_corrupting_counts(database):
    events=sample_events()
    events[1]["type"]="ball"
    with open_store(database) as store:
        with pytest.raises(ValueError,match="Unsupported event type"):
            store.ingest(chunk(),events)
        assert table_count(store,"events")==0 and store.last_chunk("history")==-1
