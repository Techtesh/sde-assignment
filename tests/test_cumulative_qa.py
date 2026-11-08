import copy
import random
from datetime import datetime, timedelta

import psycopg
import pytest

from test_controller import sample_events
from test_incidents import row, setup, tick
from controller.incidents import IncidentEngine, PROMPT_DAILY_ALPHA, PROMPT_LOOKS
from controller.metrics import alarms
from controller.store import Store


def prompt_change(world, store, *, version=2, at="2027-01-04T09:30:00+05:30", dims=None):
    previous = copy.deepcopy(world.config)
    previous["prompt_version"] = "P1"
    store.save_workflow(world.workflow, {"version": version - 1, "config": previous}, [])
    world.version = version
    store.save_workflow(world.workflow, {"version": version, "config": world.config}, [])
    event_id = store.db.execute("SELECT COALESCE(max(event_id),0)+1 FROM events").fetchone()[0]
    store.ingest({"chunk": event_id, "kind": "events", "events": 1}, [{
        "event_id": event_id, "type": "config_changed", "ts": at, "workflow_id": "wf",
        "version": version, "actor": "supervisor", "changed_dims": dims or ["prompt_version"],
    }])


def calls(store, *, count, flags, at, history=False, version=2, prompt="P2", cohort="default"):
    first_id = store.db.execute("SELECT COALESCE(max(event_id),0)+1 FROM events").fetchone()[0]
    lead, call = sample_events()[:2]
    events = []
    for index in range(count):
        event_id = first_id + 2 * index
        identity = f"person-{event_id}"
        events += [{**lead, "event_id": event_id, "ts": at, "lead_id": identity, "person_id": identity},
                   {**call, "event_id": event_id + 1, "ts": at, "lead_id": identity, "person_id": identity,
                    "config_version": version, "cohort_id": cohort,
                    "variant": {**call["variant"], "prompt_version": prompt},
                    "qa": {"hallucination_flag": index < flags}}]
    store.ingest({"chunk": first_id, "kind": "history" if history else "events", "events": len(events)}, events)
    return {"chunk": first_id, "kind": "history" if history else "events", "events": len(events)}, events


def test_first_planned_look_uses_prompt_change_instead_of_waiting_for_a_second_hour(database):
    with setup(database) as (world, store, api, governance, engine):
        prompt_change(world, store)
        calls(store, count=2000, flags=30, at="2027-01-02T09:45:00+05:30", history=True, prompt="P1")
        calls(store, count=44, flags=5, at="2027-01-04T09:45:00+05:30")
        tick(world, api, engine, 10, 30)
        incidents = store.open_incidents()
        assert len(incidents) == 1
        alarm = incidents[0]["data"]["alarm"]
        assert alarm["look_hours"] == 1
        assert alarm["current"]["connected"] == 44
        assert alarm["alpha"] == 0.004
        assert datetime.fromisoformat(incidents[0]["data"]["window_start"]) == datetime.fromisoformat("2027-01-04T09:30:00+05:30")
        assert world.paid == [] and world.writes == []


def test_two_hour_look_keeps_evidence_from_a_nonqualifying_first_hour(database):
    with setup(database) as (world, store, api, governance, engine):
        prompt_change(world, store)
        for hour in (9, 10):
            calls(store, count=2000, flags=30, at=f"2027-01-02T{hour:02d}:45:00+05:30", history=True, prompt="P1")
        calls(store, count=100, flags=4, at="2027-01-04T09:45:00+05:30")
        tick(world, api, engine, 10, 30)
        assert store.open_incidents() == []
        calls(store, count=100, flags=9, at="2027-01-04T10:45:00+05:30")
        tick(world, api, engine, 11, 30)
        alarm = store.open_incidents()[0]["data"]["alarm"]
        assert alarm["look_hours"] == 2
        assert alarm["current"]["connected"] == 200
        assert alarm["current"]["hallucinations"] == 13


