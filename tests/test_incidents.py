import copy
import hashlib
import json
import random
from contextlib import contextmanager

import httpx
import psycopg
import pytest

from controller.api import SimulatorAPI
from controller.governance import Governance
from controller.incidents import IncidentEngine
from controller.metrics import adjusted_population_harm, alarms, fisher_upper, rotate_caller, wilson
from controller.store import Store


def configuration():
    return {"cohorts": [], "allocations": {"default": {"voice": {"V1": 1}, "welcome_message": {"W1": 1},
            "caller_id": {"D1": 0.5, "D2": 0.5}}}, "prompt_version": "P2",
            "schedule": {"hour_weights": {}, "lead_preferred_hour": {}}}


def row(dimension, variant, dials=400, connected=200, engaged=100, hallucinations=0, cohort="default"):
    return {"dimension": dimension, "variant": variant, "cohort_id": cohort, "dials": dials,
            "connected": connected, "engaged": engaged, "hallucinations": hallucinations}


class World:
    def __init__(self):
        self.config = configuration()
        self.now = "2027-01-04T10:00:00+05:30"
        self.version = 1
        self.credits = 200
        self.history = [{"version": 1, "proposal_id": None}]
        self.approvals = []
        self.paid = []
        self.writes = []
        self.lose_paid = False
        self.validation_rates = {"P1": 0.99, "P3": 1.0, "P4": 0.85}
        self.workflow = {
            "workflow_id": "wf", "tenant_id": "tenant-a", "dialling_window": [9, 21], "cadence": [2, 3, 3],
            "options": {"voice": ["V1"], "welcome_message": ["W1"], "caller_id": ["D1", "D2"],
                        "prompt_version": ["P1", "P2", "P3", "P4"]},
            "objective": {"primary": "engagement_rate", "guardrail": {"pickup_rate_max_drop": 0.02}},
            "governance": {"auto_apply": {"enabled": True, "allowed_dims": ["caller_id"], "max_shift": 0.5},
                           "approver_hours": [10, 19], "proposal_ttl_hours": 24, "max_requests_per_24h": 3,
                           "min_validation_pass_rate": 0.97},
        }

    def state(self):
        return {"ts": self.now, "scenario": "test", "last_event_id": 0,
                "finished": False, "credits_remaining": self.credits}

    def handler(self, request):
        path = request.url.path
        if request.method == "GET":
            data = {"/sim/state": self.state(), "/workflows/wf": self.workflow,
                    "/workflows/wf/config": {"version": self.version, "config": self.config},
                    "/workflows/wf/config/history": self.history, "/approvals": self.approvals}[path]
            return httpx.Response(200, json=data)
        body = json.loads(request.content)
        if path.startswith("/llm/") or path.startswith("/validation/"):
            self.paid.append((path, body))
            cost = 3 if path.startswith("/llm/") else (body["n"] + 99) // 100
            self.credits -= cost
            if path.startswith("/llm/"):
                data = {"suggestions": [{"prompt_version": "P3", "summary": "candidate"},
                                        {"prompt_version": "P4", "summary": "candidate"}]}
            else:
                data = {**body, "validation_run_id": f"val_{len(self.paid)}",
                        "pass_rate": self.validation_rates[body["prompt_version"]]}
            if self.lose_paid:
                self.lose_paid = False
                raise httpx.ReadError("paid response lost")
            return httpx.Response(200, json=data)
        self.writes.append((path, body))
        if path == "/approvals":
            data = {**body, "approval_id": "apr_test", "status": "pending", "created_at": self.now,
                    "apply_by": "2027-01-04T19:00:00+05:30"}
            self.approvals.append(data)
        else:
            if path.endswith("/apply"):
                approval = next(a for a in self.approvals if a["approval_id"] == body["approval_id"])
                body = approval
                approval["status"] = "applied"
            self.config = copy.deepcopy(body["proposed_config"])
            self.version += 1
            self.history.append({"version": self.version, "proposal_id": body["proposal_id"]})
            data = {"version": self.version, "config": self.config}
        return httpx.Response(200, json=data)


@contextmanager
def setup(database):
    world = World()
    with psycopg.connect(database, autocommit=True) as db:
        store = Store(db, "incidents", "http://simulator")
        with httpx.Client(base_url="http://simulator", transport=httpx.MockTransport(world.handler)) as client:
            api = SimulatorAPI(client)
            governance = Governance(api, store)
            yield world, store, api, governance, IncidentEngine(api, store, governance)


