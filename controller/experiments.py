"""One governed voice trial per workflow, fixed winner checkpoint, retained control."""

import copy
import hashlib
import json
from datetime import datetime, timedelta

from .policy import config_diff, distribution
from .statistics import evaluate, planned_samples


DURATION_HOURS = 72
TRIAL_SHARE = 0.2
WINNER_SHARE = 0.8


def applied_timestamp(value, state: dict | None = None) -> str:
    if type(value) is int and state is not None:
        origin = datetime.fromisoformat(state["ts"]) - timedelta(minutes=state["sim_minute"])
        return (origin + timedelta(minutes=value)).isoformat()
    if isinstance(value, str) and datetime.fromisoformat(value).tzinfo is not None:
        return datetime.fromisoformat(value).isoformat()
    raise ValueError("Applied config history needs a timestamp or simulated-minute offset")


def context_key(config: dict, objective: dict) -> str:
    context = {**config, "objective": objective, "allocations": {
        name: {dim: value for dim, value in dims.items() if dim != "voice"}
        for name, dims in config["allocations"].items()
    }}
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()


def voice_config(config: dict, cohort: str, control: str, challenger: str, share: float) -> dict:
    proposed = copy.deepcopy(config)
    if cohort == "default":
        for item in config["cohorts"]:
            name = item["id"]
            proposed["allocations"].setdefault(name, {}).setdefault("voice", distribution(config, name, "voice"))
    proposed["allocations"].setdefault(cohort, {})["voice"] = {control: 1 - share, challenger: share}
    return proposed


def restore_voice(base: dict, owned: dict, current: dict, cohort: str) -> dict:
    """Restore the tested voice; retain edits to other cohorts and all other settings."""
    desired = copy.deepcopy(current)
    if cohort != "default" and cohort not in {item["id"] for item in current["cohorts"]}:
        return desired
    actual = distribution(current, cohort, "voice")
    if actual not in (distribution(base, cohort, "voice"), distribution(owned, cohort, "voice")):
        raise ValueError("Supervisor changed the tested voice distribution")
    original = base["allocations"].get(cohort, {}).get("voice")
    target = desired["allocations"].setdefault(cohort, {})
    if original is None:
        target.pop("voice", None)
    else:
        target["voice"] = copy.deepcopy(original)
    for name, dimensions in owned["allocations"].items():
        if name == cohort or "voice" in base["allocations"].get(name, {}):
            continue
        target = desired["allocations"].get(name, {})
        if target.get("voice") == dimensions.get("voice"):
            target.pop("voice", None)
    desired["allocations"] = {name: value for name, value in desired["allocations"].items() if value}
    return desired


