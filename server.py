from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from drone_sim import DroneSimulation


ROOT = Path(__file__).parent.resolve()
STATIC = ROOT / "static"
simulation = DroneSimulation(ROOT / "mission_config.json")


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self._send_json(simulation.snapshot())
            return
        if parsed.path == "/":
            self.path = "/static/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/command":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            command = str(payload.get("command", ""))
            result = simulation.command(command, payload)
            self._send_json(result, 200 if result.get("ok") else 400)
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "Invalid JSON"}, 400)

    def translate_path(self, path: str) -> str:
        clean_path = urlparse(path).path.lstrip("/")
        return str(ROOT / clean_path)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, body: dict, status: int = 200) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _port_from_args() -> int:
    if "--port" in sys.argv:
        index = sys.argv.index("--port")
        if index + 1 >= len(sys.argv):
            raise SystemExit("--port requires a value")
        return int(sys.argv[index + 1])
    return int(os.environ.get("DRONE_DASHBOARD_PORT", "8000"))


def main() -> None:
    simulation.start_background()
    port = _port_from_args()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Dashboard running at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        simulation.stop_background()
        server.server_close()


if __name__ == "__main__":
    main()
