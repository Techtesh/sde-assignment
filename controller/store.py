"""PostgreSQL evidence and atomic chunk ingestion; no simulator internals."""

from collections.abc import Iterable
from datetime import datetime
import hashlib
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .faults import crash_at


def event_row(run_id: str, chunk: int, history: bool, event: dict) -> tuple:
    if type(event.get("event_id")) is not int or event["event_id"] < 1:
        raise ValueError("Event requires a positive integer event_id") # create an explicit error
    for field in ("ts", "workflow_id", "type"):
        if not isinstance(event.get(field), str) or not event[field]:
            raise ValueError(f"Event requires {field}")
    timestamp = datetime.fromisoformat(event["ts"])
    if timestamp.tzinfo is None:
        raise ValueError("Event timestamp must include a timezone")
    if event["type"] not in {"lead", "call", "campaign_created", "config_changed", "approval_decided"}:
        raise ValueError(f"Unsupported event type: {event['type']}")
    if event["type"] == "lead":
        for field in ("lead_id", "person_id", "campaign_id"):
            if not isinstance(event.get(field), str) or not event[field]:
                raise ValueError(f"Lead requires {field}")
        if not isinstance(event.get("features"), dict):
            raise ValueError("Lead requires features")
    if event["type"] == "campaign_created" and (not isinstance(event.get("campaign_id"), str) or not event["campaign_id"]):
        raise ValueError("Campaign requires campaign_id")
    if event["type"] == "call":
        if type(event.get("connected")) is not bool or type(event.get("engaged")) is not bool:
            raise ValueError("Call outcomes must be booleans")
        if event["engaged"] and not event["connected"]:
            raise ValueError("An engaged call must be connected")
        if type(event.get("config_version")) is not int or event["config_version"] < 1:
            raise ValueError("Call requires config_version")
        for field in ("lead_id", "person_id", "cohort_id"):
            if not isinstance(event.get(field), str) or not event[field]:
                raise ValueError(f"Call requires {field}")
        variant = event.get("variant")
        if not isinstance(variant, dict) or any(
            not isinstance(variant.get(dim), str) or not variant[dim]
            for dim in ("voice", "welcome_message", "caller_id", "prompt_version")
        ):
            raise ValueError("Call requires all variant dimensions")
        if event["connected"]:
            qa = event.get("qa")
            if not isinstance(qa, dict) or type(qa.get("hallucination_flag")) is not bool:
                raise ValueError("Connected call requires hallucination QA")
    return (
        run_id, event["event_id"], chunk, history, timestamp,
        event["workflow_id"], event["type"], Jsonb(event),
    )


