from __future__ import annotations

import json
import mimetypes
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from autonomy.contextual_search_plan import create_contextual_search_plan
from autonomy.mission_command import create_mission_command
from autonomy.mission_memory import build_mission_memory
from autonomy.mission_vision_plan import create_mission_vision_plan


ROOT = Path(__file__).parent.resolve()
STATIC = ROOT / "static"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class AnalystHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/reports":
            self._send_json({"reports": list_reports()})
            return
        if parsed.path == "/api/report":
            report_path = first_query_value(parsed.query, "path")
            self._send_json(load_report_payload(report_path))
            return
        if parsed.path == "/api/mission-memory":
            self._send_json({"ok": True, "memory": build_mission_memory(ROOT)})
            return
        if parsed.path == "/api/file":
            file_path = first_query_value(parsed.query, "path")
            self._send_file(file_path)
            return
        if parsed.path == "/":
            self.path = "/static/analyst.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/mission-plan":
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                result = create_mission_plan_payload(payload)
                self._send_json(result, 200 if result.get("ok") else 400)
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "Invalid JSON"}, 400)
            return
        if parsed.path != "/api/review":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = save_review(payload)
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
        encoded = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, file_path: str | None) -> None:
        path = resolve_local_path(file_path)
        if path is None or not path.exists() or path.suffix.lower() not in IMAGE_SUFFIXES:
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def list_reports() -> list[dict]:
    reports = []
    for report_path in sorted((ROOT / "logs").glob("**/vision_report.json"), reverse=True):
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summary = data.get("summary") or {}
        evaluation = data.get("evaluation") or {}
        analyst_capture = evaluation.get("analyst_capture") or {}
        reports.append(
            {
                "path": str(report_path.relative_to(ROOT)),
                "timestamp": data.get("timestamp"),
                "mission_request": data.get("mission_request"),
                "proposal_mode": data.get("proposal_mode"),
                "scorer": data.get("scorer"),
                "processed": summary.get("processed"),
                "detections": summary.get("detections"),
                "shortlist_count": summary.get("shortlist_count"),
                "precision": evaluation.get("precision"),
                "recall": evaluation.get("recall"),
                "f1": evaluation.get("f1"),
                "capture_recall": analyst_capture.get("recall"),
            }
        )
    return reports


def create_mission_plan_payload(payload: dict) -> dict:
    request = str(payload.get("mission_request") or "").strip()
    if not request:
        return {"ok": False, "error": "mission_request is required"}
    mode = str(payload.get("operating_mode") or "connected-supervised")
    try:
        command = create_mission_command(request, operating_mode=mode)
        vision_plan = create_mission_vision_plan(command.objective)
        contextual_search_plan = create_contextual_search_plan(command.objective)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "mission_request": request,
        "command": asdict(command),
        "vision_plan": asdict(vision_plan),
        "contextual_search_plan": asdict(contextual_search_plan),
        "next_actions": [
            "Run a vision-only benchmark against image or video evidence.",
            "Review shortlisted candidates in the analyst dashboard.",
            "Use PX4/Gazebo only when validating a moving sensor platform.",
        ],
    }


def load_report_payload(report_path: str | None) -> dict:
    path = resolve_local_path(report_path)
    if path is None or path.name != "vision_report.json" or not path.exists():
        return {"ok": False, "error": "Report not found"}
    data = json.loads(path.read_text(encoding="utf-8"))
    reviews = load_reviews(path)
    return {"ok": True, "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), "report": data, "reviews": reviews}


def save_review(payload: dict) -> dict:
    report_path = resolve_local_path(str(payload.get("report_path", "")))
    if report_path is None or report_path.name != "vision_report.json" or not report_path.exists():
        return {"ok": False, "error": "Report not found"}
    candidate_key = str(payload.get("candidate_key") or "")
    if not candidate_key:
        return {"ok": False, "error": "candidate_key is required"}
    decision = normalize_decision(payload.get("decision") or payload.get("status") or "investigate")
    reason = str(payload.get("reason") or "").strip()
    notes = str(payload.get("notes") or "")
    reviews = load_reviews(report_path)
    reviews[candidate_key] = {
        "candidate_id": str(payload.get("candidate_id") or candidate_key),
        "decision": decision,
        "status": decision,
        "reason": reason,
        "notes": notes,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    review_path(report_path).write_text(json.dumps(reviews, indent=2), encoding="utf-8")
    return {"ok": True, "reviews": reviews}


def load_reviews(report_path: Path) -> dict:
    path = review_path(report_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def review_path(report_path: Path) -> Path:
    return report_path.with_name("candidate_reviews.json")


def normalize_decision(value) -> str:
    decision = str(value or "").strip().lower()
    aliases = {
        "approved": "approve",
        "confirmed": "approve",
        "rejected": "reject",
        "needs_closer_look": "investigate",
        "needs closer look": "investigate",
    }
    decision = aliases.get(decision, decision)
    if decision not in {"approve", "reject", "investigate"}:
        return "investigate"
    return decision


def resolve_local_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    decoded = unquote(path_value)
    path = Path(decoded)
    if not path.is_absolute():
        path = ROOT / decoded
    return path.resolve()


def first_query_value(query: str, key: str) -> str | None:
    values = parse_qs(query).get(key)
    return values[0] if values else None


def _port_from_args() -> int:
    if "--port" in sys.argv:
        index = sys.argv.index("--port")
        if index + 1 >= len(sys.argv):
            raise SystemExit("--port requires a value")
        return int(sys.argv[index + 1])
    return int(os.environ.get("ANALYST_DASHBOARD_PORT", "8010"))


def main() -> None:
    port = _port_from_args()
    server = ThreadingHTTPServer(("127.0.0.1", port), AnalystHandler)
    print(f"Analyst dashboard running at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