def test_exact_cutoff_excludes_old_epoch_and_future_calls_even_in_the_same_hour(database):
    with setup(database) as (world, store, api, governance, engine):
        prompt_change(world, store)
        calls(store, count=40, flags=4, at="2027-01-04T09:45:00+05:30", version=1)
        calls(store, count=40, flags=4, at="2027-01-04T10:45:00+05:30")
        calls(store, count=40, flags=4, at="2027-01-04T10:15:00+05:30")
        measured = store.qa_window_metrics("wf", 2, "P2", "2027-01-04T09:30:00+05:30", "2027-01-04T10:30:00+05:30")
        assert measured[0]["connected"] == 40 and measured[0]["hallucinations"] == 4
        # The normal look path still works from counters if raw calls are unavailable.
        store.db.execute("DELETE FROM events WHERE kind='call'")
        assert store.qa_window_metrics("wf", 2, "P2", "2027-01-04T09:30:00+05:30", "2027-01-04T10:30:00+05:30") == measured


def test_recorded_positive_look_survives_interruption_before_incident_creation(database, monkeypatch):
    with setup(database) as (world, store, api, governance, engine):
        prompt_change(world, store)
        calls(store, count=2000, flags=30, at="2027-01-02T09:45:00+05:30", history=True, prompt="P1")
        calls(store, count=44, flags=5, at="2027-01-04T09:45:00+05:30")
        save_incident = store.save_incident

        def interrupted(*args):
            raise RuntimeError("interrupted after look")

        monkeypatch.setattr(store, "save_incident", interrupted)
        with pytest.raises(RuntimeError, match="after look"):
            tick(world, api, engine, 10, 30)
        assert len(store.prompt_detections("wf", 2)) == 1
        monkeypatch.setattr(store, "save_incident", save_incident)

        def already_evaluated(*args, **kwargs):
            raise AssertionError("A saved look must not be tested again")

        monkeypatch.setattr(store, "qa_window_metrics", already_evaluated)
        restarted = IncidentEngine(api, store, governance)
        tick(world, api, restarted, 10, 45)
        assert len(store.open_incidents()) == 1
        assert len(store.prompt_detections("wf", 2)) == 1


def test_budget_is_split_across_cohorts_and_sparse_looks_stay_recorded(database):
    with setup(database) as (world, store, api, governance, engine):
        world.config["cohorts"] = [{"id": "en", "where": {"lang": ["en"]}}]
        prompt_change(world, store)
        world.now = "2027-01-07T09:30:00+05:30"
        engine.tick(world.state(), [(world.workflow, api.get("/workflows/wf/config"))])
        windows = store.prompt_detections("wf", 2)
        assert len(windows) == 14  # Four early looks plus three daily looks, two cohorts.
        assert sum(w["evidence"]["alpha"] for w in windows) < 0.01
        assert windows[0]["evidence"]["alpha"] == 0.002
        assert not any(w["evidence"]["signal"] for w in windows)
        engine.tick(world.state(), [(world.workflow, api.get("/workflows/wf/config"))])
        assert store.prompt_detections("wf", 2) == windows
        assert sum(alpha for _, alpha in PROMPT_LOOKS) + PROMPT_DAILY_ALPHA == pytest.approx(0.01)


def test_qa_counter_replay_and_one_time_old_run_backfill(database):
    with setup(database) as (world, store, api, governance, engine):
        chunk, events = calls(store, count=40, flags=4, at="2027-01-04T09:45:00+05:30")
        expected = store.db.execute("SELECT * FROM qa_metrics").fetchall()
        assert store.ingest(chunk, events) == 0
        assert store.db.execute("SELECT * FROM qa_metrics").fetchall() == expected
        store.db.execute("DELETE FROM qa_metrics")
        store.db.execute("DELETE FROM qa_evidence_ready")
    for _ in range(2):
        with psycopg.connect(database, autocommit=True) as db:
            Store(db, "incidents", "http://simulator")
            assert db.execute("SELECT * FROM qa_metrics").fetchall() == expected