class ExperimentEngine:
    def __init__(self, api, store, governance):
        self.api, self.store, self.governance = api, store, governance

    def tick(self, state: dict, snapshots: list[tuple[dict, dict]]) -> None:
        now = state["ts"]
        definitions = {workflow["workflow_id"]: workflow for workflow, _ in snapshots}
        for experiment in self.store.experiments(active=True):
            if state["finished"]:
                self._mark(experiment, "unfinished", now, reason="Scenario ended; no early winner decision or late config write")
                continue
            workflow = definitions.get(experiment["workflow_id"])
            if workflow:
                self._advance(experiment, workflow, now)
        if state["finished"]:
            return
        remaining = state.get("end_minute", float("inf")) - state.get("sim_minute", 0)
        if remaining < DURATION_HOURS * 60:
            return
        for workflow, _ in snapshots:
            wid = workflow["workflow_id"]
            if self.store.experiments(wid, active=True) or self.store.experiment_blocked_by_incident(wid):
                continue
            if any(row["workflow_id"] == wid for row in self.store.active_proposals()):
                continue
            current = self.api.get(f"/workflows/{wid}/config")
            self._start(workflow, current, now)

    def _mark(self, experiment: dict, status: str, now: str, **details) -> None:
        self.store.update_experiment(experiment["experiment_id"], status, now, {**experiment["data"], **details})

    def _start(self, workflow: dict, current: dict, now: str) -> None:
        wid, config = workflow["workflow_id"], current["config"]
        previous = self.store.experiments(wid)
        if previous and datetime.fromisoformat(now) - previous[-1]["created_at"] < timedelta(hours=24):
            return
        history = self.store.historical_rates(wid)
        primary = workflow["objective"]["primary"]
        groups = {}
        for row in history:
            if row["dimension"] != "voice":
                continue
            name = row["cohort_id"]
            if name != "default" and name not in {item["id"] for item in config["cohorts"]}:
                continue
            groups.setdefault(name, []).append(row)
        if not groups:
            return
        cohort = sorted(groups, key=lambda name: (-sum(row["dials"] for row in groups[name]), name))[0]
        weights = distribution(config, cohort, "voice")
        if len(weights) != 1:
            return  # Existing client-owned mixtures are not overwritten to create a trial.
        control = next(iter(weights))
        context = context_key(config, workflow["objective"])
        tried = {row["data"]["plan"]["challenger"] for row in previous
                 if row["data"]["context"] == context and row["data"]["plan"]["control"] == control}
        candidates = sorted(set(workflow["options"]["voice"]) - {control} - tried)
        baseline = [row for row in groups[cohort] if row["variant"] == control]
        denominator = sum(row["connected"] if primary == "engagement_rate" else row["dials"] for row in baseline)
        numerator = sum(row["engaged"] if primary == "engagement_rate" else row["connected"] for row in baseline)
        if not candidates or denominator < 200:
            return
        index = len(previous) + 1
        alpha = 0.05 / (index * (index + 1))
        plan = {
            "control": control, "challenger": candidates[0], "objective": workflow["objective"],
            "trial_index": index, "alpha": alpha, "minimum_lift": 0.08,
            "min_primary": planned_samples(numerator / denominator, alpha), "minimum_people_per_arm": 100,
            "duration_hours": DURATION_HOURS, "trial_share": TRIAL_SHARE, "winner_share": WINNER_SHARE,
            "start_rule": "first observed call in the authorized config epoch and cohort",
            "rule_version": "clustered-fixed-v1", "safety_interval_hours": 1, "decay_interval_hours": 24,
        }
        eid = hashlib.sha256(json.dumps([self.store.run_id, wid, context, cohort, control, candidates[0], index]).encode()).hexdigest()
        split = voice_config(config, cohort, control, candidates[0], TRIAL_SHARE)
        data = {"cohort": cohort, "context": context, "plan": plan, "base_config": config, "split_config": split}
        try:
            with self.store.db.transaction():
                self.store.save_experiment(eid, wid, now, data)
                pid = self.governance.plan(
                    wid, split, decision_id=f"experiment:{eid}:start", base_version=current["version"],
                    rationale=f"Prospective voice trial; plan={json.dumps(plan)}", summary="Test one voice on 20% of this cohort",
                    evidence={"experiment_id": eid, "plan": plan},
                )
                self.store.update_experiment(eid, "planned", now, data, pid)
        except ValueError as exc:
            self.store.save_experiment(eid, wid, now, data)
            self.store.update_experiment(eid, "blocked", now, {**data, "reason": str(exc)})

    def _applied(self, experiment: dict, now: str) -> dict | None:
        proposal = self.store.proposal(experiment["proposal_id"])
        if proposal["status"] in {"planned", "submitted", "pending", "approved", "applying"}:
            return None
        if proposal["status"] != "applied":
            if experiment["status"] == "promoting":
                self._restore(experiment, now, f"Promotion {proposal['status']}; retire the completed trial", "blocked")
                return None
            terminal = "interrupted" if proposal["status"] in {"stale", "superseded"} else "blocked"
            self._mark(experiment, terminal, now, reason=f"Proposal {proposal['status']}; no unobserved exposure is evidence")
            return None
        entries = self.api.get(f"/workflows/{experiment['workflow_id']}/config/history")
        entry = next((row for row in entries if row.get("proposal_id") == proposal["proposal_id"]), None)
        if entry is None:
            raise ValueError("Applied experiment has no matching configuration history")
        value = entry["applied_at"]
        at = applied_timestamp(value, self.api.get("/sim/state") if type(value) is int else None)
        return {"version": entry["version"], "at": at, "config": proposal["body"]["proposed_config"]}

    def _advance(self, experiment: dict, workflow: dict, now: str) -> None:
        data, status = experiment["data"], experiment["status"]
        if status == "restoring":
            self._restore(experiment, now, data["restore_reason"], data["final_status"])
            return
        if status in {"planned", "promoting"}:
            applied = self._applied(experiment, now)
            if applied is None:
                if status == "promoting" and self.store.proposal(experiment["proposal_id"])["status"] in {"planned", "submitted", "pending", "approved", "applying"}:
                    self._pending_safety(experiment, now)
                return
            data = {**data, "owned_version": applied["version"], "owned_config": applied["config"], "owned_at": applied["at"]}
            data["trial_version" if status == "planned" else "promotion_version"] = applied["version"]
            status = "running" if status == "planned" else "monitoring"
            self.store.update_experiment(experiment["experiment_id"], status, now, data)
            experiment = {**experiment, "status": status, "data": data}
        current = self.api.get(f"/workflows/{experiment['workflow_id']}/config")
        if type(data["owned_at"]) is int:
            data = {**data, "owned_at": applied_timestamp(data["owned_at"], self.api.get("/sim/state"))}
            self.store.update_experiment(experiment["experiment_id"], status, now, data)
            experiment = {**experiment, "data": data}
        if (current["version"] != data["owned_version"] or workflow["objective"] != data["plan"]["objective"]
                or self.store.experiment_blocked_by_incident(experiment["workflow_id"])):
            self._restore(experiment, now, "Config epoch/objective changed or an incident took priority", "interrupted")
            return
        anchor = "started_at" if status == "running" else "monitor_started_at"
        if anchor not in data:
            first = self.store.first_exposure(experiment, data["owned_version"], data["owned_at"])
            if first is None:
                return
            data = {**data, anchor: first}
            if status == "running":
                data["checkpoint"] = (datetime.fromisoformat(first) + timedelta(hours=data["plan"]["duration_hours"])).isoformat()
            self.store.update_experiment(experiment["experiment_id"], status, now, data)
            experiment = {**experiment, "data": data}
        if status == "running":
            self._running(experiment, now)
        else:
            self._monitor(experiment, now)

    def _harm(self, rows: list[dict], plan: dict, look: int, *, decay: bool = False) -> dict | None:
        alpha = 0.01 / (plan["trial_index"] * (plan["trial_index"] + 1) * look * (look + 1) * 2)
        evidence = evaluate(rows, plan, alpha=alpha, minimum=50, people=50)
        main, guard = evidence["primary"], evidence["guardrail"]
        for contrast, margin in ((main, 0.02 if decay else plan["minimum_lift"]), (guard, evidence["guardrail_margin"])):
            if any(arm["people"] < 50 or arm["observations"] < 50 for arm in contrast["arms"].values()):
                continue
            if contrast["upper"] is not None and contrast["difference"] < -margin and contrast["upper"] < (0 if contrast is main else -margin):
                return evidence
            control, challenger = contrast["arms"][plan["control"]], contrast["arms"][plan["challenger"]]
            if challenger["people"] >= 100 and challenger["rate"] == 0 and control["rate"] is not None and control["rate"] >= 0.1:
                return {**evidence, "population_stop": "zero-success challenger population versus supported control"}
        return None

    def _running(self, experiment: dict, now: str) -> None:
        data, plan = experiment["data"], experiment["data"]["plan"]
        start, deadline, instant = map(datetime.fromisoformat, (data["started_at"], data["checkpoint"], now))
        if instant >= deadline:
            if "evaluation" not in data:
                rows = self.store.collect_exposure(experiment, "trial", data["owned_version"], start.isoformat(), deadline.isoformat())
                data = {**data, "evaluation": evaluate(rows, plan)}
                self.store.update_experiment(experiment["experiment_id"], "running", now, data)
                experiment = {**experiment, "data": data}
            if data["evaluation"]["decision"] == "winner":
                self._promote(experiment, now)
            else:
                self._restore(experiment, now, "Fixed checkpoint: " + data["evaluation"]["decision"], data["evaluation"]["decision"])
            return
        look = int((instant - start).total_seconds() // 3600)
        if look <= data.get("safety_look", 0):
            return
        end = start + timedelta(hours=look)
        rows = self.store.collect_exposure(experiment, "trial", data["owned_version"], start.isoformat(), end.isoformat())
        evidence = self._harm(rows, plan, look)
        self._mark(experiment, "running", now, safety_look=look, safety_checked_until=end.isoformat())
        if evidence:
            self._restore({**experiment, "data": {**data, "safety_evidence": evidence}}, now, "Population safety stop", "lost")

    def _promote(self, experiment: dict, now: str) -> None:
        data, eid, wid = experiment["data"], experiment["experiment_id"], experiment["workflow_id"]
        if any(row["workflow_id"] == wid for row in self.store.active_proposals()):
            return
        current = self.api.get(f"/workflows/{wid}/config")
        proposed = voice_config(current["config"], data["cohort"], data["plan"]["control"], data["plan"]["challenger"], WINNER_SHARE)
        with self.store.db.transaction():
            pid = self.governance.plan(
                wid, proposed, decision_id=f"experiment:{eid}:promote", base_version=current["version"],
                rationale=f"Fixed-checkpoint winner with guardrail non-inferiority: {json.dumps(data['evaluation'])}",
                summary="Promote supported voice to 80%, retaining 20% control", evidence={"experiment_id": eid, "evaluation": data["evaluation"]},
            )
            self.store.update_experiment(eid, "promoting", now, data, pid)

    def _pending_safety(self, experiment: dict, now: str) -> None:
        data = experiment["data"]
        if "checkpoint" not in data:
            return
        current = self.api.get(f"/workflows/{experiment['workflow_id']}/config")
        if current["version"] != data["owned_version"] or self.store.experiment_blocked_by_incident(experiment["workflow_id"]):
            self._restore(experiment, now, "Promotion became stale or incident took priority", "interrupted")
            return
        start, instant = datetime.fromisoformat(data["checkpoint"]), datetime.fromisoformat(now)
        look = int((instant - start).total_seconds() // 3600)
        if look <= data.get("pending_look", 0):
            return
        end = start + timedelta(hours=look)
        rows = self.store.collect_exposure(experiment, "promotion_wait", data["owned_version"], start.isoformat(), end.isoformat())
        evidence = self._harm(rows, data["plan"], look + data["plan"]["duration_hours"])
        self._mark(experiment, "promoting", now, pending_look=look)
        if evidence:
            self._restore({**experiment, "data": {**data, "safety_evidence": evidence}}, now, "Voice degraded while awaiting promotion", "lost")

    def _monitor(self, experiment: dict, now: str) -> None:
        data = experiment["data"]
        start = datetime.fromisoformat(data["monitor_started_at"])
        look = int((datetime.fromisoformat(now) - start).total_seconds() // (24 * 3600))
        if look <= data.get("decay_look", 0):
            return
        begin, end = start + timedelta(hours=24 * (look - 1)), start + timedelta(hours=24 * look)
        rows = self.store.collect_exposure(experiment, f"decay:{look}", data["owned_version"], begin.isoformat(), end.isoformat())
        evidence = self._harm(rows, data["plan"], look, decay=True)
        self._mark(experiment, "monitoring", now, decay_look=look,
                   last_decay_window={"start": begin.isoformat(), "end": end.isoformat(), "harm": evidence})
        if evidence:
            self._restore({**experiment, "data": {**data, "decay_evidence": evidence}}, now, "Winner decay or guardrail degradation", "rolled_back")

    def _restore(self, experiment: dict, now: str, reason: str, terminal: str) -> None:
        data, eid, wid = experiment["data"], experiment["experiment_id"], experiment["workflow_id"]
        decision_id = f"experiment:{eid}:restore"
        existing = self.store.decision_proposal(decision_id)
        if existing:
            if existing["status"] == "applied":
                self._mark(experiment, terminal, now, restore_reason=reason, final_status=terminal, cleanup_proposal_id=existing["proposal_id"])
            elif existing["status"] not in {"planned", "submitted", "pending", "approved", "applying"}:
                self._mark(experiment, "blocked", now, reason=f"Cleanup {existing['status']}; operator review required", restore_reason=reason)
            return
        data = {**data, "restore_reason": reason, "final_status": terminal}
        self.store.update_experiment(eid, "restoring", now, data)
        active = [row for row in self.store.active_proposals() if row["workflow_id"] == wid]
        if any(not row["decision_id"].startswith(f"experiment:{eid}:") or row["status"] in {"submitted", "applying"} for row in active):
            return
        current = self.api.get(f"/workflows/{wid}/config")
        owned = data.get("owned_config", data["split_config"])
        try:
            desired = restore_voice(data["base_config"], owned, current["config"], data["cohort"])
            if not config_diff(current["config"], desired):
                self._mark({**experiment, "data": data}, terminal, now, cleanup="Already restored externally")
                return
            with self.store.db.transaction():
                for proposal in active:
                    self.store.transition(proposal["proposal_id"], "superseded", now, {"reason": reason})
                pid = self.governance.plan(
                    wid, desired, decision_id=decision_id, base_version=current["version"], urgent=terminal in {"lost", "rolled_back"},
                    rationale=f"Restore only experiment-owned settings: {reason}", summary="Restore incumbent voice after experiment",
                    evidence={"experiment_id": eid, "reason": reason},
                )
                self.store.update_experiment(eid, "restoring", now, data, pid)
        except ValueError as exc:
            self._mark({**experiment, "data": data}, "interrupted", now, cleanup_conflict=str(exc))