def seed(store, hour, sample, history=False):
    store.db.execute(
        "INSERT INTO hourly_metrics VALUES (%s,'wf',%s,%s,1,%s,%s,%s,%s,%s,%s,%s)",
        (store.run_id, history, f"2027-01-{'02' if history else '04'}T{hour:02d}:00:00+05:30",
         sample["cohort_id"], sample["dimension"], sample["variant"], sample["dials"], sample["connected"],
         sample["engaged"], sample["hallucinations"]),
    )


def seed_alarm(store, kind):
    for hour in (12, 13):
        if kind == "prompt_version":
            seed(store, hour, row(kind, "P1", 4000, 2000, 1000, 2), True)
        else:
            for did in ("D1", "D2"):
                seed(store, hour, row(kind, did, 4000, 2000, 1000), True)
    for hour in (9, 10):
        if kind == "prompt_version":
            seed(store, hour, row(kind, "P1", 4000, 2000, 1000, 2), True)
            seed(store, hour, row(kind, "P2", hallucinations=80))
        else:
            for did in ("D1", "D2"):
                seed(store, hour, row(kind, did, 4000, 2000, 1000), True)
            seed(store, hour, row(kind, "D1", 200, 2, 1))
            seed(store, hour, row(kind, "D2", 200, 100, 50))


def tick(world, api, engine, hour, minute=0):
    world.now = f"2027-01-04T{hour:02d}:{minute:02d}:00+05:30"
    current = api.get("/workflows/wf/config")
    engine.tick(world.state(), [(world.workflow, current)])


def test_wilson_and_population_floor():
    assert wilson(0, 0) == (0.0, 1.0)
    assert 0 < wilson(5, 10)[0] < 0.5 < wilson(5, 10)[1] < 1
    with pytest.raises(ValueError):
        wilson(2, 1)
    observations = alarms([row("prompt_version", "P2", 1, 1, 0, 1)],
                          [row("prompt_version", "P1", 4000, 2000, 1000, 0)], configuration())
    assert not any(item["signal"] for item in observations)


def test_exact_qa_test_handles_sparse_flags_without_normal_approximation():
    # For four flags split 4/0 between two groups of five, the tail is 6/252.
    assert fisher_upper(4, 5, 0, 5) == pytest.approx(6 / 252)
    assert fisher_upper(0, 100, 0, 1000) == pytest.approx(1)
    assert fisher_upper(7, 100, 15, 1000) < 0.01
    assert fisher_upper(2, 100, 15, 1000) > 0.01


def test_null_population_simulation_does_not_trigger_repeated_alarms():
    rng = random.Random(739)
    baseline = [row("caller_id", did, 4000, 1000, 500) for did in ("D1", "D2")]
    episodes = 0
    for _ in range(500):
        windows = []
        for _ in range(2):
            recent = [row("caller_id", did, 150, sum(rng.random() < 0.25 for _ in range(150)), 0)
                      for did in ("D1", "D2")]
            windows.append({item["subject"] for item in alarms(recent, baseline, configuration()) if item["signal"]})
        episodes += bool(windows[0] & windows[1])
    assert episodes <= 5


def test_null_qa_population_simulation_has_bounded_repeat_alarms():
    rng = random.Random(119)
    baseline = [row("prompt_version", "P1", 4000, 2000, 1000, 30)]
    episodes = 0
    for _ in range(500):
        signaled = []
        for _ in range(2):
            flags = sum(rng.random() < 0.015 for _ in range(70))
            current = [row("prompt_version", "P2", 280, 70, 35, flags)]
            signaled.append(any(alarm["signal"] for alarm in alarms(current, baseline, configuration())))
        episodes += all(signaled)
    assert episodes <= 5


def test_rotation_preserves_other_cohort_overrides_and_inheritance():
    config = configuration()
    config["cohorts"] = [{"id": "hi", "where": {"lang": ["hi"]}}, {"id": "en", "where": {"lang": ["en"]}}]
    config["allocations"]["hi"] = {"caller_id": {"D1": 0.3, "D2": 0.7}}
    proposed = rotate_caller(config, {"cohort": "default", "variant": "D1", "replacement": "D2"})
    assert proposed["allocations"]["default"]["caller_id"] == {"D2": 1.0}
    assert proposed["allocations"]["hi"]["caller_id"] == {"D1": 0.3, "D2": 0.7}
    assert proposed["allocations"]["en"]["caller_id"] == {"D1": 0.5, "D2": 0.5}