class Store:
    def __init__(self, connection: psycopg.Connection, run_id: str | None, simulator_url: str,
                 *, state: dict | None = None):
        self.db = connection
        # Repeated loop queries should not pay LLVM compilation costs as evidence grows.
        self.db.execute("SET jit=off")
        self.db.execute(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
        if run_id is None:
            if state is None:
                raise ValueError("Automatic run identity requires simulator state")
            run_id = self._automatic_run(simulator_url, state)
        self.run_id = run_id
        locked = self.db.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (run_id,)
        ).fetchone()[0]
        if not locked:
            raise RuntimeError("Another controller is already processing this run_id")
        self.db.execute(
            "INSERT INTO controller_runs (run_id, simulator_url) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING", (run_id, simulator_url),
        )
        existing = self.db.execute(
            "SELECT simulator_url FROM controller_runs WHERE run_id = %s", (run_id,)
        ).fetchone()[0]
        if existing != simulator_url:
            raise ValueError("run_id belongs to another simulator URL; use a fresh run_id")
        self.evidence_sql = sql.SQL(Path(__file__).with_name("evidence.sql").read_text(encoding="utf-8"))
        self.qa_sql = sql.SQL("""
            INSERT INTO qa_metrics
            SELECT run_id,workflow_id,history,(payload->>'config_version')::integer,
                   payload->>'cohort_id',payload->'variant'->>'prompt_version',ts,count(*),
                   count(*) FILTER (WHERE (payload->>'connected')::boolean),
                   count(*) FILTER (WHERE (payload->>'engaged')::boolean),
                   count(*) FILTER (WHERE (payload->>'connected')::boolean
                                     AND (payload->'qa'->>'hallucination_flag')::boolean)
            FROM {source} WHERE kind='call' GROUP BY 1,2,3,4,5,6,7
            ON CONFLICT (run_id,workflow_id,history,config_version,cohort_id,prompt_version,ts)
            DO UPDATE SET dials=qa_metrics.dials+EXCLUDED.dials,
                          connected=qa_metrics.connected+EXCLUDED.connected,
                          engaged=qa_metrics.engaged+EXCLUDED.engaged,
                          hallucinations=qa_metrics.hallucinations+EXCLUDED.hallucinations
        """)
        # Upgrade old runs atomically once; normal decisions never rescan raw JSON events.
        if not self.db.execute("SELECT 1 FROM evidence_ready WHERE run_id=%s", (run_id,)).fetchone():
            with self.db.transaction():
                source = sql.SQL("(SELECT * FROM events WHERE run_id={}) AS source").format(sql.Literal(run_id))
                self.db.execute(self.evidence_sql.format(source=source))
                self.db.execute("INSERT INTO evidence_ready VALUES (%s)", (run_id,))
        if not self.db.execute("SELECT 1 FROM qa_evidence_ready WHERE run_id=%s", (run_id,)).fetchone():
            with self.db.transaction():
                source = sql.SQL("(SELECT * FROM events WHERE run_id={}) AS source").format(sql.Literal(run_id))
                self.db.execute(self.qa_sql.format(source=source))
                self.db.execute("INSERT INTO qa_evidence_ready VALUES (%s)", (run_id,))
        if state is not None:
            self.observe_state(state)

    def _automatic_run(self, simulator_url: str, state: dict) -> str:
        locked = self.db.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                                 ("endpoint:" + simulator_url,)).fetchone()[0]
        if not locked:
            raise RuntimeError("Another controller is already processing this simulator URL")
        previous = self.db.execute(
            "SELECT e.run_id,e.generation,r.state FROM controller_endpoints e "
            "JOIN controller_runs r USING(run_id) WHERE e.simulator_url=%s", (simulator_url,),
        ).fetchone()
        if previous is None:
            # Preserve recovery for installations that previously used the implicit default.
            previous = self.db.execute("SELECT run_id,0,state FROM controller_runs "
                                       "WHERE run_id='default' AND simulator_url=%s", (simulator_url,)).fetchone()
        generation = previous[1] if previous else 0
        old = previous[2] if previous else {}
        compatible = not old or (
            old.get("scenario") == state.get("scenario")
            and datetime.fromisoformat(old["ts"]) <= datetime.fromisoformat(state["ts"])
            and old["last_event_id"] <= state["last_event_id"]
            and not (old.get("finished") and not state.get("finished"))
        )
        if previous and compatible:
            run_id = previous[0]
        else:
            generation += 1
            run_id = f"auto-{hashlib.sha256(simulator_url.encode()).hexdigest()[:24]}-{generation}"
        with self.db.transaction():
            self.db.execute("INSERT INTO controller_runs(run_id,simulator_url) VALUES (%s,%s) "
                            "ON CONFLICT DO NOTHING", (run_id, simulator_url))
            self.db.execute("INSERT INTO controller_endpoints VALUES (%s,%s,%s) "
                            "ON CONFLICT (simulator_url) DO UPDATE SET run_id=EXCLUDED.run_id,generation=EXCLUDED.generation",
                            (simulator_url, run_id, generation))
        return run_id

    def last_chunk(self, kind: str) -> int:
        return self.db.execute(
            "SELECT COALESCE(max(chunk), -1) FROM ingested_chunks WHERE run_id = %s AND kind = %s",
            (self.run_id, kind),
        ).fetchone()[0]

    def observe_state(self, state: dict) -> None:
        timestamp = datetime.fromisoformat(state["ts"])
        previous = self.db.execute(
            "SELECT last_ts, state FROM controller_runs WHERE run_id = %s", (self.run_id,)
        ).fetchone()
        if previous[0] is not None and timestamp < previous[0]:
            raise ValueError("Simulator time moved backward; use a fresh run_id for a new world")
        if previous[1] and (
            previous[1].get("scenario") != state.get("scenario")
            or previous[1]["last_event_id"] > state["last_event_id"]
        ):
            raise ValueError("Simulator world changed; use a fresh run_id")
        self.db.execute(
            "UPDATE controller_runs SET last_ts = %s, state = %s WHERE run_id = %s",
            (timestamp, Jsonb(state), self.run_id),
        )

    def save_workflow(self, workflow: dict, config: dict, history: list[dict]) -> None:
        wid = workflow["workflow_id"]
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO workflow_snapshots VALUES (%s, %s, %s) "
                "ON CONFLICT (run_id, workflow_id) DO UPDATE SET definition = EXCLUDED.definition",
                (self.run_id, wid, Jsonb(workflow)),
            )
            for snapshot in [*history, config]:
                self.db.execute(
                    "INSERT INTO config_history VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (run_id, workflow_id, version) DO UPDATE "
                    "SET snapshot = config_history.snapshot || EXCLUDED.snapshot",
                    (self.run_id, wid, snapshot["version"], Jsonb(snapshot)),
                )

    def ingest(self, chunk: dict, events: Iterable[dict]) -> int:
        number, kind = chunk["chunk"], chunk["kind"]
        if kind not in ("events", "history"):
            raise ValueError(f"Unknown chunk kind: {kind}")
        with self.db.transaction():
            existing = self.db.execute(
                "SELECT 1 FROM ingested_chunks WHERE run_id = %s AND chunk = %s",
                (self.run_id, number),
            ).fetchone()
            if existing:
                return 0
            prior_max = self.db.execute(
                "SELECT COALESCE(max(event_id),0) FROM events WHERE run_id=%s", (self.run_id,),
            ).fetchone()[0]
            self.db.execute("CREATE TEMP TABLE incoming (LIKE events) ON COMMIT DROP")
            count = 0
            minimum_id = None
            with self.db.cursor().copy("COPY incoming FROM STDIN") as copy:
                for event in events:
                    copy.write_row(event_row(self.run_id, number, kind == "history", event))
                    count += 1
                    minimum_id = event["event_id"] if minimum_id is None else min(minimum_id, event["event_id"])
                    if count == 1:
                        crash_at("mid_ingest")
            if count != chunk["events"]:
                raise ValueError(f"Chunk {number}: expected {chunk['events']} events, got {count}")
            # Sort narrow IDs first; ordinary chunks need neither JSON sorting nor a scan of prior evidence.
            duplicates = self.db.execute(
                "SELECT 1 FROM incoming GROUP BY event_id HAVING count(*)>1 LIMIT 1"
            ).fetchone()
            conflict = None
            if duplicates:
                conflict = self.db.execute(
                    "SELECT 1 FROM incoming GROUP BY event_id HAVING count(DISTINCT payload)>1 LIMIT 1"
                ).fetchone()
            if not conflict and minimum_id is not None and minimum_id <= prior_max:
                conflict = self.db.execute(
                    "SELECT 1 FROM incoming i JOIN events e USING (run_id,event_id) "
                    "WHERE i.payload<>e.payload OR i.history<>e.history LIMIT 1"
                ).fetchone()
            if conflict:
                raise ValueError("Conflicting event_id; use a fresh run_id for a new world")
            self.db.execute("CREATE TEMP TABLE fresh_events (LIKE events) ON COMMIT DROP")
            source = ("SELECT DISTINCT ON (event_id) * FROM incoming ORDER BY event_id"
                      if duplicates else "SELECT * FROM incoming")
            self.db.execute(
                "WITH added AS (INSERT INTO events " + source + " ON CONFLICT DO NOTHING RETURNING *) "
                "INSERT INTO fresh_events SELECT * FROM added"
            )
            self.db.execute(
                "INSERT INTO leads SELECT DISTINCT ON (workflow_id, payload->>'lead_id') "
                "run_id, workflow_id, payload->>'lead_id', payload->>'person_id', "
                "payload->>'campaign_id', payload->'features' FROM fresh_events WHERE kind = 'lead' "
                "ORDER BY workflow_id, payload->>'lead_id', event_id DESC "
                "ON CONFLICT (run_id, workflow_id, lead_id) DO UPDATE SET "
                "person_id = EXCLUDED.person_id, campaign_id = EXCLUDED.campaign_id, features = EXCLUDED.features"
            )
            missing = self.db.execute(
                "SELECT f.event_id FROM fresh_events f LEFT JOIN leads l ON "
                "l.run_id = f.run_id AND l.workflow_id = f.workflow_id "
                "AND l.lead_id = f.payload->>'lead_id' WHERE f.kind = 'call' "
                "AND (l.lead_id IS NULL OR l.person_id <> f.payload->>'person_id') LIMIT 1"
            ).fetchone()
            if missing:
                raise ValueError(f"Call {missing[0]} has no matching lead/person")
            self.db.execute(self.evidence_sql.format(source=sql.Identifier("fresh_events")))
            self.db.execute(self.qa_sql.format(source=sql.Identifier("fresh_events")))
            self.db.execute(
                "INSERT INTO hourly_metrics SELECT run_id, workflow_id, history, "
                "date_trunc('hour', ts, 'Asia/Kolkata'), (payload->>'config_version')::integer, "
                "payload->>'cohort_id', dim, CASE WHEN dim = 'all' THEN '*' "
                "ELSE payload->'variant'->>dim END, count(*), "
                "count(*) FILTER (WHERE (payload->>'connected')::boolean), "
                "count(*) FILTER (WHERE (payload->>'engaged')::boolean), "
                "count(*) FILTER (WHERE (payload->'qa'->>'hallucination_flag')::boolean) "
                "FROM fresh_events CROSS JOIN "
                "(VALUES ('all'), ('voice'), ('caller_id'), ('prompt_version')) dimensions(dim) "
                "WHERE kind = 'call' GROUP BY 1,2,3,4,5,6,7,8 "
                "ON CONFLICT (run_id,workflow_id,history,hour,config_version,cohort_id,dimension,variant) "
                "DO UPDATE SET dials = hourly_metrics.dials + EXCLUDED.dials, "
                "connected = hourly_metrics.connected + EXCLUDED.connected, "
                "engaged = hourly_metrics.engaged + EXCLUDED.engaged, "
                "hallucinations = hourly_metrics.hallucinations + EXCLUDED.hallucinations"
            )
            self.db.execute(
                "INSERT INTO audit_log SELECT run_id, event_id, ts, workflow_id, kind, "
                "payload->>'actor', payload FROM fresh_events "
                "WHERE kind NOT IN ('lead', 'call') ON CONFLICT DO NOTHING"
            )
            inserted = self.db.execute("SELECT count(*) FROM fresh_events").fetchone()[0]
            self.db.execute(
                "INSERT INTO ingested_chunks VALUES (%s, %s, %s, %s)",
                (self.run_id, number, kind, count),
            )
        return inserted

    def summary(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT workflow_id, history, sum(dials), sum(connected), sum(engaged) "
            "FROM hourly_metrics WHERE run_id = %s AND dimension = 'all' "
            "GROUP BY workflow_id, history ORDER BY workflow_id, history", (self.run_id,),
        ).fetchall()
        return [
            {"workflow_id": wid, "history": history, "dials": int(dials),
             "connected": int(connected), "engaged": int(engaged),
             "pickup_rate": float(connected / dials) if dials else None,
             "engagement_rate": float(engaged / connected) if connected else None}
            for wid, history, dials, connected, engaged in rows
        ]

    def record_tick(self, metrics: dict) -> None:
        self.db.execute(
            "INSERT INTO loop_ticks (run_id,ts,metrics) VALUES (%s,%s,%s) "
            "ON CONFLICT (run_id,ts) DO UPDATE SET metrics=EXCLUDED.metrics,recorded_at=clock_timestamp()",
            (self.run_id, metrics["ts"], Jsonb(metrics)),
        )

    def proposal(self, proposal_id: str) -> dict | None:
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT * FROM proposals WHERE run_id=%s AND proposal_id=%s",
                (self.run_id, proposal_id),
            ).fetchone()

    def decision_proposal(self, decision_id: str) -> dict | None:
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT * FROM proposals WHERE run_id=%s AND decision_id=%s",
                (self.run_id, decision_id),
            ).fetchone()

    def active_proposals(self) -> list[dict]:
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT * FROM proposals WHERE run_id=%s AND status IN "
                "('planned','submitted','pending','approved','applying') "
                "ORDER BY urgent DESC, created_at, workflow_id, proposal_id", (self.run_id,),
            ).fetchall()

    def save_proposal(self, body: dict, decision_id: str, base: dict, route: str,
                      now: str, urgent: bool, parent_id: str | None, policy: dict) -> None:
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO proposals (run_id,proposal_id,decision_id,workflow_id,base_config,"
                "body,route,status,urgent,created_at,parent_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'planned',%s,%s,%s)",
                (self.run_id, body["proposal_id"], decision_id, body["workflow_id"],
                 Jsonb(base), Jsonb(body), route, urgent, now, parent_id),
            )
            self.db.execute(
                "INSERT INTO proposal_audit (run_id,proposal_id,ts,status,evidence) "
                "VALUES (%s,%s,%s,'planned',%s)",
                (self.run_id, body["proposal_id"], now, Jsonb({"route": route, "body": body, "policy": policy})),
            )

    def transition(self, proposal_id: str, status: str, now: str, response: dict,
                   approval_id: str | None = None) -> None:
        with self.db.transaction():
            previous = self.proposal(proposal_id)
            if previous["status"] == status and previous["response"] == response:
                return
            self.db.execute(
                "UPDATE proposals SET status=%s,response=%s,approval_id=COALESCE(%s,approval_id),"
                "submitted_at=CASE WHEN %s='submitted' THEN COALESCE(submitted_at,%s::timestamptz) "
                "ELSE submitted_at END WHERE run_id=%s AND proposal_id=%s",
                (status, Jsonb(response), approval_id, status, now, self.run_id, proposal_id),
            )
            self.db.execute(
                "INSERT INTO proposal_audit (run_id,proposal_id,ts,status,evidence) VALUES (%s,%s,%s,%s,%s)",
                (self.run_id, proposal_id, now, status, Jsonb(response)),
            )

    def recent_approval_ids(self, workflow_id: str, now: str) -> set[str]:
        rows = self.db.execute(
            "SELECT proposal_id FROM proposals WHERE run_id=%s AND workflow_id=%s AND route='approval' "
            "AND submitted_at > %s::timestamptz - interval '24 hours'",
            (self.run_id, workflow_id, now),
        ).fetchall()
        return {row[0] for row in rows}

    def active_lead_groups(self, workflow: dict, now: str) -> list[tuple]:
        return self.db.execute(
            "SELECT l.features,count(*) FROM leads l JOIN campaigns a USING(run_id,workflow_id,campaign_id) "
            "LEFT JOIN concluded_leads c USING(run_id,workflow_id,lead_id) "
            "WHERE l.run_id=%s AND l.workflow_id=%s AND a.created_at<=%s "
            "AND ((%s::timestamptz AT TIME ZONE 'Asia/Kolkata')::date - "
            "(a.created_at AT TIME ZONE 'Asia/Kolkata')::date) BETWEEN 0 AND %s "
            "AND c.lead_id IS NULL GROUP BY l.features",
            (self.run_id, workflow["workflow_id"], now, now, len(workflow["cadence"]) - 1),
        ).fetchall()

    def historical_rates(self, workflow_id: str) -> list[dict]:
        with self.db.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                "SELECT cohort_id,dimension,variant,sum(dials)::bigint AS dials,"
                "sum(connected)::bigint AS connected,sum(engaged)::bigint AS engaged,"
                "sum(hallucinations)::bigint AS hallucinations "
                "FROM hourly_metrics WHERE run_id=%s AND workflow_id=%s AND history AND dimension<>'all' "
                "GROUP BY cohort_id,dimension,variant ORDER BY cohort_id,dimension,variant",
                (self.run_id, workflow_id),
            ).fetchall()
        return rows

    def prompt_context(self, workflow_id: str) -> dict:
        with self.db.cursor(row_factory=dict_row) as cursor:
            change = cursor.execute(
                "SELECT event_id,ts,actor,evidence FROM audit_log WHERE run_id=%s AND workflow_id=%s "
                "AND kind='config_changed' AND evidence->'changed_dims' ? 'prompt_version' ORDER BY event_id DESC LIMIT 1",
                (self.run_id, workflow_id),
            ).fetchone()
            previous = None
            if change:
                previous = cursor.execute(
                    "SELECT version,snapshot->'config'->>'prompt_version' AS prompt FROM config_history "
                    "WHERE run_id=%s AND workflow_id=%s AND version<%s AND snapshot->'config' ? 'prompt_version' "
                    "ORDER BY version DESC LIMIT 1", (self.run_id, workflow_id, change["evidence"]["version"]),
                ).fetchone()
        return {"change": {**change, "ts": change["ts"].isoformat()} if change else None,
                "previous": previous, "interpretation": "latest observed prompt edit; temporal attribution, not proof of causation"}

    def prompt_alarm_epoch(self, workflow_id: str) -> int:
        return self.db.execute(
            "SELECT COALESCE(max((evidence->>'version')::integer),1) FROM audit_log "
            "WHERE run_id=%s AND workflow_id=%s AND kind='config_changed' "
            "AND (evidence->'changed_dims' ? 'prompt_version' OR evidence->'changed_dims' ? 'cohorts')",
            (self.run_id, workflow_id),
        ).fetchone()[0]

    def prompt_alarm_change(self, workflow_id: str) -> dict | None:
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT ts,(evidence->>'version')::integer AS version,observed_version FROM ("
                "SELECT ts,evidence,event_id,max((evidence->>'version')::integer) OVER () AS observed_version "
                "FROM audit_log WHERE run_id=%s AND workflow_id=%s AND kind='config_changed') changes "
                "WHERE (evidence->'changed_dims' ? 'prompt_version' OR evidence->'changed_dims' ? 'cohorts') "
                "ORDER BY (evidence->>'version')::integer DESC,event_id DESC LIMIT 1",
                (self.run_id, workflow_id),
            ).fetchone()

    def prompt_detections(self, workflow_id: str, version: int) -> list[dict]:
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT hour,evidence FROM detection_windows WHERE run_id=%s AND workflow_id=%s "
                "AND config_version=%s AND kind='prompt-cumulative-v1' ORDER BY hour,subject",
                (self.run_id, workflow_id, version),
            ).fetchall()

    def qa_window_metrics(self, workflow_id: str, version: int, prompt: str, start: str, end: str,
                          *, history: bool = False) -> list[dict]:
        seconds = min(86400, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT cohort_id,'prompt_version' AS dimension,prompt_version AS variant,"
                "sum(dials)::bigint AS dials,sum(connected)::bigint AS connected,"
                "sum(engaged)::bigint AS engaged,sum(hallucinations)::bigint AS hallucinations "
                "FROM qa_metrics WHERE run_id=%s AND workflow_id=%s AND history=%s AND "
                "((%s AND MOD(EXTRACT(epoch FROM (ts AT TIME ZONE 'Asia/Kolkata')::time) - "
                "EXTRACT(epoch FROM (%s::timestamptz AT TIME ZONE 'Asia/Kolkata')::time)+86400,86400)<%s) "
                "OR (NOT %s AND ts>=%s AND ts<%s AND config_version>=%s AND prompt_version=%s)) "
                "GROUP BY cohort_id,prompt_version ORDER BY cohort_id,prompt_version",
                (self.run_id, workflow_id, history, history, start, seconds, history, start, end, version, prompt),
            ).fetchall()

    def uncertain_paid_action(self, incident_id: str) -> bool:
        return bool(self.db.execute("SELECT 1 FROM external_actions WHERE run_id=%s AND incident_id=%s "
                                    "AND status='uncertain' LIMIT 1", (self.run_id, incident_id)).fetchone())

    def window_metrics(self, workflow_id: str, start: str, end: str, *, history: bool = False) -> list[dict]:
        hours = min(24, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 3600)
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT cohort_id,dimension,variant,sum(dials)::bigint AS dials,"
                "sum(connected)::bigint AS connected,sum(engaged)::bigint AS engaged,"
                "sum(hallucinations)::bigint AS hallucinations FROM hourly_metrics "
                "WHERE run_id=%s AND workflow_id=%s AND history=%s AND "
                "((%s AND MOD((EXTRACT(hour FROM hour AT TIME ZONE 'Asia/Kolkata') - "
                "EXTRACT(hour FROM %s::timestamptz AT TIME ZONE 'Asia/Kolkata') + 24)::integer,24)<%s) "
                "OR (NOT %s AND hour >= %s AND hour < %s)) "
                "GROUP BY cohort_id,dimension,variant ORDER BY cohort_id,dimension,variant",
                (self.run_id, workflow_id, history, history, start, hours, history, start, end),
            ).fetchall()

    def detection_window(self, workflow_id: str, version: int, hour: str, alarm: dict) -> dict:
        params = (self.run_id, workflow_id, version, alarm["kind"], alarm["subject"], hour)
        with self.db.cursor(row_factory=dict_row) as cursor:
            existing = cursor.execute(
                "SELECT * FROM detection_windows WHERE run_id=%s AND workflow_id=%s "
                "AND config_version=%s AND kind=%s AND subject=%s AND hour=%s", params,
            ).fetchone()
            if existing:
                return existing
            previous = cursor.execute(
                "SELECT streak,episode_start FROM detection_windows WHERE run_id=%s AND workflow_id=%s "
                "AND config_version=%s AND kind=%s AND subject=%s AND hour=%s::timestamptz - interval '1 hour'", params,
            ).fetchone()
            streak = (previous["streak"] + 1 if previous else 1) if alarm["signal"] else 0
            episode = previous["episode_start"] if previous and previous["streak"] and streak else hour
            return cursor.execute(
                "INSERT INTO detection_windows VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (*params, streak, episode, Jsonb(alarm)),
            ).fetchone()

    def incident(self, incident_id: str) -> dict | None:
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute("SELECT * FROM incidents WHERE run_id=%s AND incident_id=%s",
                                  (self.run_id, incident_id)).fetchone()

    def open_incidents(self) -> list[dict]:
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT i.* FROM incidents i LEFT JOIN (SELECT tenant_id,max(id) AS served "
                "FROM external_actions WHERE run_id=%s GROUP BY tenant_id) a USING (tenant_id) "
                "WHERE i.run_id=%s AND i.status NOT IN ('resolved','needs_review','superseded') "
                "ORDER BY COALESCE(a.served,0),i.tenant_id,i.created_at,i.workflow_id,i.incident_id",
                (self.run_id, self.run_id),
            ).fetchall()

    def incident_held_for_review(self, workflow_id: str, kind: str, subject: str) -> bool:
        return self.db.execute(
            "SELECT 1 FROM incidents WHERE run_id=%s AND workflow_id=%s AND kind=%s "
                "AND status='needs_review' AND (data->'alarm'->>'subject'=%s OR data->'review_subjects' ? %s) LIMIT 1",
                (self.run_id, workflow_id, kind, subject, subject),
        ).fetchone() is not None

    def save_incident(self, incident_id: str, workflow: dict, kind: str, now: str, data: dict) -> None:
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO incidents VALUES (%s,%s,%s,%s,%s,'detected',%s,NULL,%s) ON CONFLICT DO NOTHING",
                (self.run_id, incident_id, workflow["workflow_id"], workflow["tenant_id"], kind, now, Jsonb(data)),
            )
            self.update_incident(incident_id, "detected", now, data)

    def update_incident(self, incident_id: str, status: str, now: str, data: dict,
                        proposal_id: str | None = None) -> None:
        with self.db.transaction():
            previous = self.incident(incident_id)
            if previous["status"] == status and previous["data"] == data and not proposal_id:
                # Initial detection still needs its audit row.
                if self.db.execute("SELECT 1 FROM incident_audit WHERE run_id=%s AND incident_id=%s LIMIT 1",
                                   (self.run_id, incident_id)).fetchone():
                    return
            self.db.execute(
                "UPDATE incidents SET status=%s,data=%s,proposal_id=COALESCE(%s,proposal_id) "
                "WHERE run_id=%s AND incident_id=%s",
                (status, Jsonb(data), proposal_id, self.run_id, incident_id),
            )
            self.db.execute("INSERT INTO incident_audit (run_id,incident_id,ts,status,evidence) VALUES (%s,%s,%s,%s,%s)",
                            (self.run_id, incident_id, now, status, Jsonb(data)))

    def action(self, action_id: str) -> dict | None:
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute("SELECT * FROM external_actions WHERE run_id=%s AND action_id=%s",
                                  (self.run_id, action_id)).fetchone()

    def reserve_action(self, action_id: str, incident: dict, kind: str, cost: int,
                       now: str, request: dict) -> None:
        self.db.execute(
            "INSERT INTO external_actions (run_id,action_id,incident_id,tenant_id,kind,cost,created_at,status,request) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'uncertain',%s)",
            (self.run_id, action_id, incident["incident_id"], incident["tenant_id"], kind, cost, now, Jsonb(request)),
        )

    def finish_action(self, action_id: str, status: str, response: dict) -> None:
        self.db.execute("UPDATE external_actions SET status=%s,response=%s WHERE run_id=%s AND action_id=%s",
                        (status, Jsonb(response), self.run_id, action_id))

    def credit_usage(self, initial: float) -> dict:
        self.db.execute("INSERT INTO credit_budgets VALUES (%s,%s) ON CONFLICT DO NOTHING", (self.run_id, initial))
        budget = self.db.execute("SELECT initial_credits FROM credit_budgets WHERE run_id=%s", (self.run_id,)).fetchone()[0]
        with self.db.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                "SELECT tenant_id,incident_id,sum(cost)::integer AS cost FROM external_actions "
                "WHERE run_id=%s AND status IN ('uncertain','succeeded') GROUP BY tenant_id,incident_id",
                (self.run_id,),
            ).fetchall()
        return {"initial": budget, "spending": rows}

    def experiments(self, workflow_id: str | None = None, *, active: bool = False) -> list[dict]:
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT * FROM experiments WHERE run_id=%s AND (%s::text IS NULL OR workflow_id=%s) "
                "AND (NOT %s OR status IN ('planned','running','promoting','monitoring','restoring')) "
                "ORDER BY created_at,experiment_id", (self.run_id, workflow_id, workflow_id, active),
            ).fetchall()

    def save_experiment(self, experiment_id: str, workflow_id: str, now: str, data: dict) -> None:
        with self.db.transaction():
            self.db.execute("INSERT INTO experiments VALUES (%s,%s,%s,'planned',%s,NULL,%s)",
                            (self.run_id, experiment_id, workflow_id, now, Jsonb(data)))
            self.db.execute(
                "INSERT INTO experiment_audit (run_id,experiment_id,ts,status,evidence) VALUES (%s,%s,%s,'planned',%s)",
                (self.run_id, experiment_id, now, Jsonb(data)),
            )

    def update_experiment(self, experiment_id: str, status: str, now: str, data: dict,
                          proposal_id: str | None = None) -> None:
        with self.db.transaction():
            self.db.execute(
                "UPDATE experiments SET status=%s,data=%s,proposal_id=COALESCE(%s,proposal_id) "
                "WHERE run_id=%s AND experiment_id=%s",
                (status, Jsonb(data), proposal_id, self.run_id, experiment_id),
            )
            self.db.execute(
                "INSERT INTO experiment_audit (run_id,experiment_id,ts,status,evidence) VALUES (%s,%s,%s,%s,%s)",
                (self.run_id, experiment_id, now, status, Jsonb(data)),
            )

    def experiment_blocked_by_incident(self, workflow_id: str) -> bool:
        return self.db.execute(
            "SELECT 1 FROM incidents WHERE run_id=%s AND workflow_id=%s "
            "AND status NOT IN ('resolved','superseded') LIMIT 1", (self.run_id, workflow_id),
        ).fetchone() is not None

    def first_exposure(self, experiment: dict, version: int, after: str) -> str | None:
        data = experiment["data"]
        row = self.db.execute(
            "SELECT min(ts) FROM person_metrics WHERE run_id=%s AND workflow_id=%s "
            "AND ts >= %s AND config_version=%s AND cohort_id=%s AND voice=ANY(%s)",
            (self.run_id, experiment["workflow_id"], after, version, data["cohort"],
             [data["plan"]["control"], data["plan"]["challenger"]]),
        ).fetchone()[0]
        return row.isoformat() if row else None

    def collect_exposure(self, experiment: dict, phase: str, version: int, start: str, end: str,
                         *, exposure: str = "all") -> list[dict]:
        """Add only newly closed time ranges; counters and their cursor commit together."""
        eid = experiment["experiment_id"]
        data = experiment["data"]
        if exposure not in {"all", "first", "repeat"}:
            raise ValueError("Exposure must be all, first, or repeat")
        if exposure != "all":
            phase += ":" + exposure
        with self.db.transaction():
            previous = self.db.execute(
                "SELECT max(end_at) FROM experiment_windows WHERE run_id=%s AND experiment_id=%s AND phase=%s",
                (self.run_id, eid, phase),
            ).fetchone()[0]
            begin = previous if previous else datetime.fromisoformat(start)
            if begin > datetime.fromisoformat(end):
                raise ValueError("Cannot evaluate before the already collected horizon")
            if begin < datetime.fromisoformat(end):
                params = [self.run_id, experiment["workflow_id"], version, data["cohort"], begin, end,
                          [data["plan"]["control"], data["plan"]["challenger"]]]
                source = ("SELECT * FROM person_metrics WHERE run_id=%s AND workflow_id=%s AND config_version=%s "
                          "AND cohort_id=%s AND ts>=%s AND ts<%s AND voice=ANY(%s)")
                measures = "dials,connected,engaged"
                if exposure != "all":
                    source = ("SELECT * FROM (SELECT *,row_number() OVER (PARTITION BY person_id,voice "
                              "ORDER BY ts,first_event_id) AS position FROM person_metrics "
                              "WHERE run_id=%s AND workflow_id=%s AND config_version=ANY(%s) "
                              "AND cohort_id=%s AND ts>=%s AND ts<%s AND voice=ANY(%s)) ranked "
                              "WHERE config_version=%s AND ts>=%s")
                    versions = sorted({version, data.get("trial_version", version)})
                    params = [self.run_id, experiment["workflow_id"], versions, data["cohort"],
                              data["started_at"], end, params[-1], version, begin]
                    first = ("CASE WHEN position=1 THEN 1 ELSE 0 END",
                             "CASE WHEN position=1 THEN first_connected ELSE 0 END",
                             "CASE WHEN position=1 THEN first_engaged ELSE 0 END")
                    columns = ("dials", "connected", "engaged")
                    values = first if exposure == "first" else [f"{column}-({value})" for column, value in zip(columns, first)]
                    measures = ",".join(f"{value} AS {column}" for column, value in zip(columns, values))
                self.db.execute(
                    "WITH selected AS (" + source + "), measured AS (SELECT run_id,person_id,voice," + measures +
                    " FROM selected) INSERT INTO experiment_people "
                    "SELECT run_id,%s,%s,person_id,voice,sum(dials),sum(connected),sum(engaged) "
                    "FROM measured GROUP BY run_id,person_id,voice HAVING sum(dials)>0 "
                    "ON CONFLICT (run_id,experiment_id,phase,person_id,voice) DO UPDATE SET "
                    "dials=experiment_people.dials+EXCLUDED.dials,connected=experiment_people.connected+EXCLUDED.connected,"
                    "engaged=experiment_people.engaged+EXCLUDED.engaged",
                    (*params, eid, phase),
                )
                self.db.execute("INSERT INTO experiment_windows VALUES (%s,%s,%s,%s)", (self.run_id, eid, phase, end))
        with self.db.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(
                "SELECT person_id,voice,dials,connected,engaged FROM experiment_people "
                "WHERE run_id=%s AND experiment_id=%s AND phase=%s ORDER BY person_id,voice",
                (self.run_id, eid, phase),
            ).fetchall()
