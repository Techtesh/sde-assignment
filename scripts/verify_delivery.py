"""External verification: simulator CLI + HTTP, never imported simulator internals.

Run from the repository root. DATABASE_URL supplies PostgreSQL. A crash matrix uses
isolated retained schemas with the same run ID so decision IDs remain comparable.
"""

import argparse
import hashlib
import json
import os
import pstats
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo


POINTS = ("mid_ingest", "after_advance", "after_intent", "after_post", "after_apply")


def get(client, path, **params):
    response = client.get(path, params=params)
    response.raise_for_status()
    return response.json()


def signature(db, client, run_id):
    """Compare committed business evidence, allowing extra recovery audit transitions."""
    data = {}
    for table, columns, order in (
        ("ingested_chunks", "chunk,kind,event_count", "chunk"),
        ("hourly_metrics", "workflow_id,history,hour,config_version,cohort_id,dimension,variant,dials,connected,engaged,hallucinations", "workflow_id,history,hour,config_version,cohort_id,dimension,variant"),
        ("proposals", "proposal_id,decision_id,workflow_id,body,route,status,approval_id", "proposal_id"),
        ("experiments", "experiment_id,workflow_id,status,data", "experiment_id"),
        ("experiment_people", "experiment_id,phase,person_id,voice,dials,connected,engaged", "experiment_id,phase,person_id,voice"),
        ("incidents", "incident_id,workflow_id,kind,status,proposal_id,data", "incident_id"),
        ("audit_log", "event_id,ts,workflow_id,kind,actor,evidence", "event_id"),
        ("detection_windows", "workflow_id,config_version,kind,subject,hour,streak,episode_start,evidence", "workflow_id,config_version,kind,subject,hour"),
    ):
        count, digest = 0, hashlib.sha256()
        with db.transaction(), db.cursor(name="evidence_signature") as cursor:
            cursor.execute(f"SELECT {columns} FROM {table} WHERE run_id=%s ORDER BY {order}", (run_id,))
            for record in cursor:
                digest.update(json.dumps(record, sort_keys=True, default=str).encode()+b"\n")
                count += 1
        data[table] = {"rows": count, "sha256": digest.hexdigest()}
    for table in ("campaigns", "concluded_leads", "person_metrics", "qa_metrics"):
        count, fingerprint = db.execute(f"SELECT count(*),sum(hashtextextended(row_to_json(t)::text,0)::numeric) "
                                        f"FROM {table} t WHERE run_id=%s", (run_id,)).fetchone()
        data[table] = {"rows": count, "fingerprint": str(fingerprint)}
    data["events"] = list(db.execute(
        "SELECT count(*),min(event_id),max(event_id),sum(hashtextextended(payload::text,0)::numeric) "
        "FROM events WHERE run_id=%s", (run_id,)).fetchone())
    data["state"] = get(client, "/sim/state")
    assert data["events"][2] == data["state"]["last_event_id"], "Final events are missing"
    assert data["ingested_chunks"]["rows"] == data["state"]["chunks"], "Final chunks are missing"
    data["config_history"] = {}
    data["approvals"] = {}
    data["workflows"] = get(client, "/workflows")
    for workflow in data["workflows"]:
        wid = workflow["workflow_id"]
        history = get(client, f"/workflows/{wid}/config/history")
        applied_ids = [item["proposal_id"] for item in history if item.get("proposal_id")]
        assert len(applied_ids) == len(set(applied_ids)), "A proposal was applied twice"
        approvals = get(client, "/approvals", workflow_id=wid)
        assert len({item["proposal_id"] for item in approvals}) == len(approvals), "Duplicate approval request"
        data["config_history"][wid] = history
        data["approvals"][wid] = approvals
    return data