def test_completed_windows_not_overlapping_ticks_and_gap_breaks_streak(database):
    with setup(database) as (world, store, api, governance, engine):
        seed_alarm(store, "prompt_version")
        tick(world, api, engine, 10)
        tick(world, api, engine, 10, 15)
        tick(world, api, engine, 10, 45)
        assert store.open_incidents() == [] and world.paid == []
        tick(world, api, engine, 11)
        assert len(store.open_incidents()) == 1 and world.paid == []
        alarm = {"kind": "caller_id", "subject": "default:D1", "signal": True}
        first = store.detection_window("other", 1, "2027-01-04T09:00:00+05:30", alarm)
        second = store.detection_window("other", 1, "2027-01-04T11:00:00+05:30", alarm)
        assert first["streak"] == second["streak"] == 1


def test_validated_prompt_repair_goes_through_approval_and_is_verified(database):
    with setup(database) as (world, store, api, governance, engine):
        seed_alarm(store, "prompt_version")
        tick(world, api, engine, 10)
        tick(world, api, engine, 11)
        tick(world, api, engine, 11, 15)
        incident = store.open_incidents()[0]
        assert incident["data"]["candidate"] == "P1"  # Prior exposure precedes unknown LLM candidates.
        assert world.config["prompt_version"] == "P2" and world.writes == []
        tick(world, api, engine, 11, 30)
        governance.tick(world.now)
        assert world.writes[0][0] == "/approvals"
        assert world.writes[0][1]["evidence"]["validation_run_id"]
        world.approvals[0]["status"] = "approved"
        governance.tick(world.now)
        assert world.config["prompt_version"] == "P1"
        tick(world, api, engine, 11, 45)
        for hour in (12, 13):
            seed(store, hour, row("prompt_version", "P1"))
        tick(world, api, engine, 14)
        completed = store.incident(incident["incident_id"])
        assert completed["status"] == "resolved"
        assert completed["data"]["verification"]["after"]["hallucinations"] == 0
        assert len(world.paid) == 1 and world.credits == 195
        assert world.paid[0][1]["n"] == 500


def test_caller_rotation_is_governed_and_post_apply_pickup_is_verified(database):
    with setup(database) as (world, store, api, governance, engine):
        seed_alarm(store, "caller_id")
        tick(world, api, engine, 10)
        tick(world, api, engine, 11)
        incident = store.open_incidents()[0]
        assert world.writes == []
        governance.tick(world.now)
        assert world.config["allocations"]["default"]["caller_id"] == {"D2": 1.0}
        tick(world, api, engine, 11, 15)
        for hour in (12, 13):
            seed(store, hour, row("all", "*"))
        tick(world, api, engine, 14)
        assert store.incident(incident["incident_id"])["status"] == "resolved"
        assert world.paid == []


def test_lost_paid_response_never_repeats_charge(database):
    with setup(database) as (world, store, api, governance, engine):
        seed_alarm(store, "prompt_version")
        tick(world, api, engine, 10)
        world.lose_paid = True
        tick(world, api, engine, 11)
        tick(world, api, engine, 11, 15)
        record = store.db.execute("SELECT incident_id,status FROM incidents").fetchone()
        assert record[1] == "needs_review"
        restarted = IncidentEngine(api, store, governance)
        tick(world, api, restarted, 11, 30)
        assert len(world.paid) == 1 and world.credits == 195
        assert store.db.execute("SELECT status FROM external_actions").fetchone()[0] == "uncertain"
        world.version += 1
        tick(world, api, restarted, 11, 45)
        seed(store, 11, row("prompt_version", "P2", hallucinations=80))
        tick(world, api, restarted, 12)
        assert len(world.paid) == 1  # An unrelated config epoch must not bypass the review hold.


def test_successful_paid_response_is_recovered_without_rebuying(database):
    with setup(database) as (world, store, api, governance, engine):
        seed_alarm(store, "prompt_version")
        tick(world, api, engine, 10)
        tick(world, api, engine, 11)
        tick(world, api, engine, 11, 15)
        incident = store.open_incidents()[0]
        old = {key: value for key, value in incident["data"].items() if key not in {"validation", "candidate"}}
        store.update_incident(incident["incident_id"], "suggested", world.now, old)
        tick(world, api, IncidentEngine(api, store, governance), 11, 30)
        assert len(world.paid) == 1
        assert store.open_incidents()[0]["status"] == "validated"


