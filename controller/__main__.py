"""Ingest evidence and reconcile governed changes: python -m controller --url SIM_URL."""

import argparse
import json
import os
import sys
import time

import httpx
import psycopg

from .api import SimulatorAPI
from .governance import Governance
from .experiments import ExperimentEngine
from .incidents import IncidentEngine
from .store import Store
from .faults import crash_at
from .observability import audit, status, status_text


def drain(api: SimulatorAPI, store: Store) -> int:
    inserted = 0
    for kind in ("history", "events"):
        chunks = api.get("/events/chunks", kind=kind, after=store.last_chunk(kind))
        for chunk in sorted(chunks, key=lambda item: item["chunk"]):
            if chunk["kind"] != kind:
                raise ValueError("Chunk kind differs from requested stream")
            inserted += store.ingest(chunk, api.events(chunk["chunk"]))
    return inserted


def run(api: SimulatorAPI, store: Store, *, max_ticks: int | None = None, observe_only: bool = False) -> None:
    api.get("/health")
    state = api.get("/sim/state")
    store.observe_state(state)
    store.db.execute("INSERT INTO loop_starts (run_id,sim_ts) VALUES (%s,%s)", (store.run_id, state["ts"]))
    for workflow in sorted(api.get("/workflows"), key=lambda item: item["workflow_id"]):
        wid = workflow["workflow_id"]
        store.save_workflow(
            workflow, api.get(f"/workflows/{wid}/config"), api.get(f"/workflows/{wid}/config/history")
        )
    ticks = 0
    governance = Governance(api, store)
    incidents = IncidentEngine(api, store, governance)
    experiments = ExperimentEngine(api, store, governance)
    advance_seconds = 0.0
    while True:
        started = time.perf_counter()
        fetch_before, parse_before = api.stream_fetch_seconds, api.stream_parse_seconds
        inserted = drain(api, store)
        ingest_seconds = time.perf_counter() - started
        fetch_seconds = api.stream_fetch_seconds - fetch_before
        parse_seconds = api.stream_parse_seconds - parse_before
        decision_started = time.perf_counter()
        store.observe_state(state)
        governance.tick(state["ts"], allow_writes=not state["finished"] and not observe_only)
        snapshots = []
        for workflow in sorted(api.get("/workflows"), key=lambda item: item["workflow_id"]):
            wid = workflow["workflow_id"]
            config = api.get(f"/workflows/{wid}/config")
            store.save_workflow(workflow, config, [])
            snapshots.append((workflow, config))
        if not observe_only:
            incidents.tick(state, snapshots)
            experiments.tick(state, snapshots)
            governance.tick(state["ts"], allow_writes=not state["finished"])
        metrics = {
            "mode": "controller", "ts": state["ts"], "finished": state["finished"],
            "ingested_events": inserted, "ingest_seconds": round(ingest_seconds, 3),
            "stream_fetch_seconds": round(fetch_seconds, 3), "parse_seconds": round(parse_seconds, 3),
            "write_seconds": round(max(0, ingest_seconds-fetch_seconds-parse_seconds), 3),
            "decision_seconds": round(time.perf_counter()-decision_started, 3),
            "advance_seconds": round(advance_seconds, 3),
            "loop_seconds": round(time.perf_counter() - started, 3),
            "credits_remaining": state["credits_remaining"],
        }
        if sys.platform == "linux":
            import resource
            metrics["peak_rss_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
        store.record_tick(metrics)
        print(json.dumps(metrics), flush=True)
        if state["finished"] or (max_ticks is not None and ticks >= max_ticks):
            break
        # If this response is lost, exit. Restart reads /sim/state and drains chunks first.
        advance_started = time.perf_counter()
        api.advance()
        crash_at("after_advance")
        state = api.get("/sim/state")
        advance_seconds = time.perf_counter()-advance_started
        ticks += 1
    print(json.dumps({"metrics": store.summary()}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("run", "status", "audit"), default="run")
    parser.add_argument("--url")
    parser.add_argument("--workflow", help="workflow to inspect with audit")
    parser.add_argument("--at", help="audit the latest change at or before this ISO timestamp")
    parser.add_argument("--json", action="store_true", help="print the detailed status as JSON")
    parser.add_argument("--version", type=int, help="select an exact config version for audit when changes share a timestamp")
    parser.add_argument("--run-id", default=os.environ.get("SIM_RUN_ID", "default"))
    parser.add_argument("--sequential-testing", action="store_true", default=False)
    parser.add_argument("--observe-only", action="store_true", help="ingest and reconcile without config writes or paid calls")
    parser.add_argument("--max-ticks", type=int, help="stop after N advances; omit to run to completion")
    args = parser.parse_args()
    if args.sequential_testing:
        parser.error("Sequential testing is not implemented; use fixed evaluation checkpoints")
    if args.max_ticks is not None and args.max_ticks < 0:
        parser.error("--max-ticks must be non-negative")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        parser.error("Set DATABASE_URL to a PostgreSQL connection string (see docs/CONTROLLER.md)")
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as connection:
        if args.command != "run":
            if args.command == "audit" and not (args.workflow and args.at):
                parser.error("audit requires --workflow and --at")
            with connection.transaction():
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                result = status(connection, args.run_id) if args.command == "status" else audit(connection, args.run_id, args.workflow, args.at, args.version)
            print(status_text(result) if args.command == "status" and not args.json else json.dumps(result, default=str, indent=2))
            return
        if not args.url:
            parser.error("run requires --url")
        store = Store(connection, args.run_id, args.url.rstrip("/"))
        with httpx.Client(base_url=args.url.rstrip("/"), timeout=120) as client:
            run(SimulatorAPI(client), store, max_ticks=args.max_ticks, observe_only=args.observe_only)


if __name__ == "__main__":
    main()
