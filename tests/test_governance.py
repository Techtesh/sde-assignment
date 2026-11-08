import copy
import json
from contextlib import contextmanager
from datetime import datetime, timedelta

import httpx
import psycopg
import pytest

from controller.api import SimulatorAPI
from controller.governance import Governance
from controller.policy import cohort_id, decide_route, rebase_config
from controller.store import Store


def workflow():
    return {
        "workflow_id": "wf", "dialling_window": [9, 21], "cadence": [2, 3, 3],
        "options": {"voice": ["V1", "V2"], "welcome_message": ["W1", "W2"],
                    "caller_id": ["D1", "D2"], "prompt_version": ["P1", "P2"]},
        "governance": {"auto_apply": {"enabled": True, "allowed_dims": ["voice", "caller_id"], "max_shift": 0.2},
                       "approver_hours": [10, 19], "proposal_ttl_hours": 12, "max_requests_per_24h": 3},
    }


def config():
    return {
        "cohorts": [], "allocations": {"default": {
            "voice": {"V1": 1.0}, "welcome_message": {"W1": 1.0}, "caller_id": {"D1": 0.5, "D2": 0.5},
        }}, "prompt_version": "P1", "schedule": {"hour_weights": {}, "lead_preferred_hour": {}},
    }


class World:
    """HTTP fault harness; PostgreSQL remains real, including intent-before-send assertions."""

    def __init__(self):
        self.workflow = workflow()
        self.config = config()
        self.version = 1
        self.now = "2027-01-04T11:00:00+05:30"
        self.history = [{"version": 1, "proposal_id": None}]
        self.approvals = []
        self.writes = []
        self.lose_response = False
        self.fail_before_send = False
        self.http_error = None
        self.hide_approvals_once = False
        self.store = None

    def edit(self, cfg):
        self.config = cfg
        self.version += 1
        self.history.append({"version": self.version, "actor": "supervisor", "proposal_id": None})

    def handler(self, request):
        path = request.url.path
        if request.method == "GET":
            if path == "/workflows/wf":
                data = self.workflow
            elif path == "/workflows/wf/config":
                data = {"version": self.version, "config": self.config}
            elif path == "/workflows/wf/config/history":
                data = self.history
            elif path == "/approvals":
                data = [] if self.hide_approvals_once else self.approvals
                self.hide_approvals_once = False
            elif path == "/sim/state":
                data = {"ts": self.now, "scenario": "test", "last_event_id": 0, "finished": False}
            else:
                raise AssertionError(path)
            return httpx.Response(200, json=data)
        body = json.loads(request.content)
        self.writes.append((path, body))
        if self.fail_before_send:
            self.fail_before_send = False
            raise httpx.ConnectError("request never reached remote")
        if path == "/workflows/wf/apply":
            approval = next(a for a in self.approvals if a["approval_id"] == body["approval_id"])
            pid = approval["proposal_id"]
            body = approval["body"]
        else:
            pid = body["proposal_id"]
        local = self.store.proposal(pid)
        assert local is not None and local["status"] in {"submitted", "applying"}
        if self.http_error:
            status, error = self.http_error
            return httpx.Response(status, json={"error": error})
        if body["base_version"] != self.version:
            return httpx.Response(409, json={"error": "stale_base_version"})
        if path == "/approvals":
            if any(a["proposal_id"] == pid for a in self.approvals):
                return httpx.Response(409, json={"error": "duplicate_proposal_id"})
            approval = {
                "approval_id": f"apr_{len(self.approvals)}", "proposal_id": pid,
                "workflow_id": "wf", "status": "pending", "body": body,
                "created_at": self.now,
                "apply_by": (datetime.fromisoformat(self.now) + timedelta(hours=2)).isoformat(),
            }
            self.approvals.append(approval)
            data = approval
        else:
            self.config = copy.deepcopy(body["proposed_config"])
            self.version += 1
            self.history.append({"version": self.version, "proposal_id": pid})
            if path.endswith("/apply"):
                approval["status"] = "applied"
            data = {"version": self.version, "config": self.config}
        if self.lose_response:
            self.lose_response = False
            raise httpx.ReadError("remote committed; response lost")
        return httpx.Response(200, json=data)


@contextmanager
def setup(database):
    world = World()
    with psycopg.connect(database, autocommit=True) as db:
        store = Store(db, "governance", "http://simulator")
        world.store = store
        with httpx.Client(base_url="http://simulator", transport=httpx.MockTransport(world.handler)) as client:
            api = SimulatorAPI(client)
            yield world, store, api, Governance(api, store)


