import copy
import random
from contextlib import contextmanager
from datetime import datetime, timedelta

import httpx
import psycopg
import pytest

from controller.api import SimulatorAPI
from controller.experiments import ExperimentEngine, applied_timestamp
from controller.governance import Governance
from controller.store import Store
from test_governance import World


@contextmanager
def setup(database):
    world = World()
    world.workflow["objective"] = {"primary": "engagement_rate", "guardrail": {"pickup_rate_max_drop": 0.1}}
    world.workflow["tenant_id"] = "tenant"
    world.workflow["mid_flight"] = "allowed"
    original = world.handler
    def handler(request):
        response = original(request)
        for entry in world.history:
            entry.setdefault("applied_at", world.now if entry.get("proposal_id") else None)
        if request.method == "GET" and request.url.path == "/sim/state":
            state = response.json()
            state["sim_minute"] = int((datetime.fromisoformat(world.now) - datetime.fromisoformat("2027-01-04T00:00:00+05:30")).total_seconds() / 60)
            return httpx.Response(200, json=state)
        return response
    with psycopg.connect(database, autocommit=True) as db:
        store = Store(db, "experiments", "http://simulator")
        world.store = store
        store.db.execute(
            "INSERT INTO hourly_metrics VALUES (%s,'wf',true,'2027-01-03T11:00:00+05:30',1,"
            "'default','voice','V1',40000,20000,10000,0)", (store.run_id,),
        )
        with httpx.Client(base_url="http://simulator", transport=httpx.MockTransport(handler)) as client:
            api = SimulatorAPI(client)
            governance = Governance(api, store)
            yield world, store, api, governance, ExperimentEngine(api, store, governance)


def tick(world, api, engine, when=None, *, finished=False):
    if when:
        world.now = when.isoformat() if isinstance(when, datetime) else when
    state = {"ts": world.now, "finished": finished, "sim_minute": 0, "end_minute": 99999}
    engine.tick(state, [(world.workflow, api.get("/workflows/wf/config"))])


def record(store, eid):
    return next(row for row in store.experiments("wf") if row["experiment_id"] == eid)


def start(world, store, api, governance, engine):
    tick(world, api, engine)
    experiment = store.experiments("wf")[0]
    assert experiment["status"] == "planned"
    governance.tick(world.now)
    tick(world, api, engine)
    return experiment["experiment_id"]


def seed_calls(store, version, when, *, prefix="trial", harmful=False, promoted=False, small=False):
    rng = random.Random(117)
    next_id = store.db.execute("SELECT COALESCE(max(event_id),0)+1 FROM events").fetchone()[0]
    events = []
    for voice, number in (("V1", 125 if promoted else 1000), ("V2", 1125 if promoted else 250)):
        for person in range(2 if small else number):
            pid = f"{prefix}-{voice}-{person}"
            events.append({"event_id": next_id, "type": "lead", "ts": when.isoformat(),
                           "workflow_id": "wf", "lead_id": pid, "person_id": pid,
                           "campaign_id": "campaign", "features": {"lang": "en"}})
            next_id += 1
            for _ in range(4):
                connected = rng.random() < 0.7
                engaged = connected and rng.random() < (0.05 if harmful and voice == "V2" else (0.85 if voice == "V2" else 0.5))
                events.append({"event_id": next_id, "type": "call", "ts": when.isoformat(),
                               "workflow_id": "wf", "lead_id": pid, "person_id": pid,
                               "cohort_id": "default", "config_version": version,
                               "variant": {"voice": voice, "welcome_message": "W1", "caller_id": "D1", "prompt_version": "P1"},
                               "connected": connected, "engaged": engaged,
                               "qa": {"hallucination_flag": False} if connected else None})
                next_id += 1
    number = store.last_chunk("events") + 1
    store.ingest({"chunk": number, "kind": "events", "events": len(events)}, events)


def expose(world, store, api, engine, version=2, **kwargs):
    first = datetime.fromisoformat(world.now) + timedelta(minutes=15)
    seed_calls(store, version, first, **kwargs)
    tick(world, api, engine, first + timedelta(minutes=15))
    return first


