from __future__ import annotations

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agentkit.extensions.harness_sidecar.failover_proxy import StableHttpRelay


def _upstream(label: str):
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            requests.append({"path": self.path, "body": body.decode("utf-8")})
            payload = json.dumps({"upstream": label}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}", requests


def test_stable_relay_switches_to_direct_upstream_without_changing_url() -> None:
    sidecar, sidecar_thread, sidecar_url, sidecar_requests = _upstream("sidecar")
    direct, direct_thread, direct_url, direct_requests = _upstream("direct")
    relay = StableHttpRelay(f"{sidecar_url}/api/v3", f"{direct_url}/direct/v3")
    stable_url = relay.url
    request_url = f"{stable_url}/chat/completions?trace=test"

    try:
        request = urllib.request.Request(
            request_url, data=b'{"messages":[]}', method="POST"
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert json.loads(response.read()) == {"upstream": "sidecar"}

        relay.activate_fallback()
        request = urllib.request.Request(
            request_url, data=b'{"messages":[]}', method="POST"
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert json.loads(response.read()) == {"upstream": "direct"}
    finally:
        relay.close()
        for server, thread in (
            (sidecar, sidecar_thread),
            (direct, direct_thread),
        ):
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    assert relay.url == stable_url
    assert sidecar_requests == [
        {"path": "/api/v3/chat/completions?trace=test", "body": '{"messages":[]}'}
    ]
    assert direct_requests == [
        {"path": "/direct/v3/chat/completions?trace=test", "body": '{"messages":[]}'}
    ]