def plan(governance, world, decision="decision", share=0.5, urgent=False):
    proposed = copy.deepcopy(world.config)
    proposed["allocations"]["default"]["voice"] = {"V1": 1 - share, "V2": share}
    return governance.plan("wf", proposed, decision_id=decision, base_version=world.version, rationale="test population evidence",
                           summary="Test a voice challenger", urgent=urgent)


def test_policy_effective_cohort_inheritance_and_normalized_weights():
    old = config()
    old["cohorts"] = [{"id": "hi", "where": {"lang": ["hi"]}}]
    assert cohort_id(old, {"lang": "hi"}) == "hi"
    new = copy.deepcopy(old)
    new["allocations"]["hi"] = {"voice": {"V1": 0.8, "V2": 0.2}}
    assert decide_route(workflow(), old, new) == "auto"
    new["allocations"]["hi"]["voice"] = {"V1": 7, "V2": 3}
    assert decide_route(workflow(), old, new) == "approval"
    new = copy.deepcopy(old)
    new["allocations"]["default"]["caller_id"] = {"D1": 0.7, "D2": 0.3}
    assert decide_route(workflow(), old, new) == "auto"
    policy = workflow()
    policy["governance"]["auto_apply"]["enabled"] = False
    assert decide_route(policy, old, new) == "approval"


@pytest.mark.parametrize("weights", [{"V1": -1}, {"V1": 0}, {"V1": float("nan")},
                                     {"V1": True}, {"unknown": 1}, {"V1": 1e308, "V2": 1e308}])
def test_bad_allocations_are_blocked(weights):
    new = config()
    new["allocations"]["default"]["voice"] = weights
    with pytest.raises(ValueError):
        decide_route(workflow(), config(), new)


def test_rebase_preserves_unrelated_edit_and_refuses_overlapping_edit():
    base = config()
    desired = copy.deepcopy(base)
    desired["allocations"]["default"]["voice"] = {"V2": 1}
    current = copy.deepcopy(base)
    current["prompt_version"] = "P2"
    merged = rebase_config(base, desired, current)
    assert merged["prompt_version"] == "P2"
    assert merged["allocations"]["default"]["voice"] == {"V2": 1}
    current["allocations"]["default"]["voice"] = {"V1": 0.5, "V2": 0.5}
    with pytest.raises(ValueError, match="Supervisor conflict"):
        rebase_config(base, desired, current)


@pytest.mark.parametrize("share,expected_path", [(0.2, "/workflows/wf/config"), (0.5, "/approvals")])
def test_policy_route_and_durable_intent(database, share, expected_path):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world, share=share)
        assert store.proposal(pid)["status"] == "planned"
        assert world.writes == []
        assert plan(governance, world, share=share) == pid
        governance.tick(world.now)
        assert world.writes[0][0] == expected_path
        expected_status = "applied" if share == 0.2 else "pending"
        assert store.proposal(pid)["status"] == expected_status
        assert store.proposal(pid)["body"]["dry_run"]["estimates"][0]["projected_rates"] is None


@pytest.mark.parametrize("share", [0.2, 0.5])
def test_lost_submission_response_reconciles_without_resending(database, share):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world, share=share)
        world.lose_response = True
        with pytest.raises(httpx.ReadError):
            governance.tick(world.now)
        assert store.proposal(pid)["status"] == "submitted"
        Governance(api, store).tick(world.now)
        assert len(world.writes) == 1
        assert store.proposal(pid)["status"] == ("applied" if share == 0.2 else "pending")


def test_request_that_never_arrived_reuses_same_proposal_id(database):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world)
        world.fail_before_send = True
        with pytest.raises(httpx.ConnectError):
            governance.tick(world.now)
        Governance(api, store).tick(world.now)
        assert [body["proposal_id"] for _, body in world.writes] == [pid, pid]
        assert len(world.approvals) == 1


def test_lost_apply_response_does_not_apply_twice(database):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world)
        governance.tick(world.now)
        world.approvals[0]["status"] = "approved"
        world.lose_response = True
        with pytest.raises(httpx.ReadError):
            governance.tick(world.now)
        assert store.proposal(pid)["status"] == "applying"
        Governance(api, store).tick(world.now)
        assert store.proposal(pid)["status"] == "applied"
        assert sum(path.endswith("/apply") for path, _ in world.writes) == 1
        assert world.version == 2


