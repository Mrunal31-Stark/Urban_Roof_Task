#!/usr/bin/env python3
from __future__ import annotations
from fastapi import FastAPI
import json
import secrets
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
app = FastAPI(title="DDR AI Report Generator")
import os
import uvicorn



THIS_DIR = Path(__file__).resolve().parent
ROOT_DIR = THIS_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import init_db
from app.routes.report import get_history, get_report
from app.routes.upload import build_processing_trace, run_pipeline
from src.ddr_builder import load_document, render_simple_pdf

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
OUTPUT_DIR = Path("output/history")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class DDRHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            return self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if parsed.path == "/app.js":
            return self._send_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        if parsed.path == "/styles.css":
            return self._send_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
        if parsed.path == "/api/processing-trace":
            return self._send_json({"trace": build_processing_trace()})
        if parsed.path == "/api/history":
            return self._send_json({"items": get_history()})
        if parsed.path == "/api/report":
            report_id = parse_qs(parsed.query).get("id", [""])[0]
            record = get_report(report_id)
            if not record:
                return self._send_json({"error": "Report not found"}, HTTPStatus.NOT_FOUND)
            return self._send_json(record)
        if parsed.path == "/api/download/pdf":
            report_id = parse_qs(parsed.query).get("id", [""])[0]
            return self._send_file(OUTPUT_DIR / f"{report_id}.pdf", "application/pdf")
        if parsed.path == "/api/download/json":
            report_id = parse_qs(parsed.query).get("id", [""])[0]
            return self._send_file(OUTPUT_DIR / f"{report_id}.json", "application/json; charset=utf-8")

        return self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/upload":
            return self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return self._send_json({"error": "multipart/form-data required"}, HTTPStatus.BAD_REQUEST)

        boundary = content_type.split("boundary=")[-1].encode("utf-8")
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)

        files: dict[str, tuple[str, bytes]] = {}
        for part in body.split(b"--" + boundary):
            if b"Content-Disposition" not in part or b"filename=" not in part:
                continue
            headers, _, payload = part.partition(b"\r\n\r\n")
            payload = payload.rstrip(b"\r\n")
            disp = next((line for line in headers.split(b"\r\n") if b"Content-Disposition" in line), b"")
            disp_s = disp.decode("utf-8", errors="ignore")
            if "name=\"inspection\"" in disp_s:
                key = "inspection"
            elif "name=\"thermal\"" in disp_s:
                key = "thermal"
            else:
                continue
            filename = "uploaded.bin"
            if "filename=\"" in disp_s:
                filename = disp_s.split("filename=\"")[1].split("\"")[0] or filename
            files[key] = (filename, payload)

        if "inspection" not in files or "thermal" not in files:
            return self._send_json({"error": "Both inspection and thermal files are required"}, HTTPStatus.BAD_REQUEST)

        report_id = secrets.token_hex(8)
        temp_dir = OUTPUT_DIR / f"tmp_{report_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            in_name, in_data = files["inspection"]
            th_name, th_data = files["thermal"]
            inspection_path = temp_dir / in_name
            thermal_path = temp_dir / th_name
            inspection_path.write_bytes(in_data)
            thermal_path.write_bytes(th_data)

            inspection_text, inspection_notes = load_document(str(inspection_path))
            thermal_text, thermal_notes = load_document(str(thermal_path))
            report = run_pipeline(report_id, inspection_text, thermal_text, inspection_notes + thermal_notes)

            report_json_path = OUTPUT_DIR / f"{report_id}.json"
            report_pdf_path = OUTPUT_DIR / f"{report_id}.pdf"
            report_json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
            render_simple_pdf(json.dumps(report.to_dict(), indent=2), report_pdf_path)

            return self._send_json({
                "report_id": report_id,
                "report": report.to_dict(),
                "downloads": {
                    "json": f"/api/download/json?id={report_id}",
                    "pdf": f"/api/download/pdf?id={report_id}",
                },
            })
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY)
        except Exception as exc:
            return self._send_json({"error": f"Pipeline failed: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            for p in temp_dir.glob("**/*"):
                if p.is_file():
                    p.unlink(missing_ok=True)
            for p in sorted(temp_dir.glob("**/*"), reverse=True):
                if p.is_dir():
                    p.rmdir()
            temp_dir.rmdir()


def run(host: str = "0.0.0.0", port: int = 8010) -> None:
    init_db()
    server = ThreadingHTTPServer((host, port), DDRHandler)
    print(f"DDR app running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8010))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)