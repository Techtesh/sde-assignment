import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg
import pytest

from controller.store import Store


URL = "http://simulator"
STATE = {"ts": "2027-01-04T09:00:00+05:30", "scenario": "one",
         "last_event_id": 10, "finished": False}


def automatic(database, state, url=URL):
    with psycopg.connect(database, autocommit=True) as db:
        store = Store(db, None, url, state=state)
        return store.run_id


def test_automatic_identity_survives_restart_and_uncertain_advance(database):
    first = automatic(database, STATE)
    assert automatic(database, STATE) == first
    advanced = {**STATE, "ts": "2027-01-04T09:15:00+05:30", "last_event_id": 20}
    assert automatic(database, advanced) == first


@pytest.mark.parametrize("replacement", [
    {**STATE, "scenario": "two"},
    {**STATE, "ts": "2027-01-04T08:45:00+05:30"},
    {**STATE, "last_event_id": 9},
])
def test_new_world_gets_new_identity_without_deleting_evidence(database, replacement):
    old = automatic(database, STATE)
    new = automatic(database, replacement)
    assert new != old
    assert automatic(database, replacement) == new
    with psycopg.connect(database, autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM controller_runs").fetchone()[0] == 2


def test_finished_world_restart_is_idempotent_and_new_unfinished_world_is_separate(database):
    finished = {**STATE, "finished": True}
    old = automatic(database, finished)
    assert automatic(database, finished) == old
    assert automatic(database, STATE) != old


def test_upgrade_adopts_compatible_legacy_default_but_other_urls_are_separate(database):
    with psycopg.connect(database, autocommit=True) as db:
        Store(db, "default", URL).observe_state(STATE)
    assert automatic(database, STATE) == "default"
    assert automatic(database, STATE, "http://another") != "default"


def test_second_automatic_writer_is_rejected(database):
    with psycopg.connect(database, autocommit=True) as first:
        Store(first, None, URL, state=STATE)
        with psycopg.connect(database, autocommit=True) as second:
            with pytest.raises(RuntimeError, match="already processing"):
                Store(second, None, URL, state=STATE)


@pytest.mark.skipif(sys.platform != "linux", reason="Exercises the real Bash launcher on Linux")
def test_launcher_without_run_flags_recovers_then_handles_two_new_worlds(database):
    initial = {**STATE, "last_event_id": 0, "credits_remaining": 200}
    state = dict(initial)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            value = state if self.path == "/sim/state" else [] if self.path.startswith(("/workflows", "/events/chunks")) else {}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(value).encode())

        def do_POST(self):
            assert self.path == "/sim/advance"
            state.update(ts="2027-01-04T09:15:00+05:30", finished=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    env = {**os.environ, "DATABASE_URL": database, "PYTHON": sys.executable}
    for name in ("SIM_RUN_ID", "CRASH_AT", "CONTROLLER_PROFILE"):
        env.pop(name, None)

    def launch(crash=False):
        process = subprocess.run(["bash", "./run.sh", f"http://127.0.0.1:{server.server_port}"],
                                 cwd=Path(__file__).resolve().parents[1],
                                 env={**env, **({"CRASH_AT": "after_advance"} if crash else {})},
                                 capture_output=True, text=True, timeout=30)
        assert process.returncode == (137 if crash else 0), process.stderr
        return json.loads(process.stdout.splitlines()[0])["run_id"]

    try:
        first = launch(crash=True)
        assert launch() == first
        assert launch() == first
        state.update(initial, scenario="two")
        second = launch()
        assert second != first
        state.update(initial, scenario="two")
        assert launch() not in {first, second}
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