def test_supervisor_change_stales_approval_and_explicit_reproposal_rebases(database):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world)
        governance.tick(world.now)
        current = copy.deepcopy(world.config)
        current["allocations"]["default"]["caller_id"] = {"D1": 0.6, "D2": 0.4}
        world.edit(current)
        world.approvals[0]["status"] = "approved"
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == "stale"
        assert len(world.writes) == 1
        new_pid = governance.repropose(pid, decision_id="fresh-decision", rationale="Fresh evidence after edit")
        replacement = store.proposal(new_pid)
        assert replacement["body"]["base_version"] == 2
        assert replacement["body"]["proposed_config"]["allocations"]["default"]["caller_id"] == {"D1": 0.6, "D2": 0.4}
        assert replacement["parent_id"] == pid and new_pid != pid
        governance.tick(world.now)
        assert store.proposal(new_pid)["status"] == "pending"


@pytest.mark.parametrize("terminal", ["rejected", "expired", "lapsed"])
def test_terminal_remote_status_never_silently_resubmits(database, terminal):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world)
        governance.tick(world.now)
        world.approvals[0]["status"] = terminal
        governance.tick(world.now)
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == terminal
        assert len(world.writes) == 1
        replacement = governance.repropose(pid, decision_id="fresh-decision", rationale="Fresh re-evaluation")
        assert replacement != pid


def test_approved_but_missed_apply_window_lapses_locally(database):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world)
        governance.tick(world.now)
        world.approvals[0]["status"] = "approved"
        world.approvals[0]["apply_by"] = world.now
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == "lapsed"
        assert len(world.writes) == 1


def test_approver_hours_and_reserved_incident_slot(database):
    with setup(database) as (world, store, api, governance):
        world.now = "2027-01-04T09:00:00+05:30"
        pid = plan(governance, world)
        governance.tick(world.now)
        assert world.writes == []
        world.now = "2027-01-04T10:00:00+05:30"
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == "pending"
        world.approvals[0]["status"] = "rejected"
        governance.tick(world.now)
        pid2 = plan(governance, world, decision="second")
        governance.tick(world.now)
        world.approvals[1]["status"] = "rejected"
        governance.tick(world.now)
        pid3 = plan(governance, world, decision="third")
        governance.tick(world.now)
        assert store.proposal(pid3)["status"] == "planned"
        assert len(world.writes) == 2
        store.transition(pid3, "superseded", world.now, {"reason": "incident takes priority"})
        urgent_pid = plan(governance, world, decision="incident", urgent=True)
        governance.tick(world.now)
        assert store.proposal(urgent_pid)["status"] == "pending"
        assert len(world.writes) == 3


def test_prompt_change_requires_validation_and_final_tick_is_read_only(database):
    with setup(database) as (world, store, api, governance):
        new = config()
        new["prompt_version"] = "P2"
        with pytest.raises(ValueError, match="validation_run_id"):
            governance.plan("wf", new, decision_id="prompt", base_version=world.version, rationale="incident", summary="repair")
        pid = plan(governance, world)
        governance.tick(world.now, allow_writes=False)
        assert world.writes == []
        assert store.proposal(pid)["status"] == "planned"


@pytest.mark.parametrize("http_status,error,expected", [
    (402, "credits_exhausted", "blocked"), (403, "auto_apply_not_permitted", "blocked"),
    (422, "invalid_config", "blocked"), (409, "stale_base_version", "stale"),
    (410, "apply_window_lapsed", "lapsed"),
])
def test_failed_write_is_recorded_without_blind_retry(database, http_status, error, expected):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world, share=0.2)
        world.http_error = (http_status, error)
        governance.tick(world.now)
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == expected
        assert len(world.writes) == 1


def test_external_approval_requests_count_toward_fatigue(database):
    with setup(database) as (world, store, api, governance):
        world.approvals = [
            {"proposal_id": "external-1", "created_at": world.now},
            {"proposal_id": "external-2", "created_at": world.now},
        ]
        pid = plan(governance, world)
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == "planned"
        assert world.writes == []


def test_http_5xx_leaves_uncertain_intent_for_reconciliation(database):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world)
        world.http_error = (503, "unavailable")
        with pytest.raises(httpx.HTTPStatusError):
            governance.tick(world.now)
        assert store.proposal(pid)["status"] == "submitted"
        world.http_error = None
        Governance(api, store).tick(world.now)
        assert store.proposal(pid)["status"] == "pending"
        assert [body["proposal_id"] for _, body in world.writes] == [pid, pid]


