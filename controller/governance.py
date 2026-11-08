"""Durable intent, explicit policy routing, and reconciliation before every write."""

import hashlib
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .api import SimulatorAPI
from .policy import (
    ALLOCATION_DIMS, cohort_id, config_diff, decide_route, distribution, rebase_config,
)
from .store import Store
from .faults import crash_at


def proposal_facts(store: Store, workflow: dict, old: dict, new: dict, now: str) -> dict:
    groups = store.active_lead_groups(workflow, now)
    total = affected = 0
    global_change = old["prompt_version"] != new["prompt_version"] or old["schedule"] != new["schedule"]
    for features, count in groups:
        total += count
        before, after = cohort_id(old, features), cohort_id(new, features)
        if global_change or before != after or any(
            distribution(old, before, dim) != distribution(new, after, dim) for dim in ALLOCATION_DIMS
        ):
            affected += count
    rates = store.historical_rates(workflow["workflow_id"])
    estimates = []
    for change in config_diff(old, new):
        path = change["path"]
        if len(path) != 3 or old["cohorts"] != new["cohorts"]:
            estimates.append({"path": path, "projected_rates": None, "reason": "no supported historical replay"})
            continue
        name, dim = path[1:]
        observed = {row["variant"]: row for row in rates if row["cohort_id"] == name and row["dimension"] == dim}
        weights = distribution(new, name, dim)
        missing = [key for key in weights if key not in observed or not observed[key]["dials"]]
        if missing:
            estimates.append({"path": path, "projected_rates": None, "unsupported_options": sorted(missing)})
            continue
        pickup = sum(weight * observed[key]["connected"] / observed[key]["dials"] for key, weight in weights.items())
        concluded = sum(weight * observed[key]["engaged"] / observed[key]["dials"] for key, weight in weights.items())
        estimates.append({"path": path, "projected_rates": {
            "pickup_rate": pickup, "engagement_rate": concluded / pickup if pickup else None,
        }})
    return {
        "affected_leads": affected,
        "impact_score": affected / total if total else 0.0,
        "dry_run": {
            "as_of": now, "method": "observational historical reweighting, not causal lift",
            "population": "known nonconcluded leads within campaign lifespan; upper estimate",
            "known_active_leads": total, "impact_score_meaning": "affected share of known active leads",
            "historical_counts": rates, "estimates": estimates,
            "limitations": "No prediction for unseen variants or joint interactions; future uploads excluded",
        },
    }