def test_no_winner_before_fixed_checkpoint_then_governed_promotion(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        tick(world, api, engine, first + timedelta(hours=1))
        experiment = record(store, eid)
        assert experiment["status"] == "running" and "evaluation" not in experiment["data"]
        assert world.config["allocations"]["default"]["voice"] == {"V1": 0.8, "V2": 0.2}
        tick(world, api, engine, first + timedelta(hours=72))
        experiment = record(store, eid)
        assert experiment["data"]["evaluation"]["decision"] == "winner"
        assert experiment["status"] == "promoting"
        assert world.config["allocations"]["default"]["voice"]["V2"] == 0.2
        governance.tick(world.now)
        assert world.approvals[-1]["body"]["proposed_config"]["allocations"]["default"]["voice"]["V2"] == 0.9
        world.approvals[-1]["status"] = "approved"
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "monitoring"
        assert world.config["allocations"]["default"]["voice"]["V1"] == pytest.approx(0.1)


def test_unapproved_split_provides_no_experiment_evidence(database):
    with setup(database) as (world, store, api, governance, engine):
        world.workflow["governance"]["auto_apply"]["enabled"] = False
        tick(world, api, engine)
        eid = store.experiments()[0]["experiment_id"]
        governance.tick(world.now)
        tick(world, api, engine, datetime.fromisoformat(world.now) + timedelta(hours=1))
        assert record(store, eid)["status"] == "planned"
        assert "started_at" not in record(store, eid)["data"]
        assert store.db.execute("SELECT count(*) FROM experiment_people").fetchone()[0] == 0
        world.approvals[-1]["status"] = "rejected"
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "blocked"


def test_campaign_pinned_old_versions_are_not_pooled(database):
    with setup(database) as (world, store, api, governance, engine):
        world.workflow["mid_flight"] = "next_campaign_only"
        eid = start(world, store, api, governance, engine)
        first = datetime.fromisoformat(world.now) + timedelta(minutes=15)
        seed_calls(store, 1, first, prefix="old")
        tick(world, api, engine, first + timedelta(minutes=15))
        assert "started_at" not in record(store, eid)["data"]
        second = expose(world, store, api, engine, small=True)
        experiment = record(store, eid)
        rows = store.collect_exposure(experiment, "trial", 2, second.isoformat(), (second + timedelta(hours=1)).isoformat())
        assert sum(row["dials"] for row in rows) == 16


def test_inconclusive_checkpoint_restores_without_extending_until_significant(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine, small=True)
        tick(world, api, engine, first + timedelta(hours=72))
        original = record(store, eid)["data"]["evaluation"]
        assert original["decision"] == "inconclusive"
        assert not store.decision_proposal(f"experiment:{eid}:restore")["urgent"]
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "inconclusive"
        assert world.config["allocations"]["default"]["voice"] == {"V1": 1.0}
        assert record(store, eid)["data"]["evaluation"] == original


def test_population_harm_can_stop_early_but_never_promote_early(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine, harmful=True)
        tick(world, api, engine, first + timedelta(hours=1))
        assert record(store, eid)["status"] == "restoring"
        assert "evaluation" not in record(store, eid)["data"]
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "lost"


def test_supervisor_voice_edit_is_never_undone(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        edited = copy.deepcopy(world.config)
        edited["allocations"]["default"]["voice"] = {"V2": 1}
        world.edit(edited)
        before = len(world.writes)
        tick(world, api, engine, first + timedelta(hours=1))
        assert record(store, eid)["status"] == "interrupted"
        assert len(world.writes) == before
        assert world.config["allocations"]["default"]["voice"] == {"V2": 1}


def test_unrelated_edit_interrupts_epoch_and_cleanup_preserves_it(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        edited = copy.deepcopy(world.config)
        edited["prompt_version"] = "P2"
        world.edit(edited)
        tick(world, api, engine, first + timedelta(hours=1))
        assert record(store, eid)["status"] == "restoring"
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "interrupted"
        assert world.config["prompt_version"] == "P2"
        assert world.config["allocations"]["default"]["voice"] == {"V1": 1.0}


def test_collection_replay_and_restart_do_not_double_count_people(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        tick(world, api, engine, first + timedelta(hours=1))
        experiment = record(store, eid)
        count = store.db.execute("SELECT sum(dials) FROM experiment_people WHERE phase='trial'").fetchone()[0]
        store.db.close()
        with psycopg.connect(database, autocommit=True) as db:
            restarted = Store(db, "experiments", "http://simulator")
            world.store = restarted
            new_engine = ExperimentEngine(api, restarted, Governance(api, restarted))
            tick(world, api, new_engine)
            assert restarted.db.execute("SELECT sum(dials) FROM experiment_people WHERE phase='trial'").fetchone()[0] == count
            with pytest.raises(ValueError, match="already collected"):
                restarted.collect_exposure(experiment, "trial", 2, first.isoformat(), first.isoformat())


def test_aggregation_and_window_cursor_rollback_together(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        store.db.execute("""
            CREATE FUNCTION fail_window() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'window failure'; END $$;
            CREATE TRIGGER reject_window BEFORE INSERT ON experiment_windows
            FOR EACH ROW EXECUTE FUNCTION fail_window();
        """)
        with pytest.raises(psycopg.Error, match="window failure"):
            store.collect_exposure(record(store, eid), "trial", 2, first.isoformat(), (first + timedelta(hours=1)).isoformat())
        assert store.db.execute("SELECT count(*) FROM experiment_people").fetchone()[0] == 0
        assert store.db.execute("SELECT count(*) FROM experiment_windows").fetchone()[0] == 0
        store.db.execute("DROP TRIGGER reject_window ON experiment_windows")
        rows = store.collect_exposure(record(store, eid), "trial", 2, first.isoformat(), (first + timedelta(hours=1)).isoformat())
        assert sum(row["dials"] for row in rows) == 5000


def test_promoted_winner_decay_rolls_back_through_approval(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        tick(world, api, engine, first + timedelta(hours=72))
        governance.tick(world.now)
        world.approvals[-1]["status"] = "approved"
        governance.tick(world.now)
        tick(world, api, engine)
        monitor = expose(world, store, api, engine, version=3, prefix="decay", harmful=True, promoted=True)
        tick(world, api, engine, monitor + timedelta(hours=24))
        assert record(store, eid)["status"] == "restoring"
        assert record(store, eid)["data"]["decay_evidence"]
        governance.tick(world.now)
        assert world.config["allocations"]["default"]["voice"]["V2"] == 0.9
        world.approvals[-1]["status"] = "approved"
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "rolled_back"
        assert world.config["allocations"]["default"]["voice"] == {"V1": 1.0}


def test_scenario_finish_cannot_create_an_early_winner_or_write(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        expose(world, store, api, engine)
        writes = len(world.writes)
        tick(world, api, engine, finished=True)
        assert record(store, eid)["status"] == "unfinished"
        assert "evaluation" not in record(store, eid)["data"] and len(world.writes) == writes


def test_lost_split_response_resumes_the_same_trial_without_applying_twice(database):
    with setup(database) as (world, store, api, governance, engine):
        tick(world, api, engine)
        eid = store.experiments()[0]["experiment_id"]
        world.lose_response = True
        with pytest.raises(httpx.ReadError):
            governance.tick(world.now)
        Governance(api, store).tick(world.now)
        tick(world, api, ExperimentEngine(api, store, Governance(api, store)))
        assert record(store, eid)["status"] == "running"
        assert len(world.writes) == 1 and world.version == 2


def test_rejected_promotion_cleans_up_the_completed_trial(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        tick(world, api, engine, first + timedelta(hours=72))
        governance.tick(world.now)
        world.approvals[-1]["status"] = "rejected"
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "restoring"
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "blocked"
        assert world.config["allocations"]["default"]["voice"] == {"V1": 1.0}


def test_incident_preemption_waits_for_permission_and_cleanup_preserves_repair(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        expose(world, store, api, engine)
        desired = copy.deepcopy(world.config)
        desired["allocations"]["default"]["caller_id"] = {"D1": 1.0}
        pid = governance.plan("wf", desired, decision_id="urgent-repair", base_version=world.version,
                              rationale="fixture incident", summary="repair caller", urgent=True)
        store.save_incident("incident", world.workflow, "caller_id", world.now, {})
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "restoring"
        assert store.decision_proposal(f"experiment:{eid}:restore") is None
        assert store.proposal(pid)["status"] == "pending"
        world.approvals[-1]["status"] = "approved"
        governance.tick(world.now)
        tick(world, api, engine)
        cleanup = store.decision_proposal(f"experiment:{eid}:restore")
        assert cleanup["body"]["proposed_config"]["allocations"]["default"]["caller_id"] == {"D1": 1.0}
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "interrupted"
        assert world.config["allocations"]["default"]["caller_id"] == {"D1": 1.0}


def test_numeric_auto_apply_timestamp_and_iso_approval_timestamp():
    state = {"ts": "2027-01-04T11:15:00+05:30", "sim_minute": 675}
    assert applied_timestamp(0, state) == "2027-01-04T00:00:00+05:30"
    assert applied_timestamp(660, state) == "2027-01-04T11:00:00+05:30"
    assert applied_timestamp("2027-01-04T11:00:00+05:30") == "2027-01-04T11:00:00+05:30"


def test_numeric_timestamp_persisted_before_crash_is_normalized_on_restart(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        experiment = record(store, eid)
        store.update_experiment(eid, "running", world.now, {**experiment["data"], "owned_at": 660})
        tick(world, api, ExperimentEngine(api, store, governance))
        assert record(store, eid)["data"]["owned_at"] == "2027-01-04T11:00:00+05:30"


def test_cleanup_preserves_supervisor_voice_edit_to_another_cohort(database):
    with setup(database) as (world, store, api, governance, engine):
        world.config["cohorts"] = [{"id": "ta", "where": {"lang": ["ta"]}}]
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        edited = copy.deepcopy(world.config)
        edited["allocations"]["ta"]["voice"] = {"V2": 1}
        world.edit(edited)
        tick(world, api, engine, first + timedelta(hours=1))
        governance.tick(world.now)
        tick(world, api, engine)
        assert record(store, eid)["status"] == "interrupted"
        assert world.config["allocations"]["default"]["voice"] == {"V1": 1}
        assert world.config["allocations"]["ta"]["voice"] == {"V2": 1}