def test_tenant_quota_and_credit_reserve_prevent_exhaustion(database):
    with setup(database) as (world, store, api, governance, engine):
        world.credits = 9
        seed_alarm(store, "prompt_version")
        tick(world, api, engine, 10)
        tick(world, api, engine, 11)
        tick(world, api, engine, 11, 15)
        assert world.credits == 9 and len(world.paid) == 0
        assert store.db.execute("SELECT status FROM incidents").fetchone()[0] == "needs_review"


def test_paid_intent_saved_before_send_and_uncertain_intent_not_retried(database):
    with setup(database) as (world, store, api, governance, engine):
        data = {"alarm": {}, "expected_prompt": "P2", "proposal_attempt": 0}
        store.save_incident("i", world.workflow, "prompt_version", world.now, data)
        incident = store.incident("i")
        request = {"workflow_id": "wf", "problem": "incident"}
        aid = hashlib.sha256(json.dumps(["i", "suggest", request], sort_keys=True).encode()).hexdigest()
        store.reserve_action(aid, incident, "suggest", 3, world.now, request)
        assert IncidentEngine(api, store, governance)._paid(incident, world.workflow, world.now, 1, "suggest", request, 3) is None
        assert world.paid == []
        assert store.incident("i")["status"] == "needs_review"


def test_supervisor_edit_during_monitoring_does_not_get_overwritten(database):
    with setup(database) as (world, store, api, governance, engine):
        seed_alarm(store, "prompt_version")
        for hour, minute in ((10, 0), (11, 0), (11, 15), (11, 30)):
            tick(world, api, engine, hour, minute)
        governance.tick(world.now)
        world.approvals[0]["status"] = "approved"
        governance.tick(world.now)
        incident = store.open_incidents()[0]
        world.config["prompt_version"] = "P3"
        world.version += 1
        tick(world, api, engine, 11, 45)
        assert store.incident(incident["incident_id"])["status"] == "superseded"
        assert world.config["prompt_version"] == "P3"


def test_safe_validation_does_not_prove_engagement_and_unsafe_prompt_is_not_restored(database):
    with setup(database) as (world, store, api, governance, engine):
        seed_alarm(store, "prompt_version")
        for hour, minute in ((10, 0), (11, 0), (11, 15), (11, 30)):
            tick(world, api, engine, hour, minute)
        governance.tick(world.now)
        world.approvals[0]["status"] = "approved"
        governance.tick(world.now)
        incident = store.open_incidents()[0]
        tick(world, api, engine, 11, 45)
        for hour in (12, 13):
            seed(store, hour, row("prompt_version", "P1", engaged=1))
        tick(world, api, engine, 14)
        state = store.incident(incident["incident_id"])
        assert state["status"] == "suggested"
        assert state["data"]["candidate_index"] == 1
        assert world.config["prompt_version"] == "P1" and not any(
            body.get("proposed_config", {}).get("prompt_version") == "P2" for _, body in world.writes)


def test_caller_guardrail_rollback_is_governed(database):
    with setup(database) as (world, store, api, governance, engine):
        seed_alarm(store, "caller_id")
        tick(world, api, engine, 10)
        tick(world, api, engine, 11)
        governance.tick(world.now)
        incident = store.open_incidents()[0]
        tick(world, api, engine, 11, 15)
        for hour in (12, 13):
            seed(store, hour, row("all", "*", engaged=1))
        tick(world, api, engine, 14)
        assert store.incident(incident["incident_id"])["status"] == "rollback"
        assert world.config["allocations"]["default"]["caller_id"] == {"D2": 1.0}
        governance.tick(world.now)
        assert world.config["allocations"]["default"]["caller_id"] == {"D1": 0.5, "D2": 0.5}
        tick(world, api, engine, 14, 15)
        assert store.incident(incident["incident_id"])["status"] == "needs_review"


def test_tenant_credit_attention_is_durable_and_round_robin(database):
    with setup(database) as (world, store, api, governance, engine):
        for iid, tenant in (("a1", "a"), ("a2", "a"), ("b1", "b")):
            store.save_incident(iid, {**world.workflow, "tenant_id": tenant}, "prompt_version", world.now, {})
        store.reserve_action("paid-a", store.incident("a1"), "suggest", 3, world.now, {})
        store.finish_action("paid-a", "succeeded", {})
        assert store.open_incidents()[0]["tenant_id"] == "b"
        assert store.credit_usage(200)["spending"][0]["cost"] == 3
        assert store.credit_usage(197)["initial"] == 200


