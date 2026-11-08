"""Opt-in governance smoke test. Mutates a dedicated simulator through HTTP only."""

import copy
import json
import os

import httpx
import psycopg
import pytest

from controller.__main__ import drain
from controller.api import SimulatorAPI
from controller.governance import Governance
from controller.policy import decide_route, distribution
from controller.store import Store


class LoseApprovalResponse(httpx.Client):
    """Send the real request, then lose one successful response at the client boundary."""

    dropped = False

    def request(self, method, url, *args, **kwargs):
        response = super().request(method, url, *args, **kwargs)
        if method == "POST" and url == "/approvals" and response.is_success and not self.dropped:
            self.dropped = True
            response.close()
            raise httpx.ReadError("injected loss after real simulator accepted approval")
        return response


def test_real_governance_auto_approval_and_restart(database):
    url = os.environ.get("GOV_SIM_URL")
    if not url:
        pytest.skip("Set GOV_SIM_URL to a dedicated fresh simulator; this test advances and changes it")
    run_id = "governance_live"
    with LoseApprovalResponse(base_url=url, timeout=120) as client:
        api = SimulatorAPI(client)
        state = api.get("/sim/state")
        initial_credits = state["credits_remaining"]
        assert state["sim_minute"] <= 600 and not api.get("/approvals"), "Use a fresh dedicated simulator before D0 10:00"
        assert all(w["current_version"] == 1 for w in api.get("/workflows"))
        if state["sim_minute"] < 600:
            response = client.post("/sim/advance", json={"minutes": 600 - state["sim_minute"]})
            response.raise_for_status()
        state = api.get("/sim/state")
        workflows = sorted(api.get("/workflows"), key=lambda item: item["workflow_id"])
        with psycopg.connect(database, autocommit=True) as db:
            store = Store(db, run_id, url)
            store.observe_state(state)
            drain(api, store)
            governance = Governance(api, store)
            auto_workflow = next(w for w in workflows if w["governance"]["auto_apply"]["enabled"]
                                 and "caller_id" in w["governance"]["auto_apply"]["allowed_dims"]
                                 and w["governance"]["auto_apply"]["max_shift"] > 0
                                 and len(w["options"]["caller_id"]) > 1)
            wid = auto_workflow["workflow_id"]
            current = api.get(f"/workflows/{wid}/config")
            proposed = copy.deepcopy(current["config"])
            weights = distribution(proposed, "default", "caller_id")
            donor = sorted(weights)[0]
            receiver = next(option for option in auto_workflow["options"]["caller_id"] if option != donor)
            shift = min(0.05, weights[donor] / 2, auto_workflow["governance"]["auto_apply"]["max_shift"] / 2)
            weights[donor] -= shift
            weights[receiver] = weights.get(receiver, 0) + shift
            proposed["allocations"]["default"]["caller_id"] = weights
            auto_pid = governance.plan(
                wid, proposed, decision_id="api-auto", base_version=current["version"], rationale="Integration test of signed policy; no lift claim",
                summary="Small caller-ID shift for API verification",
            )
            governance.tick(state["ts"])
            assert store.proposal(auto_pid)["status"] == "applied"
            history = api.get(f"/workflows/{wid}/config/history")
            assert sum(item.get("proposal_id") == auto_pid for item in history) == 1

            for candidate in workflows:
                approval_wid = candidate["workflow_id"]
                current = api.get(f"/workflows/{approval_wid}/config")
                desired = copy.deepcopy(current["config"])
                voices = distribution(desired, "default", "voice")
                challenger = next((v for v in candidate["options"]["voice"] if v not in voices), None)
                if challenger is None:
                    continue
                desired["allocations"]["default"]["voice"] = {challenger: 1.0}
                if decide_route(candidate, current["config"], desired) == "approval":
                    break
            else:
                pytest.fail("Dedicated scenario has no voice change that requires approval")
            approval_pid = governance.plan(
                approval_wid, desired, decision_id="api-approval", base_version=current["version"],
                rationale="Integration test of approval/recovery; no winner or lift claim",
                summary="Voice change for governance API verification",
            )
            with pytest.raises(httpx.ReadError, match="injected loss"):
                governance.tick(state["ts"])
            assert store.proposal(approval_pid)["status"] == "submitted"
            remote = [entry for entry in api.get("/approvals", workflow_id=approval_wid)
                      if entry["proposal_id"] == approval_pid]
            assert len(remote) == 1

        # A new PostgreSQL session and controller reconcile the request with its response lost.
        with psycopg.connect(database, autocommit=True) as restarted_db:
            restarted = Store(restarted_db, run_id, url)
            governance = Governance(api, restarted)
            governance.tick(state["ts"])
            assert restarted.proposal(approval_pid)["status"] == "pending"
            for _ in range(96):
                api.advance()
                state = api.get("/sim/state")
                restarted.observe_state(state)
                drain(api, restarted)
                governance.tick(state["ts"])
                status = restarted.proposal(approval_pid)["status"]
                if status not in {"pending", "approved", "applying"}:
                    break
            assert status == "applied", restarted.proposal(approval_pid)["response"]
            history = api.get(f"/workflows/{approval_wid}/config/history")
            assert sum(item.get("proposal_id") == approval_pid for item in history) == 1
            assert sum(entry["proposal_id"] == approval_pid for entry in
                       api.get("/approvals", workflow_id=approval_wid)) == 1
            assert api.get("/sim/state")["credits_remaining"] == initial_credits
            print(json.dumps({"step2": "passed", "auto_apply_count": 1, "approval_apply_count": 1,
                              "lost_response_reconciled": True, "duplicate_requests": 0,
                              "duplicate_applications": 0, "credits_used": 0}))
