"""Deterministic incident response. Every config write still belongs to Governance."""

import copy
import hashlib
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .governance import Governance
from .metrics import adjusted_population_harm, alarms, counts, fisher_upper, rotate_caller
from .policy import config_diff, distribution, rebase_config


RESERVE_CREDITS = 6
INCIDENT_CREDIT_LIMIT = 12
VALIDATION_N = 300


def hour_start(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp).astimezone(ZoneInfo("Asia/Kolkata")).replace(minute=0, second=0, microsecond=0)


class IncidentEngine:
    def __init__(self, api, store, governance: Governance):
        self.api, self.store, self.governance = api, store, governance
        self.paid_this_tick = False

    def tick(self, state: dict, snapshots: list[tuple[dict, dict]]) -> None:
        if state["finished"]:
            return
        self.paid_this_tick = False
        now = state["ts"]
        end = hour_start(now)
        start = end - timedelta(hours=1)
        self.store.credit_usage(state["credits_remaining"])
        tenants = max(1, len({workflow["tenant_id"] for workflow, _ in snapshots}))
        for workflow, current in snapshots:
            wid = workflow["workflow_id"]
            recent = self.store.window_metrics(wid, start.isoformat(), end.isoformat())
            baseline = self.store.window_metrics(wid, start.isoformat(), end.isoformat(), history=True)
            for alarm in alarms(recent, baseline, current["config"]):
                window = self.store.detection_window(wid, current["version"], start.isoformat(), alarm)
                if window["streak"] < 2:
                    continue
                if self.store.incident_held_for_review(wid, alarm["kind"], alarm["subject"]):
                    continue
                identity = [wid, current["version"], alarm["kind"], alarm["subject"], window["episode_start"].isoformat()]
                iid = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
                if self.store.incident(iid):
                    continue
                if any(row["workflow_id"] == wid and row["kind"] == alarm["kind"] for row in self.store.open_incidents()):
                    continue
                data = {"alarm": alarm, "epoch": current["version"], "rule_version": "hourly-v1",
                        "window_start": start.isoformat(), "window_end": end.isoformat(),
                        "proposal_attempt": 0, "candidate_index": 0, "expected_prompt": current["config"]["prompt_version"],
                        "guardrail_before": [row for row in recent if row["dimension"] == alarm["kind"]],
                        "guardrail_history_before": [row for row in baseline if row["dimension"] == alarm["kind"]]}
                self.store.save_incident(iid, workflow, alarm["kind"], now, data)
        definitions = {workflow["workflow_id"]: workflow for workflow, _ in snapshots}
        for incident in self.store.open_incidents():
            workflow = definitions.get(incident["workflow_id"])
            if workflow:
                self._service(incident, workflow, now, tenants)

    def _mark(self, incident: dict, status: str, now: str, **details) -> None:
        data = {**incident["data"], **details}
        self.store.update_incident(incident["incident_id"], status, now, data)
        if status == "needs_review":
            print(json.dumps({"alert": "incident_needs_review", "workflow_id": incident["workflow_id"],
                              "incident_id": incident["incident_id"], "reason": data.get("reason")}), flush=True)

    def _paid(self, incident: dict, workflow: dict, now: str, tenants: int,
              kind: str, request: dict, cost: int) -> dict | None:
        aid = hashlib.sha256(json.dumps([incident["incident_id"], kind, request], sort_keys=True).encode()).hexdigest()
        previous = self.store.action(aid)
        if previous:
            if previous["status"] == "succeeded":
                return previous["response"]
            self._mark(incident, "needs_review", now,
                       reason="Paid action has an uncertain/failed result; do not repeat its charge", action_id=aid)
            return None
        if self.paid_this_tick:
            return None
        state = self.api.get("/sim/state")
        usage = self.store.credit_usage(state["credits_remaining"])
        spent = usage["spending"]
        tenant_used = sum(row["cost"] for row in spent if row["tenant_id"] == incident["tenant_id"])
        incident_used = sum(row["cost"] for row in spent if row["incident_id"] == incident["incident_id"])
        quota = max(0, (usage["initial"] - RESERVE_CREDITS) / tenants)
        required = cost + ((VALIDATION_N + 99) // 100 if kind == "suggest" else 0)
        if (state["credits_remaining"] - required < RESERVE_CREDITS or tenant_used + required > quota
                or incident_used + required > INCIDENT_CREDIT_LIMIT):
            self._mark(incident, "needs_review", now, reason="Credit reserve, tenant quota, or incident limit reached")
            return None
        self.store.reserve_action(aid, incident, kind, cost, now, request)
        self.paid_this_tick = True
        path = "/llm/suggest-fixes" if kind == "suggest" else "/validation/runs"
        try:
            response = self.api.mutate("POST", path, request)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Paid response must be an object")
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
            # A transport/5xx/parse failure may have spent credits. No idempotency API exists here.
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                self.store.finish_action(aid, "failed", {"http_status": exc.response.status_code})
            self._mark(incident, "needs_review", now, reason=f"Paid action requires reconciliation: {type(exc).__name__}", action_id=aid)
            return None
        self.store.finish_action(aid, "succeeded", result)
        return result

    def _service(self, incident: dict, workflow: dict, now: str, tenants: int) -> None:
        data, status = incident["data"], incident["status"]
        wid = incident["workflow_id"]
        if status in {"proposed", "monitoring", "rollback"}:
            self._follow(incident, workflow, now)
            return
        if incident["kind"] == "caller_id":
            self._submit(incident, workflow, now)
            return
        current = self.api.get(f"/workflows/{wid}/config")
        if current["config"]["prompt_version"] != data["expected_prompt"]:
            self._mark(incident, "superseded", now, reason="Supervisor changed the incident prompt; re-detect on fresh evidence")
            return
        if status == "detected":
            if not set(workflow["options"]["prompt_version"]) - {data["expected_prompt"]}:
                self._mark(incident, "needs_review", now, reason="No alternative prompt is available under policy")
                return
            result = self._paid(incident, workflow, now, tenants, "suggest", {
                "workflow_id": wid,
                "problem": json.dumps({"incident_id": incident["incident_id"], "alarm": data["alarm"]}),
            }, 3)
            if result is None:
                return
            suggestions = result.get("suggestions")
            if not isinstance(suggestions, list) or any(not isinstance(row, dict) for row in suggestions):
                self._mark(incident, "needs_review", now, reason="Malformed LLM suggestions")
                return
            observed = self.store.historical_rates(wid)
            known = [row for row in observed if row["dimension"] == "prompt_version" and row["connected"] >= 200]
            known_ids = [row["variant"] for row in sorted(known, key=lambda row: (-row["connected"], row["variant"]))]
            suggested_ids = sorted({row.get("prompt_version") for row in suggestions
                                    if isinstance(row.get("prompt_version"), str)})
            candidates = list(dict.fromkeys(known_ids + suggested_ids))
            candidates = [value for value in candidates if value in workflow["options"]["prompt_version"]
                          and value != data["expected_prompt"]]
            self._mark(incident, "suggested", now, candidates=candidates, suggestions=result)
            return
        if status == "suggested":
            candidates = data["candidates"]
            index = data["candidate_index"]
            if index >= len(candidates):
                self._mark(incident, "needs_review", now, reason="No remaining supported prompt candidates")
                return
            prompt = candidates[index]
            result = self._paid(incident, workflow, now, tenants, "validate", {
                "workflow_id": wid, "prompt_version": prompt, "n": VALIDATION_N,
            }, (VALIDATION_N + 99) // 100)
            if result is None:
                return
            if (result.get("workflow_id") != wid or result.get("prompt_version") != prompt
                    or result.get("n") != VALIDATION_N or not isinstance(result.get("validation_run_id"), str)
                    or type(result.get("pass_rate")) not in (int, float) or not 0 <= result["pass_rate"] <= 1):
                self._mark(incident, "needs_review", now, reason="Validation response does not match its request")
                return
            if result["pass_rate"] < workflow["governance"]["min_validation_pass_rate"]:
                self._mark(incident, "suggested", now, candidate_index=index + 1, last_validation=result)
            else:
                self._mark(incident, "validated", now, candidate=prompt, validation=result)
            return
        if status in {"validated", "ready"}:
            self._submit(incident, workflow, now)

    def _submit(self, incident: dict, workflow: dict, now: str) -> None:
        data, iid, wid = incident["data"], incident["incident_id"], incident["workflow_id"]
        attempt = data["proposal_attempt"]
        decision_id = f"incident:{iid}:{attempt}"
        existing = self.store.decision_proposal(decision_id)
        if existing:
            self.store.update_incident(iid, "proposed", now, data, existing["proposal_id"])
            return
        current = self.api.get(f"/workflows/{wid}/config")
        if incident["kind"] == "prompt_version" and current["config"]["prompt_version"] != data["expected_prompt"]:
            self._mark(incident, "superseded", now, reason="Prompt changed before proposal; fresh detection required")
            return
        try:
            if "desired" in data:
                if data["before"]["cohorts"] != current["config"]["cohorts"]:
                    raise ValueError("Cohort definition changed")
                desired = rebase_config(data["before"], data["desired"], current["config"])
            elif incident["kind"] == "caller_id":
                if data["alarm"]["variant"] not in distribution(current["config"], data["alarm"]["cohort"], "caller_id"):
                    self._mark(incident, "resolved", now, reason="Degraded caller ID is already removed")
                    return
                desired = rotate_caller(current["config"], data["alarm"])
            else:
                desired = copy.deepcopy(current["config"])
                desired["prompt_version"] = data["candidate"]
            active = [row for row in self.store.active_proposals() if row["workflow_id"] == wid]
            replaced = None
            if active:
                previous = active[0]
                if previous["status"] in {"submitted", "applying"}:
                    return  # Governance must resolve uncertain writes before preemption.
                if previous["urgent"] and incident["kind"] != "prompt_version":
                    return
                combined = rebase_config(previous["base_config"], previous["body"]["proposed_config"], current["config"])
                if incident["kind"] == "prompt_version" and previous["urgent"]:
                    combined["prompt_version"] = data["candidate"]
                    desired = combined
                elif previous["urgent"]:
                    return
                replaced = previous["proposal_id"]
            data = {**data, "before": current["config"], "desired": desired}
            evidence = {"incident_id": iid, "detection": data["alarm"]}
            if incident["kind"] == "prompt_version":
                evidence["validation_run_id"] = data["validation"]["validation_run_id"]
            # Atomically replace queued intents; no external config write occurs in this transaction.
            with self.store.db.transaction():
                if replaced:
                    self.store.transition(replaced, "superseded", now, {"reason": "Replaced by incident repair", "incident_id": iid})
                self.store.update_incident(iid, "ready", now, data)
                pid = self.governance.plan(
                    wid, desired, decision_id=decision_id, base_version=current["version"], urgent=True, parent_id=replaced,
                    rationale=f"Incident {iid}: two completed hourly populations; {json.dumps(data['alarm'])}",
                    summary="Repair elevated hallucination flags" if incident["kind"] == "prompt_version" else "Rotate degraded caller ID",
                    evidence=evidence,
                )
                if replaced:
                    for other in self.store.open_incidents():
                        if other["proposal_id"] == replaced:
                            self.store.update_incident(other["incident_id"], "proposed", now, other["data"], pid)
                self.store.update_incident(iid, "proposed", now, data, pid)
        except ValueError as exc:
            self._mark(incident, "needs_review", now, reason=str(exc))

    def _follow(self, incident: dict, workflow: dict, now: str) -> None:
        data, iid = incident["data"], incident["incident_id"]
        proposal = self.store.proposal(incident["proposal_id"])
        if proposal["status"] in {"planned", "submitted", "pending", "approved", "applying"}:
            return
        if proposal["status"] != "applied":
            if proposal["status"] in {"rejected", "expired", "lapsed", "stale"} and data["proposal_attempt"] < 2:
                current = self.api.get(f"/workflows/{incident['workflow_id']}/config")
                end = hour_start(now)
                recent = self.store.window_metrics(incident["workflow_id"], (end - timedelta(hours=1)).isoformat(), end.isoformat())
                historical = self.store.window_metrics(incident["workflow_id"], (end - timedelta(hours=1)).isoformat(), end.isoformat(), history=True)
                fresh = next((row for row in alarms(recent, historical, current["config"])
                              if row["subject"] == data["alarm"]["subject"] and row["signal"]), None)
                if fresh:
                    self._mark(incident, "validated" if incident["kind"] == "prompt_version" else "detected", now,
                               alarm=fresh, proposal_attempt=data["proposal_attempt"] + 1)
                    return
            self._mark(incident, "needs_review", now, reason=f"Proposal ended as {proposal['status']}; no automatic stale retry")
            return
        if incident["status"] == "rollback":
            self._mark(incident, "needs_review", now, reason="Guardrail rollback applied; review incident before further changes")
            return
        current = self.api.get(f"/workflows/{incident['workflow_id']}/config")["config"]
        if current["cohorts"] != data["before"]["cohorts"]:
            self._mark(incident, "superseded", now, reason="Supervisor changed cohort definitions during verification")
            return
        if incident["kind"] == "prompt_version" and current["prompt_version"] != data["candidate"]:
            self._mark(incident, "superseded", now, reason="Supervisor changed the repair prompt during verification")
            return
        if incident["kind"] == "caller_id" and distribution(current, data["alarm"]["cohort"], "caller_id") != distribution(data["desired"], data["alarm"]["cohort"], "caller_id"):
            self._mark(incident, "superseded", now, reason="Supervisor changed caller-ID settings during verification")
            return
        if "applied_at" not in data:
            self._mark(incident, "monitoring", now, applied_at=now)
            return
        begin = hour_start(data["applied_at"]) + timedelta(hours=1)
        end = hour_start(now)
        if end <= begin:
            return
        rows = self.store.window_metrics(incident["workflow_id"], begin.isoformat(), end.isoformat())
        if incident["kind"] == "prompt_version":
            selected = [row for row in rows if row["dimension"] == "prompt_version" and row["variant"] == data["candidate"]
                        and row["cohort_id"] == data["alarm"]["cohort"]]
        else:
            selected = [row for row in rows if row["dimension"] == "all" and row["cohort_id"] == data["alarm"]["cohort"]]
        after = counts(selected)
        if after["dials"] < 200 or after["connected"] < 60:
            return
        # Match live pre/post populations and clock hours before attributing a change to a repair.
        historical = self.store.window_metrics(incident["workflow_id"], begin.isoformat(), end.isoformat(), history=True)
        checks = []
        dimension = incident["kind"]
        names = {row["cohort_id"] for row in rows if row["dimension"] == dimension}
        if dimension == "caller_id":
            names = {data["alarm"]["cohort"]}
        for name in sorted(names):
            population = after if dimension == "caller_id" else counts([
                row for row in rows if row["dimension"] == dimension and row["cohort_id"] == name and row["variant"] == data["candidate"]])
            reference = counts([row for row in data.get("guardrail_before", []) if row["cohort_id"] == name])
            history_pre = counts([row for row in data.get("guardrail_history_before", []) if row["cohort_id"] == name])
            history_post = counts([row for row in historical if row["dimension"] == dimension and row["cohort_id"] == name])
            check = adjusted_population_harm(reference, population, history_pre, history_post, workflow["objective"])
            checks.append({"cohort_id": name, "before": reference, "after": population, **check})
        data["guardrail_populations"] = checks
        harm = any(check["material_harm"] for check in checks)
        before = data["alarm"]["current"]
        if harm:
            if incident["kind"] == "caller_id":
                self._rollback_caller(incident, now, after)
            else:
                self._next_prompt(incident, now, after, "Observed engagement/guardrail degradation")
            return
        if incident["kind"] == "prompt_version":
            recovered = (before["hallucinations"] / before["connected"] - after["hallucinations"] / after["connected"] >= 0.02
                         and fisher_upper(before["hallucinations"], before["connected"], after["hallucinations"], after["connected"]) <= 0.05)
        else:
            recovered = (after["connected"] / after["dials"] - before["connected"] / before["dials"] >= 0.02
                         and fisher_upper(after["connected"], after["dials"], before["connected"], before["dials"]) <= 0.05)
        supported = bool(checks) and all(all(item["supported"] for item in check["checks"].values()) for check in checks)
        verification = {"after": after, "window_start": begin.isoformat(), "window_end": end.isoformat(),
                        "guardrail": "no detected material harm; not a non-inferiority result" if supported else "insufficient matched guardrail evidence",
                        "recovered": recovered}
        if recovered:
            self._mark(incident, "resolved", now, verification=verification)
        elif after["connected"] >= 300:
            if incident["kind"] == "prompt_version":
                self._next_prompt(incident, now, after, "Safety did not improve after application")
            else:
                self._mark(incident, "needs_review", now, reason="Caller-ID rotation has not recovered pickup", verification=verification)
        else:
            self._mark(incident, "monitoring", now, verification=verification)

    def _next_prompt(self, incident: dict, now: str, after: dict, reason: str) -> None:
        current = self.api.get(f"/workflows/{incident['workflow_id']}/config")
        if current["config"]["prompt_version"] != incident["data"]["candidate"]:
            self._mark(incident, "superseded", now, reason="Supervisor changed the repair prompt")
            return
        data = {key: value for key, value in incident["data"].items() if key not in {"before", "desired", "applied_at"}}
        data.update(candidate_index=data["candidate_index"] + 1, proposal_attempt=data["proposal_attempt"] + 1,
                    expected_prompt=current["config"]["prompt_version"], last_failure={"reason": reason, "after": after})
        # Do not restore a prompt already known to hallucinate to recover engagement.
        self.store.update_incident(incident["incident_id"], "suggested", now, data)

    def _rollback_caller(self, incident: dict, now: str, after: dict) -> None:
        decision_id = f"incident:{incident['incident_id']}:rollback"
        existing = self.store.decision_proposal(decision_id)
        if existing:
            self.store.update_incident(incident["incident_id"], "rollback", now, incident["data"], existing["proposal_id"])
            return
        current = self.api.get(f"/workflows/{incident['workflow_id']}/config")
        try:
            desired = rebase_config(incident["data"]["desired"], incident["data"]["before"], current["config"])
            if not config_diff(current["config"], desired):
                raise ValueError("Rollback settings already changed externally")
            if any(row["workflow_id"] == incident["workflow_id"] for row in self.store.active_proposals()):
                return
            pid = self.governance.plan(
                incident["workflow_id"], desired, decision_id=decision_id, base_version=current["version"],
                rationale=f"Observed guardrail harm after caller rotation: {json.dumps(after)}",
                summary="Roll back caller-ID rotation after material degradation", urgent=True,
            )
            self.store.update_incident(incident["incident_id"], "rollback", now,
                                       {**incident["data"], "rollback_evidence": after}, pid)
        except ValueError as exc:
            self._mark(incident, "needs_review", now, reason=f"Rollback conflict: {exc}")