def test_duplicate_response_is_reconciled_not_assumed_applied(database):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world)
        world.approvals = [{
            "approval_id": "apr_existing", "proposal_id": pid, "workflow_id": "wf",
            "status": "pending", "created_at": world.now, "body": store.proposal(pid)["body"],
        }]
        world.hide_approvals_once = True
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == "pending"
        assert store.proposal(pid)["approval_id"] == "apr_existing"
        assert len(world.writes) == 1


def test_unresolved_duplicate_blocks_instead_of_resending_forever(database):
    with setup(database) as (world, store, api, governance):
        pid = plan(governance, world, share=0.2)
        world.http_error = (409, "duplicate_proposal_id")
        governance.tick(world.now)
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == "blocked"
        assert len(world.writes) == 1


def test_supervisor_edit_between_preparation_and_planning_is_not_blessed(database):
    with setup(database) as (world, store, api, governance):
        desired = config()
        desired["allocations"]["default"]["voice"] = {"V2": 1}
        edited = config()
        edited["prompt_version"] = "P2"
        world.edit(edited)
        with pytest.raises(ValueError, match="Base changed while preparing"):
            governance.plan("wf", desired, decision_id="old-intent", base_version=1,
                            rationale="old evidence", summary="change voice")
        assert store.active_proposals() == []
        assert world.writes == [] and world.config["prompt_version"] == "P2"


def test_urgent_request_waits_when_ttl_would_expire_before_approver_returns(database):
    with setup(database) as (world, store, api, governance):
        world.now = "2027-01-04T20:00:00+05:30"
        world.workflow["governance"]["approver_latency_minutes"] = [20, 120]
        pid = plan(governance, world, urgent=True)
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == "planned"
        assert world.writes == []
        world.now = "2027-01-05T10:00:00+05:30"
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == "pending"


def test_full_workday_latency_does_not_deadlock_approval_submission(database):
    with setup(database) as (world, store, api, governance):
        world.now = "2027-01-04T10:15:00+05:30"
        policy = world.workflow["governance"]
        policy["approver_hours"] = [10, 18]
        policy["approver_latency_minutes"] = [60, 480]
        policy["proposal_ttl_hours"] = 24
        pid = plan(governance, world)
        governance.tick(world.now)
        assert store.proposal(pid)["status"] == "pending"


@pytest.mark.parametrize("now,urgent,ttl,submitted", [
    ("2027-01-04T18:59:00+05:30", False, 15, False),
    ("2027-01-04T18:59:00+05:30", False, 16, True),
    ("2027-01-04T19:00:00+05:30", False, 24, False),
    ("2027-01-04T19:00:00+05:30", True, 15, False),
    ("2027-01-04T19:00:00+05:30", True, 16, True),
    ("2027-01-04T13:29:00+00:00", False, 16, True),
    ("2027-01-04T13:30:00+00:00", False, 24, False),
])
def test_closing_boundary_keeps_submission_hours_separate_from_ttl_feasibility(database, now, urgent, ttl, submitted):
    with setup(database) as (world, store, api, governance):
        world.now = now
        world.workflow["governance"].update(approver_latency_minutes=[2, 2], proposal_ttl_hours=ttl)
        pid = plan(governance, world, urgent=urgent)
        governance.tick(world.now)
        assert bool(world.writes) == submitted
        assert store.proposal(pid)["status"] == ("pending" if submitted else "planned")


def test_request_window_deduplicates_local_remote_ids_across_timezones(database):
    with setup(database) as (world, store, api, governance):
        world.now = "2027-01-05T11:00:00+05:30"
        old = plan(governance, world, decision="old")
        governance.tick(world.now)
        world.approvals[0]["created_at"] = "2027-01-04T05:31:00+00:00"  # 23h59 ago.
        world.approvals[0]["status"] = "rejected"
        governance.tick(world.now)
        store.db.execute("UPDATE proposals SET submitted_at=%s WHERE proposal_id=%s",
                         ("2027-01-04T11:01:00+05:30", old))
        assert store.recent_approval_ids("wf", world.now) == {old}
        new = plan(governance, world, decision="new")
        governance.tick(world.now)
        assert store.proposal(new)["status"] == "pending"  # One slot used, not two.