def test_per_incident_limit_blocks_further_paid_calls(database):
    with setup(database) as (world, store, api, governance, engine):
        store.save_incident("i", world.workflow, "prompt_version", world.now, {})
        incident = store.incident("i")
        store.reserve_action("spent", incident, "validate", 12, world.now, {})
        store.finish_action("spent", "succeeded", {})
        assert engine._paid(incident, world.workflow, world.now, 1, "validate",
                            {"workflow_id": "wf", "prompt_version": "P1", "n": 300}, 3) is None
        assert world.paid == [] and store.incident("i")["status"] == "needs_review"


def test_repaired_global_prompt_checks_small_cohorts_separately(database):
    with setup(database) as (world, store, api, governance, engine):
        world.config["cohorts"] = [{"id": "small", "where": {"lang": ["ta"]}}]
        seed_alarm(store, "prompt_version")
        seed(store, 10, row("prompt_version", "P1", 4000, 2000, 1000, 0, "small"), True)
        seed(store, 10, row("prompt_version", "P2", cohort="small"))
        for hour in (12, 13):
            seed(store, hour, row("prompt_version", "P1", 4000, 2000, 1000, 0, "small"), True)
        for hour, minute in ((10, 0), (11, 0), (11, 15), (11, 30)):
            tick(world, api, engine, hour, minute)
        governance.tick(world.now)
        world.approvals[0]["status"] = "approved"
        governance.tick(world.now)
        incident = store.open_incidents()[0]
        tick(world, api, engine, 11, 45)
        for hour in (12, 13):
            seed(store, hour, row("prompt_version", "P1", 4000, 2000, 1200))
            seed(store, hour, row("prompt_version", "P1", engaged=1, cohort="small"))
        tick(world, api, engine, 14)
        result = store.incident(incident["incident_id"])
        assert result["status"] == "suggested"
        assert any(check["cohort_id"] == "small" and check["material_harm"] for check in result["data"]["guardrail_populations"])


def test_prompt_repair_preempts_pending_experiment_without_adopting_its_voice_change(database):
    with setup(database) as (world, store, api, governance, engine):
        world.workflow["options"]["voice"].append("V2")
        split = copy.deepcopy(world.config)
        split["allocations"]["default"]["voice"] = {"V1": 0.8, "V2": 0.2}
        pid = governance.plan("wf", split, decision_id="experiment:pending:start", base_version=world.version,
                              rationale="unapproved trial", summary="test voice")
        governance.tick(world.now)
        seed_alarm(store, "prompt_version")
        # Begin at the same simulated time; no preparation is allowed to move the clock backward.
        tick(world, api, engine, 11)
        seed(store, 11, row("prompt_version", "P2", hallucinations=80))
        seed(store, 11, row("prompt_version", "P1", 4000, 2000, 1000, 2), True)
        tick(world, api, engine, 12)
        tick(world, api, engine, 12, 15)
        tick(world, api, engine, 12, 30)
        assert store.proposal(pid)["status"] == "superseded"
        repair = store.open_incidents()[0]
        body = store.proposal(repair["proposal_id"])["body"]
        assert body["proposed_config"]["allocations"]["default"]["voice"] == {"V1": 1}


def test_incident_verification_does_not_attribute_clock_hour_pickup_to_prompt():
    objective = {"primary": "engagement_rate", "guardrail": {"pickup_rate_max_drop": 0.02}}
    before = row("prompt_version", "P2", 400, 86, 46, 5)
    after = row("prompt_version", "P1", 400, 84, 36, 2)
    historical_before = row("prompt_version", "P1", 5600, 1503, 821, 18)
    historical_after = row("prompt_version", "P1", 5600, 1232, 616, 18)
    assert historical_before["connected"] / historical_before["dials"] - after["connected"] / after["dials"] > 0.02
    assert fisher_upper(historical_before["connected"], historical_before["dials"], after["connected"], after["dials"]) < 0.01
    assert not adjusted_population_harm(before, after, historical_before, historical_after, objective)["material_harm"]
    after["engaged"] = 1
    assert adjusted_population_harm(before, after, historical_before, historical_after, objective)["material_harm"]
