import sys
from contextlib import nullcontext

import httpx
import pytest

from controller.__main__ import main
from controller.api import SimulatorAPI


def clock(monkeypatch):
    elapsed = [0.0]
    monkeypatch.setattr("controller.api.time.monotonic", lambda: elapsed[0])
    monkeypatch.setattr("controller.api.time.sleep", lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
    return elapsed


def test_readiness_wait_handles_connection_refusal_and_startup_503(monkeypatch, capsys):
    elapsed = clock(monkeypatch)
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET" and request.url.path == "/health"
        assert request.extensions["timeout"]["read"] <= 2
        if len(requests) == 1:
            raise httpx.ConnectError("server starting", request=request)
        return httpx.Response(503 if len(requests) == 2 else 200)

    with httpx.Client(base_url="http://simulator", transport=httpx.MockTransport(handler)) as client:
        SimulatorAPI(client).wait_until_ready(timeout=5)
    assert len(requests) == 3 and elapsed[0] == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "Waiting" in output.err and "Simulator is ready." in output.err


def test_readiness_wait_stops_at_deadline(monkeypatch):
    elapsed = clock(monkeypatch)
    with httpx.Client(base_url="http://simulator", transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
        with pytest.raises(TimeoutError, match="within 1s"):
            SimulatorAPI(client).wait_until_ready(timeout=1)
    assert elapsed[0] == 1


def test_readiness_wait_does_not_hide_a_wrong_health_endpoint(monkeypatch):
    elapsed = clock(monkeypatch)
    with httpx.Client(base_url="http://simulator", transport=httpx.MockTransport(lambda _: httpx.Response(404))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            SimulatorAPI(client).wait_until_ready()
    assert elapsed[0] == 0


def test_cli_reports_readiness_timeout_without_a_traceback(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["controller", "--url", "http://simulator"])
    monkeypatch.setattr("controller.__main__.psycopg.connect", lambda *args, **kwargs: nullcontext(None))

    def timeout(self):
        raise TimeoutError("Simulator startup timed out")

    monkeypatch.setattr(SimulatorAPI, "wait_until_ready", timeout)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert capsys.readouterr().err == "Simulator startup timed out\n"


@pytest.mark.parametrize("configured", [None, "postgresql://custom/database"])
def test_cli_uses_local_database_default_and_respects_override(monkeypatch, configured):
    class ConnectionAttempt(Exception):
        pass

    monkeypatch.setattr(sys, "argv", ["controller", "status", "--run-id", "example"])
    if configured:
        monkeypatch.setenv("DATABASE_URL", configured)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)

    def connect(dsn, **kwargs):
        assert dsn == (configured or "postgresql://controller:controller@127.0.0.1:55432/controller")
        raise ConnectionAttempt

    monkeypatch.setattr("controller.__main__.psycopg.connect", connect)
    with pytest.raises(ConnectionAttempt):
        main()


@pytest.mark.parametrize("args,message", [
    ([], "run requires --url"),
    (["status"], "status/audit require --run-id"),
    (["audit", "--run-id", "example", "--workflow", "wf"], "audit requires --workflow and --end-time"),
])
def test_missing_cli_arguments_fail_before_connecting(monkeypatch, capsys, args, message):
    monkeypatch.setattr(sys, "argv", ["controller", *args])
    monkeypatch.delenv("SIM_RUN_ID", raising=False)

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Argument validation must happen first")

    monkeypatch.setattr("controller.__main__.psycopg.connect", unexpected_connection)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert message in capsys.readouterr().err
