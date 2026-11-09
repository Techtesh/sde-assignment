"""HTTP boundary: reads may retry; uncertain time/config mutations must not."""

import json
import sys
import time
from collections.abc import Iterator

import httpx


class SimulatorAPI:
    def __init__(self, client: httpx.Client):
        self.client = client
        self.stream_fetch_seconds = 0.0
        self.stream_parse_seconds = 0.0

    def wait_until_ready(self, timeout: float = 60.0) -> None:
        print(f"Waiting up to {timeout:g}s for simulator readiness...", file=sys.stderr, flush=True)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Simulator did not become ready within {timeout:g}s; check its URL and server process")
            try:
                response = self.client.get("/health", timeout=min(2.0, remaining))
                response.raise_for_status()
                print("Simulator is ready.", file=sys.stderr, flush=True)
                return
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise
            time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))

    def get(self, path: str, **params):
        for attempt in range(3):
            try:
                response = self.client.get(path, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise
                if attempt == 2:
                    raise
                time.sleep(0.2 * 2**attempt)

    def events(self, chunk: int) -> Iterator[dict]:
        # A failed stream rolls back the whole chunk; restart retries discovery.
        started = time.perf_counter()
        with self.client.stream("GET", f"/events/chunks/{chunk}") as response:
            response.raise_for_status()
            self.stream_fetch_seconds += time.perf_counter() - started
            lines = iter(response.iter_lines())
            while True:
                started = time.perf_counter()
                line = next(lines, None)
                self.stream_fetch_seconds += time.perf_counter() - started
                if line is None:
                    break
                if line.strip():
                    started = time.perf_counter()
                    event = json.loads(line)
                    self.stream_parse_seconds += time.perf_counter() - started
                    if not isinstance(event, dict):
                        raise ValueError("Expected an event object")
                    yield event

    def mutate(self, method: str, path: str, body: dict) -> httpx.Response:
        # The durable governance state machine reconciles uncertainty before any retry.
        return self.client.request(method, path, json=body)

    def advance(self) -> dict:
        response = self.client.post("/sim/advance", json={"minutes": 15})
        if response.status_code == 409:
            # Confirm completion independently; other conflicts remain failures.
            state = self.get("/sim/state")
            if state["finished"]:
                return state
        response.raise_for_status()
        return response.json()
