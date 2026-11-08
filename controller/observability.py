"""Read-only supervisor and audit views, independent of the controller's writer lock."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row


def rows(db, query: str, params: tuple) -> list[dict]:
    with db.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(query, params).fetchall()


def status(db, run_id: str) -> dict:
    run = rows(db, "SELECT * FROM controller_runs WHERE run_id=%s", (run_id,))
    if not run:
        raise ValueError(f"Unknown run ID: {run_id}")
    state = run[0]["state"]
    now = state.get("ts")
    ingested = db.execute("SELECT COALESCE(max(event_id),0) FROM events WHERE run_id=%s", (run_id,)).fetchone()[0]
    tick = rows(db, "SELECT ts,recorded_at,metrics,EXTRACT(epoch FROM clock_timestamp()-recorded_at)::float "
                    "AS wall_age_seconds FROM loop_ticks WHERE run_id=%s ORDER BY ts DESC LIMIT 1", (run_id,))
    experiments = rows(db, "SELECT workflow_id,experiment_id,status,proposal_id,data->>'cohort' AS cohort_id,data->'plan' AS plan, "
                          "data->'evaluation' AS result,data->'checkpoint' AS checkpoint FROM experiments "
                          "WHERE run_id=%s ORDER BY workflow_id,created_at", (run_id,))
    proposals = rows(db, "SELECT workflow_id,proposal_id,status,route,urgent,approval_id,created_at, "
                        "body->>'change_summary' AS summary,body->'impact_score' AS impact_score,response->>'apply_by' AS apply_by, "
                        "EXTRACT(epoch FROM %s::timestamptz-created_at)::float/3600 AS age_sim_hours "
                        "FROM proposals WHERE run_id=%s AND status IN "
                        "('planned','submitted','pending','approved','applying') "
                        "ORDER BY urgent DESC,created_at,workflow_id", (now, run_id))
    decisions = rows(db, "SELECT source,count(*) AS transitions FROM ( "
                        "SELECT 'proposal' AS source,ts FROM proposal_audit WHERE run_id=%s UNION ALL "
                        "SELECT 'incident',ts FROM incident_audit WHERE run_id=%s UNION ALL "
                        "SELECT 'experiment',ts FROM experiment_audit WHERE run_id=%s) a "
                        "WHERE ts > %s::timestamptz-interval '1 hour' AND ts<=%s::timestamptz GROUP BY source",
                     (run_id, run_id, run_id, now, now))
    view = {
        "run_id": run_id, "as_of": now, "finished": state.get("finished"),
        "health": {"last_tick": tick[0] if tick else None, "ingested_event_id": ingested,
                   "event_backlog_at_last_observation": max(0, state.get("last_event_id", 0)-ingested),
                   "chunk_backlog_at_last_observation": max(0, state.get("chunks", 0)-db.execute(
                       "SELECT count(*) FROM ingested_chunks WHERE run_id=%s", (run_id,)).fetchone()[0]),
                   "starts_without_sim_progress_last_5_wall_minutes": db.execute(
                       "SELECT count(*) FROM loop_starts WHERE run_id=%s AND started_at>clock_timestamp()-interval '5 minutes' AND sim_ts=%s",
                       (run_id, now)).fetchone()[0],
                   "chunk_checkpoints": rows(db, "SELECT kind,max(chunk) AS last_chunk,count(*) AS chunks "
                                                 "FROM ingested_chunks WHERE run_id=%s GROUP BY kind", (run_id,)),
                   "new_proposals_last_sim_hour": db.execute(
                       "SELECT count(*) FROM proposals WHERE run_id=%s AND created_at>%s::timestamptz-interval '1 hour' "
                       "AND created_at<=%s::timestamptz", (run_id, now, now)).fetchone()[0],
                   "decision_transitions_last_sim_hour": decisions},
        "recent_metrics": rows(db, "SELECT workflow_id,cohort_id,sum(dials)::bigint AS dials,sum(connected)::bigint AS connected, "
                                   "sum(engaged)::bigint AS engaged,sum(hallucinations)::bigint AS hallucinations, "
                                   "sum(connected)::float/NULLIF(sum(dials),0) AS pickup_rate, "
                                   "sum(engaged)::float/NULLIF(sum(connected),0) AS engagement_rate "
                                   "FROM hourly_metrics WHERE run_id=%s AND NOT history AND dimension='all' "
                                   "AND hour>=date_trunc('hour',%s::timestamptz,'Asia/Kolkata')-interval '24 hours' "
                                   "AND hour<date_trunc('hour',%s::timestamptz,'Asia/Kolkata') "
                                   "GROUP BY workflow_id,cohort_id ORDER BY workflow_id,cohort_id", (run_id, now, now)),
        "cohorts": rows(db, "SELECT h.workflow_id,h.version,h.snapshot->'config'->'cohorts' AS cohorts "
                            "FROM config_history h JOIN (SELECT workflow_id,max(version) AS version "
                            "FROM config_history WHERE run_id=%s GROUP BY workflow_id) c "
                            "USING(workflow_id,version) WHERE h.run_id=%s ORDER BY workflow_id", (run_id, run_id)),
        "experiments": experiments, "pending_proposals": proposals,
        "recent_changes": rows(db, "SELECT workflow_id,ts,actor,evidence FROM audit_log "
                                   "WHERE run_id=%s AND kind='config_changed' ORDER BY ts DESC,event_id DESC LIMIT 20", (run_id,)),
        "open_incidents": rows(db, "SELECT workflow_id,incident_id,kind,status,created_at,proposal_id,data "
                                   "FROM incidents WHERE run_id=%s AND status NOT IN ('resolved','superseded') "
                                   "ORDER BY created_at,workflow_id", (run_id,)),
        "credits": {"remaining_at_last_observation": state.get("credits_remaining"),
                    "by_workflow": rows(db, "SELECT i.workflow_id,a.status,sum(a.cost) AS credits "
                                            "FROM external_actions a JOIN incidents i USING(run_id,incident_id) "
                                            "WHERE a.run_id=%s GROUP BY i.workflow_id,a.status ORDER BY i.workflow_id,a.status", (run_id,))},
    }
    alerts = []
    if not view["finished"]:
        if tick and float(tick[0]["wall_age_seconds"]) > 120:
            alerts.append({"severity": "page", "reason": "No completed tick for over 120 wall seconds",
                           "action": "Check controller process, simulator health and PostgreSQL activity; restart with the same run ID"})
        for incident in view["open_incidents"]:
            if incident["status"] == "needs_review":
                alerts.append({"severity": "page" if incident["kind"] == "prompt_version" else "ticket",
                               "workflow_id": incident["workflow_id"], "incident_id": incident["incident_id"],
                               "reason": incident["data"].get("reason"),
                               "action": "Inspect incident evidence and paid-action ledger; reconcile before authorizing another action"})
            elif incident["data"].get("supervisor_alert"):
                alerts.append({"workflow_id": incident["workflow_id"], "incident_id": incident["incident_id"],
                               **incident["data"]["supervisor_alert"]})
            elif now and (datetime.fromisoformat(now)-incident["created_at"]).total_seconds()>6*3600:
                alerts.append({"severity": "ticket", "workflow_id": incident["workflow_id"],
                               "reason": "Incident open for over six simulated hours",
                               "action": "Inspect incident evidence, current config and pending permission; escalate a safety issue"})
        for proposal in proposals:
            if proposal["apply_by"] and now and (datetime.fromisoformat(proposal["apply_by"])-datetime.fromisoformat(now)).total_seconds()<=1800:
                alerts.append({"severity": "page", "workflow_id": proposal["workflow_id"], "proposal_id": proposal["proposal_id"],
                               "reason": "Approved proposal is within 30 simulated minutes of apply_by or overdue",
                               "action": "Reconcile approval and current base version immediately; do not bypass expiry or governance"})
        if state.get("credits_remaining", 6)<6:
            alerts.append({"severity": "ticket", "reason": "Credits below the six-credit reserve",
                           "action": "Inspect the paid-action ledger and other spenders; suspend new paid exploration"})
        if view["health"]["starts_without_sim_progress_last_5_wall_minutes"]>=3:
            alerts.append({"severity": "page", "reason": "Three starts in five wall minutes without simulated progress",
                           "action": "Inspect the last exception, database and simulator; stop blind restarts until the cause is understood"})
        for experiment in experiments:
            if experiment["status"] == "blocked":
                alerts.append({"severity": "ticket", "workflow_id": experiment["workflow_id"],
                               "reason": "Experiment blocked", "action": "Inspect experiment audit and proposal status, including any cleanup conflict"})
    view["alerts"] = alerts
    return view


def status_text(view: dict) -> str:
    health = view["health"]
    tick = health["last_tick"]
    lines = [f"Run {view['run_id']} | {view['as_of']} | {'finished' if view['finished'] else 'running'}",
             f"Backlog: {health['chunk_backlog_at_last_observation']} chunks / {health['event_backlog_at_last_observation']} event IDs (last observed)",
             f"Last tick: {tick['metrics'].get('loop_seconds','?') if tick else '?'}s | new proposals/hour: {health['new_proposals_last_sim_hour']} | credits left: {view['credits']['remaining_at_last_observation']}",
             "WORKFLOW           EXPERIMENT       PENDING (age h)       INCIDENT          CREDITS spent/uncertain"]
    names = {row["workflow_id"] for key in ("cohorts", "experiments", "pending_proposals", "open_incidents") for row in view[key]}
    for name in sorted(names):
        trials = [r for r in view["experiments"] if r["workflow_id"]==name]
        pending = [f"{r['status']}({r['age_sim_hours']:.1f})" for r in view["pending_proposals"] if r["workflow_id"]==name]
        incidents = [r["status"] for r in view["open_incidents"] if r["workflow_id"]==name]
        spent = sum(r["credits"] for r in view["credits"]["by_workflow"] if r["workflow_id"]==name and r["status"]=="succeeded")
        uncertain = sum(r["credits"] for r in view["credits"]["by_workflow"] if r["workflow_id"]==name and r["status"]=="uncertain")
        lines.append(f"{name:<18} {(trials[-1]['status'] if trials else '-'):<16} {','.join(pending) or '-':<21} {','.join(incidents) or '-':<17} {spent}/{uncertain}")
    lines.append(f"Recent changes: {len(view['recent_changes'])} shown by --json; experiments: {len(view['experiments'])}")
    lines.extend(f"{alert['severity'].upper()}: {alert.get('reason',alert.get('message'))}; {alert['action']}" for alert in view["alerts"])
    return "\n".join(lines)


def audit(db, run_id: str, workflow_id: str, at: str) -> dict:
    instant = datetime.fromisoformat(at)
    if instant.tzinfo is None:
        raise ValueError("--at must include a timezone")
    changes = rows(db, "SELECT ts,actor,evidence FROM audit_log WHERE run_id=%s AND workflow_id=%s "
                       "AND kind='config_changed' AND ts<=%s ORDER BY ts DESC,event_id DESC LIMIT 1",
                   (run_id, workflow_id, instant))
    if not changes:
        raise ValueError("No recorded config change at or before this timestamp")
    change = changes[0]
    pid = change["evidence"].get("proposal_id")
    proposal = rows(db, "SELECT proposal_id,decision_id,body,route,status,approval_id FROM proposals "
                        "WHERE run_id=%s AND proposal_id=%s", (run_id, pid))
    approval_id = proposal[0]["approval_id"] if proposal else change["evidence"].get("approval_id")
    changed_at = change["ts"].astimezone(ZoneInfo("Asia/Kolkata"))
    start = changed_at.replace(minute=0, second=0, microsecond=0)
    if start < changed_at:
        start += timedelta(hours=1)
    end = changed_at + timedelta(hours=24)
    counts = rows(db, "SELECT min(hour) AS first_hour,max(hour) AS last_hour, "
                     "COALESCE(sum(dials),0)::bigint AS dials,COALESCE(sum(connected),0)::bigint AS connected, "
                     "COALESCE(sum(engaged),0)::bigint AS engaged,COALESCE(sum(hallucinations),0)::bigint AS hallucinations "
                     "FROM hourly_metrics WHERE run_id=%s AND workflow_id=%s AND NOT history "
                     "AND dimension='all' AND config_version=%s AND hour>=%s AND hour<%s "
                     "AND hour+interval '1 hour' <= (SELECT last_ts FROM controller_runs WHERE run_id=%s)",
                  (run_id, workflow_id, change["evidence"]["version"], start, end.replace(minute=0, second=0, microsecond=0), run_id))[0]
    return {
        "run_id": run_id, "workflow_id": workflow_id, "change": change,
        "proposal": proposal[0] if proposal else None,
        "approval_events": rows(db, "SELECT ts,evidence FROM audit_log WHERE run_id=%s "
                                    "AND kind='approval_decided' AND evidence->>'approval_id'=%s ORDER BY ts,event_id", (run_id, approval_id)),
        "proposal_history": rows(db, "SELECT ts,status,evidence FROM proposal_audit WHERE run_id=%s "
                                     "AND proposal_id=%s ORDER BY id", (run_id, pid)),
        "incidents": rows(db, "SELECT incident_id,status,data FROM incidents WHERE run_id=%s AND proposal_id=%s", (run_id, pid)),
        "after": {"method": "Observed new-version exposure in complete hours within the next 24h; observational, not causal", **counts,
                  "pickup_rate": float(counts["connected"]/counts["dials"]) if counts["dials"] else None,
                  "engagement_rate": float(counts["engaged"]/counts["connected"]) if counts["connected"] else None},
        "identity_limit": "Approval IDs/status are recorded; the simulator does not expose a named human approver",
    }