def timings(log: Path, wall_seconds: float) -> dict:
    ticks = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.startswith('{"mode":')]
    assert ticks and ticks[-1]["finished"], "Controller did not finish"
    fields = ("ingest_seconds", "stream_fetch_seconds", "parse_seconds", "write_seconds", "decision_seconds", "advance_seconds", "loop_seconds")
    totals = {field: round(sum(tick[field] for tick in ticks), 3) for field in fields}
    start, end = (datetime.fromisoformat(ticks[index]["ts"]) for index in (0, -1))
    days = (end-start).total_seconds()/86400
    live = ticks[1:]
    per_day = {}
    for tick in live:
        day = min(int((datetime.fromisoformat(tick["ts"])-start).total_seconds()//86400), int(days)-1)
        per_day[day] = per_day.get(day, 0) + tick["loop_seconds"] + tick["advance_seconds"]
    return {"ticks": len(ticks), "simulated_days": days, "wall_seconds": round(wall_seconds, 3),
            "wall_seconds_per_day_including_bootstrap": round(wall_seconds/days, 3),
            "bootstrap": ticks[0], "totals": totals,
            "live_events": sum(tick["ingested_events"] for tick in live),
            "live_ingest_events_per_second": round(sum(tick["ingested_events"] for tick in live)/max(.001, sum(tick["ingest_seconds"] for tick in live)), 1),
            "max_decision_lag_bound_seconds": max(round(tick["advance_seconds"]+tick["loop_seconds"], 3) for tick in live),
            "live_wall_seconds_by_simulated_day": {str(k): round(v, 3) for k, v in per_day.items()},
            "peak_controller_rss_mib": max((tick.get("peak_rss_mib", 0) for tick in ticks), default=0)}


def run_case(args, case, schema, dsn):
    application_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    source_hash = hashlib.sha256()
    for path in sorted(Path("controller").iterdir()):
        if path.suffix in {".py", ".sql"}:
            source_hash.update(path.as_posix().encode() + b"\0" + path.read_bytes().replace(b"\r\n", b"\n"))
    directory = Path("runs") / f"{args.label}_{case}_{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True)
    isolated = make_conninfo(dsn, options=f"-csearch_path={schema}")
    env = {**os.environ, "DATABASE_URL": isolated, "SIM_RUN_ID": args.label, "PYTHONUTF8": "1"}
    env.pop("CRASH_AT", None)
    url = f"http://127.0.0.1:{args.port}"
    command = [sys.executable, "-m", "controller", "--url", url, "--run-id", args.label]
    if args.profile:
        command[1:1] = ["-m", "cProfile", "-o", str(directory/"controller.prof")]
    if args.linux:
        settings = conninfo_to_dict(isolated)
        network = ["--network", "host"] if sys.platform == "linux" else []
        sim_url = url if network else f"http://host.docker.internal:{args.port}"
        if not network and settings.get("host") in ("127.0.0.1", "localhost"):
            settings["host"] = "host.docker.internal"
        # Aggregate controller + database budget: 3 CPUs/6 GiB + 1 CPU/2 GiB.
        command = ["docker", "run", "--rm", *network, "--cpus", "3", "--memory", "6g", "--memory-swap", "6g",
                   "-e", "DATABASE_URL=" + make_conninfo(**settings), "-e", "SIM_RUN_ID=" + args.label,
                   "-v", f"{Path.cwd()}:/app:ro", "formi-controller:milestone5", sim_url]
        if args.profile:
            command[3:3] = ["-v", f"{directory.resolve()}:/evidence", "-e", "CONTROLLER_PROFILE=/evidence/controller.prof"]
    with (directory/"simulator.log").open("w", encoding="utf-8") as simulator_log:
        server = subprocess.Popen([sys.executable, "-m", "sim", "serve", "--scenario", args.scenario,
                                   "--run-dir", str(directory/"world"), "--port", str(args.port)],
                                  stdout=simulator_log, stderr=subprocess.STDOUT, env=env)
        try:
            with httpx.Client(base_url=url, timeout=120) as client:
                deadline = time.monotonic()+600
                while True:
                    if server.poll() is not None:
                        raise RuntimeError(f"Simulator exited; see {directory/'simulator.log'}")
                    try:
                        get(client, "/health")
                        break
                    except httpx.TransportError:
                        if time.monotonic() > deadline:
                            raise TimeoutError("Simulator did not become healthy")
                        time.sleep(.25)
                if case != "clean":
                    crash_command = command
                    crash_env = {**env, "CRASH_AT": case}
                    if args.linux:
                        crash_command = [*command[:3], "-e", "CRASH_AT="+case, *command[3:]]
                    with (directory/"crash.log").open("w", encoding="utf-8") as output:
                        failed = subprocess.run(crash_command, env=crash_env, stdout=output, stderr=subprocess.STDOUT, timeout=1800)
                    assert failed.returncode == 137, f"Crash point not reached: {case}; see {directory/'crash.log'}"
                    print(json.dumps({"case": case, "exit": failed.returncode, "restarting": True}), flush=True)
                started = time.perf_counter()
                with (directory/"controller.log").open("w", encoding="utf-8") as output:
                    finished = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=7200)
                elapsed = time.perf_counter()-started
                assert finished.returncode == 0, f"Controller failed; see {directory/'controller.log'}"
                with psycopg.connect(isolated, autocommit=True) as db:
                    evidence = signature(db, client, args.label)
                assert evidence["state"]["finished"]
                result = {"case": case, "schema": schema, "run_id": args.label, "directory": str(directory),
                          "application_commit": application_commit,
                          "application_tree_sha256": source_hash.hexdigest(),
                          "application_controller_tree": subprocess.check_output(["git", "rev-parse", "HEAD:controller"], text=True).strip(),
                          "application_dirty": bool(subprocess.check_output(["git", "status", "--porcelain", "--", "controller"]).strip()),
                          "profiled": args.profile,
                          "exit": finished.returncode, "timings": timings(directory/"controller.log", elapsed),
                          "signature": evidence}
                if args.profile:
                    profile = pstats.Stats(str(directory/"controller.prof"))
                    hottest = sorted(profile.stats.items(),key=lambda item:item[1][3],reverse=True)[:25]
                    result["profile"] = {"total_calls":profile.total_calls,"elapsed_accounted_seconds":profile.total_tt,
                                         "functions":[{"file":key[0],"line":key[1],"function":key[2],
                                                       "calls":value[1],"internal_seconds":value[2],"cumulative_seconds":value[3]}
                                                      for key,value in hottest]}
                if case == "clean" and args.baseline:
                    subprocess.run([sys.executable, "-X", "utf8", "-m", "sim", "grade", "--run", str(directory/"world"),
                                    "--baseline", args.baseline, "--out", args.grade], check=True)
                return result
        finally:
            server.terminate()
            server.wait(timeout=20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--port", type=int, default=8720)
    parser.add_argument("--linux", action="store_true", help="use the Docker image with 3 CPUs/6 GiB")
    parser.add_argument("--crash-matrix", action="store_true")
    parser.add_argument("--profile", action="store_true", help="capture cProfile; its overhead is included in measured wall time")
    parser.add_argument("--baseline")
    parser.add_argument("--grade")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not re.fullmatch("[a-z][a-z0-9_]{0,35}", args.label):
        parser.error("label must be a short lowercase PostgreSQL identifier")
    if bool(args.baseline) != bool(args.grade):
        parser.error("provide --baseline and --grade together")
    dsn = os.environ["DATABASE_URL"]
    results = []
    with psycopg.connect(dsn, autocommit=True) as admin:
        for case in ("clean", *POINTS) if args.crash_matrix else ("clean",):
            schema = f"{args.label}_{case}_{uuid.uuid4().hex[:6]}"
            admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            result = run_case(args, case, schema, dsn)
            if results:
                result["matches_clean"] = result["signature"] == results[0]["signature"]
            results.append(result)
            Path(args.out).write_text(json.dumps(results, indent=2, default=str)+"\n", encoding="utf-8")
            assert result.get("matches_clean",True), f"Recovery differs from clean run: {case}; both signatures retained in {args.out}"
            print(json.dumps({"case": case, "finished": True, "matches_clean": result.get("matches_clean"),
                              "wall_seconds": result["timings"]["wall_seconds"], "schema": schema}), flush=True)


if __name__ == "__main__":
    main()