class Governance:
    def __init__(self, api: SimulatorAPI, store: Store):
        self.api = api
        self.store = store

    def plan(self, workflow_id: str, config: dict, *, decision_id: str, base_version: int, rationale: str,
             summary: str, urgent: bool = False, evidence: dict | None = None,
             parent_id: str | None = None) -> str:
        if any(not isinstance(value, str) or not value.strip() for value in (decision_id, rationale, summary)):
            raise ValueError("A decision ID, rationale, and summary are required")
        if type(urgent) is not bool or (evidence is not None and not isinstance(evidence, dict)):
            raise ValueError("Urgency must be a boolean and evidence must be an object")
        existing = self.store.decision_proposal(decision_id)
        if existing:
            if existing["workflow_id"] != workflow_id or existing["body"]["proposed_config"] != config:
                raise ValueError("Decision ID already belongs to a different intent")
            return existing["proposal_id"]
        if any(row["workflow_id"] == workflow_id for row in self.store.active_proposals()):
            raise ValueError("Workflow already has an active proposal; batch changes before planning")
        workflow = self.api.get(f"/workflows/{workflow_id}")
        current = self.api.get(f"/workflows/{workflow_id}/config")
        if current["version"] != base_version:
            raise ValueError("Base changed while preparing proposal; re-evaluate against current config")
        state = self.api.get("/sim/state")
        if state["finished"]:
            raise ValueError("Cannot plan a new change after the scenario finishes")
        self.store.observe_state(state)
        route = decide_route(workflow, current["config"], config)
        evidence = evidence or {}
        if current["config"]["prompt_version"] != config["prompt_version"]:
            validation_id = evidence.get("validation_run_id")
            if not isinstance(validation_id, str) or not validation_id.strip():
                raise ValueError("Prompt changes require validation_run_id")
        proposal_id = hashlib.sha256(json.dumps(
            [self.store.run_id, decision_id], separators=(",", ":"), ensure_ascii=True,
        ).encode()).hexdigest()
        body = {
            "proposal_id": proposal_id, "workflow_id": workflow_id, "base_version": current["version"],
            "proposed_config": config, "change_summary": summary,
            "diff": {"changes": config_diff(current["config"], config)}, "rationale": rationale,
            "evidence": evidence, "expires_in_hours": workflow["governance"]["proposal_ttl_hours"],
            **proposal_facts(self.store, workflow, current["config"], config, state["ts"]),
        }
        self.store.save_proposal(body, decision_id, current["config"], route, state["ts"], urgent,
                                 parent_id, workflow["governance"])
        return proposal_id

    def repropose(self, proposal_id: str, *, decision_id: str, rationale: str,
                  evidence: dict | None = None) -> str:
        previous = self.store.proposal(proposal_id)
        if not previous or previous["status"] not in {"stale", "expired", "lapsed", "rejected"}:
            raise ValueError("Only a terminal unsuccessful proposal can be re-evaluated")
        current = self.api.get(f"/workflows/{previous['workflow_id']}/config")
        merged = rebase_config(previous["base_config"], previous["body"]["proposed_config"], current["config"])
        return self.plan(
            previous["workflow_id"], merged, decision_id=decision_id, rationale=rationale,
            base_version=current["version"],
            summary=previous["body"]["change_summary"], urgent=previous["urgent"],
            evidence=evidence, parent_id=proposal_id,
        )

    def _write(self, proposal: dict, status: str, now: str, method: str, path: str, body: dict):
        pid = proposal["proposal_id"]
        self.store.transition(pid, status, now, {"method": method, "path": path, "request": body})
        crash_at("after_intent")
        try:
            response = self.api.mutate(method, path, body)
        except httpx.TransportError as exc:
            self.store.transition(pid, status, now, {"uncertain": type(exc).__name__})
            raise
        if response.status_code >= 500:
            self.store.transition(pid, status, now, {"uncertain_http_status": response.status_code})
            response.raise_for_status()
        if response.is_success:
            crash_at("after_post" if path == "/approvals" else "after_apply")
        return response

    def tick(self, now: str, *, allow_writes: bool = True) -> None:
        for proposal in self.store.active_proposals():
            self._reconcile(proposal, now, allow_writes)

    def _reconcile(self, proposal: dict, now: str, allow_writes: bool) -> None:
        pid, wid = proposal["proposal_id"], proposal["workflow_id"]
        body = proposal["body"]
        history = self.api.get(f"/workflows/{wid}/config/history")
        applied = next((entry for entry in history if entry.get("proposal_id") == pid), None)
        if applied:
            self.store.transition(pid, "applied", now, {"config_history": applied})
            return
        remote = None
        approvals = []
        if proposal["route"] == "approval":
            approvals = self.api.get("/approvals", workflow_id=wid)
            remote = next((entry for entry in approvals
                           if entry["proposal_id"] == pid), None)
            if remote:
                status = remote["status"]
                if status not in {"pending", "approved", "applied", "rejected", "expired", "lapsed"}:
                    raise ValueError(f"Unknown remote approval status: {status}")
                self.store.transition(pid, status, now, remote, remote["approval_id"])
                if status not in {"pending", "approved"}:
                    return
        current = self.api.get(f"/workflows/{wid}/config")
        if current["version"] != body["base_version"]:
            self.store.transition(pid, "stale", now, {
                "current_version": current["version"], "current_config": current["config"],
                "reason": "Base changed; a fresh decision and evidence are required before re-proposal",
            })
            return
        if remote and remote["status"] == "approved":
            if datetime.fromisoformat(now) >= datetime.fromisoformat(remote["apply_by"]):
                self.store.transition(pid, "lapsed", now, remote)
                return
        if not allow_writes:
            return
        if remote:
            if remote["status"] == "pending":
                return
            response = self._write(proposal, "applying", now, "POST", f"/workflows/{wid}/apply",
                                   {"approval_id": remote["approval_id"]})
        elif proposal["route"] == "auto":
            workflow = self.api.get(f"/workflows/{wid}")
            if decide_route(workflow, current["config"], body["proposed_config"]) != "auto":
                self.store.transition(pid, "blocked", now, {"reason": "Auto-apply policy changed; fresh proposal required"})
                return
            request = {key: body[key] for key in (
                "proposal_id", "base_version", "proposed_config", "rationale", "evidence",
            )}
            response = self._write(proposal, "submitted", now, "PUT", f"/workflows/{wid}/config", request)
        else:
            workflow = self.api.get(f"/workflows/{wid}")
            policy = workflow["governance"]
            hour = datetime.fromisoformat(now).astimezone(ZoneInfo("Asia/Kolkata")).hour
            start, end = policy["approver_hours"]
            if not proposal["urgent"] and not start <= hour < end:
                return
            instant = datetime.fromisoformat(now).astimezone(ZoneInfo("Asia/Kolkata"))
            latency = timedelta(minutes=max(policy.get("approver_latency_minutes", [0])))
            ready = instant + latency
            midnight = ready.replace(hour=0, minute=0, second=0, microsecond=0)
            opens = midnight + timedelta(hours=start)
            closes = midnight + timedelta(hours=end)
            if ready < opens:
                latest_decision = opens
            elif ready >= closes:
                latest_decision = opens + timedelta(days=1)
            else:
                latest_decision = ready
            if latest_decision >= instant + timedelta(hours=body["expires_in_hours"]):
                return  # Keep intent queued until its TTL can survive approver availability.
            cutoff = datetime.fromisoformat(now) - timedelta(hours=24)
            remote_ids = {entry["proposal_id"] for entry in approvals
                          if datetime.fromisoformat(entry["created_at"]) > cutoff}
            used = len(self.store.recent_approval_ids(wid, now) | remote_ids)
            maximum = policy["max_requests_per_24h"]
            reserve = 1 if not proposal["urgent"] and maximum > 1 else 0
            limit = maximum - reserve
            # Retrying the same persisted intent does not consume another local request slot.
            if proposal["submitted_at"] is None and used >= limit:
                return
            response = self._write(proposal, "submitted", now, "POST", "/approvals", body)
        data = response.json()
        if response.is_success:
            if remote or proposal["route"] == "auto":
                self.store.transition(pid, "applied", now, {"result": data})
            else:
                self.store.transition(pid, data["status"], now, data, data["approval_id"])
            return
        error = json.dumps(data)
        if response.status_code == 409 and "duplicate_proposal_id" in error:
            # A duplicate is not proof of approval/application. Reconcile before another write.
            self._reconcile(self.store.proposal(pid), now, False)
            if self.store.proposal(pid)["status"] in {"submitted", "applying"}:
                self.store.transition(pid, "blocked", now, {
                    "reason": "Duplicate ID has no matching remote approval or configuration history",
                    "result": data,
                })
            return
        status = "blocked"
        if response.status_code == 409 and "stale_base_version" in error:
            status = "stale"
        elif response.status_code == 410:
            status = "lapsed"
        self.store.transition(pid, status, now, {"http_status": response.status_code, "result": data})