def test_voice_edits_keep_the_anchor_but_cohort_edits_start_a_new_population(database):
    with setup(database) as (world, store, api, governance, engine):
        prompt_change(world, store)
        for hour in (9, 10):
            calls(store, count=2000, flags=30, at=f"2027-01-02T{hour:02d}:45:00+05:30", history=True, prompt="P1")
        calls(store, count=100, flags=4, at="2027-01-04T09:45:00+05:30")
        tick(world, api, engine, 10, 30)
        event_id = store.db.execute("SELECT max(event_id)+1 FROM events").fetchone()[0]
        store.ingest({"chunk": event_id, "kind": "events", "events": 1}, [{
            "event_id": event_id, "type": "config_changed", "ts": "2027-01-04T10:30:00+05:30",
            "workflow_id": "wf", "version": 3, "actor": "supervisor", "changed_dims": ["voice"],
        }])
        world.version = 3
        calls(store, count=100, flags=9, at="2027-01-04T10:45:00+05:30", version=3)
        tick(world, api, engine, 11, 30)
        incident = store.open_incidents()[0]
        assert incident["data"]["epoch"] == 2
        assert incident["data"]["alarm"]["current"]["connected"] == 200
        world.config["cohorts"] = [{"id": "en", "where": {"lang": ["en"]}}]
        event_id += 201
        store.ingest({"chunk": event_id, "kind": "events", "events": 1}, [{
            "event_id": event_id, "type": "config_changed", "ts": "2027-01-04T11:30:00+05:30",
            "workflow_id": "wf", "version": 4, "actor": "supervisor", "changed_dims": ["cohorts"],
        }])
        world.version = 4
        change = store.prompt_alarm_change("wf")
        assert engine._prompt_alarms("wf", world.config, change, "2027-01-04T12:30:00+05:30") == []
        windows = store.prompt_detections("wf", 4)
        assert len(windows) == 2
        assert all(w["evidence"]["current"]["connected"] == 0 for w in windows)


def test_qa_updates_roll_back_with_the_chunk_checkpoint(database):
    with setup(database) as (world, store, api, governance, engine):
        store.db.execute("""
            CREATE FUNCTION reject_qa_chunk() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'reject checkpoint'; END $$;
            CREATE TRIGGER reject_qa_checkpoint BEFORE INSERT ON ingested_chunks
            FOR EACH ROW EXECUTE FUNCTION reject_qa_chunk();
        """)
        with pytest.raises(psycopg.Error, match="reject checkpoint"):
            calls(store, count=40, flags=4, at="2027-01-04T09:45:00+05:30")
        assert store.db.execute("SELECT count(*) FROM qa_metrics").fetchone()[0] == 0
        assert store.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        store.db.execute("DROP TRIGGER reject_qa_checkpoint ON ingested_chunks")
        calls(store, count=40, flags=4, at="2027-01-04T09:45:00+05:30")
        assert store.db.execute("SELECT connected,hallucinations FROM qa_metrics").fetchone() == (40, 4)


@pytest.mark.parametrize("look_already_saved", [False, True])
def test_new_remote_config_waits_for_its_event_instead_of_reusing_an_old_anchor(database, look_already_saved):
    with setup(database) as (world, store, api, governance, engine):
        prompt_change(world, store)
        calls(store, count=2000, flags=30, at="2027-01-02T09:45:00+05:30", history=True, prompt="P1")
        calls(store, count=44, flags=5, at="2027-01-04T09:45:00+05:30")
        if look_already_saved:
            engine._prompt_alarms("wf", world.config, store.prompt_alarm_change("wf"), "2027-01-04T10:30:00+05:30")
        before = store.prompt_detections("wf", 2)
        world.config["prompt_version"] = "P1"
        world.version = 3  # Governance applied; its event is not ingested until next tick.
        store.save_workflow(world.workflow, {"version": 3, "config": world.config}, [])
        tick(world, api, engine, 10, 30)
        assert store.open_incidents() == []
        assert store.prompt_detections("wf", 2) == before


def test_seeded_null_calibration_covers_the_whole_four_look_rule():
    rng = random.Random(9182)
    false_alarms = 0
    for _ in range(500):
        baseline = [row("prompt_version", "P1", connected=2000,
                        hallucinations=sum(rng.random() < 0.015 for _ in range(2000)))]
        flags = 0
        previous = 0
        signaled = False
        for hours, alpha in PROMPT_LOOKS:
            count = 100 * hours
            flags += sum(rng.random() < 0.015 for _ in range(count - previous))
            observation = row("prompt_version", "P2", connected=count, hallucinations=flags)
            signaled |= alarms([observation], baseline, {"prompt_version": "P2"}, qa_alpha=alpha)[0]["signal"]
            previous = count
        false_alarms += signaled
    assert false_alarms <= 10  # Allows finite-simulation variation around the 0.008 early budget.
    print({"null_replicates": 500, "four_look_false_alarms": false_alarms})
