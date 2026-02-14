#!/usr/bin/env python3
"""Minimal UI for DDR generation and PDF download."""

from __future__ import annotations

import html
import secrets
import sys
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict
from urllib.parse import parse_qs, urlparse

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from ddr_builder import build_ddr, load_document, render_markdown, render_simple_pdf

REPORT_STORE: Dict[str, Dict[str, bytes | str]] = {}

PAGE_STYLE = """
<style>
  body { font-family: Arial, sans-serif; background:#f5f7fb; margin:0; padding:0; color:#1b1f24; }
  .wrap { max-width: 920px; margin: 24px auto; background:white; border-radius:14px; box-shadow:0 8px 24px rgba(0,0,0,0.08); overflow:hidden; }
  .header { padding:20px 24px; background: linear-gradient(90deg,#2f6fed,#2f9cf0); color:white; }
  .content { padding:24px; }
  .row { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  .card { border:1px solid #e2e8f0; border-radius:10px; padding:16px; background:#fafcff; }
  label { font-weight:600; display:block; margin-bottom:8px; }
  input[type=file] { width:100%; margin-bottom:8px; }
  .btn { background:#2f6fed; color:white; border:none; padding:10px 14px; border-radius:8px; cursor:pointer; font-weight:600; }
  .btn:hover { background:#2459bf; }
  .report { margin-top:20px; border:1px solid #dbe4f0; border-radius:10px; background:#fcfdff; padding:16px; }
  pre { white-space:pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .msg { padding:10px 12px; border-radius:8px; margin-bottom:12px; }
  .ok { background:#ebfff2; border:1px solid #a7e5bc; }
  .err { background:#fff1f1; border:1px solid #f0b5b5; }
</style>
"""


def render_page(message: str = "", report_markdown: str = "", report_id: str = "") -> str:
    msg_html = ""
    if message:
        msg_html = f'<div class="msg {"ok" if report_markdown else "err"}">{html.escape(message)}</div>'

    actions = ""
    if report_id:
        actions = (
            f'<p><a class="btn" href="/download?id={report_id}">Download PDF Report</a></p>'
        )

    report_html = ""
    if report_markdown:
        report_html = (
            "<div class='report'><h3>Generated DDR Report (Preview)</h3>"
            f"<pre>{html.escape(report_markdown)}</pre>{actions}</div>"
        )

    return f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <title>Urban Roof DDR Builder</title>
  {PAGE_STYLE}
</head>
<body>
  <div class="wrap">
    <div class="header">
      <h2>Urban Roof - DDR Report Builder</h2>
      <p>Upload inspection + thermal files, view report, and download PDF.</p>
    </div>
    <div class="content">
      {msg_html}
      <form method="post" enctype="multipart/form-data">
        <div class="row">
          <div class="card">
            <label>Inspection File</label>
            <input type="file" name="inspection" required>
          </div>
          <div class="card">
            <label>Thermal File</label>
            <input type="file" name="thermal" required>
          </div>
        </div>
        <p style="margin-top:16px"><button class="btn" type="submit">Generate Report</button></p>
      </form>
      {report_html}
    </div>
  </div>
</body>
</html>
"""


class DDRUIHandler(BaseHTTPRequestHandler):
    def _send_html(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(render_page())
            return

        if parsed.path == "/download":
            query = parse_qs(parsed.query)
            report_id = query.get("id", [""])[0]
            report = REPORT_STORE.get(report_id)
            if not report:
                self._send_html(render_page("Report not found. Generate a new one."), HTTPStatus.NOT_FOUND)
                return

            pdf_bytes = report["pdf"]
            if not isinstance(pdf_bytes, bytes):
                self._send_html(render_page("Stored report is invalid."), HTTPStatus.INTERNAL_SERVER_ERROR)
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", "attachment; filename=main_ddr.pdf")
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)
            return

        self._send_html(render_page("Page not found."), HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_html(render_page("Invalid form submission."), HTTPStatus.BAD_REQUEST)
            return

        boundary = content_type.split("boundary=")[-1].encode("utf-8")
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)

        parts = body.split(b"--" + boundary)
        files = {}
        for part in parts:
            if b"Content-Disposition" not in part or b"filename=" not in part:
                continue
            headers, _, payload = part.partition(b"\r\n\r\n")
            payload = payload.rstrip(b"\r\n")
            disp_line = [line for line in headers.split(b"\r\n") if b"Content-Disposition" in line]
            if not disp_line:
                continue
            disp = disp_line[0].decode("utf-8", errors="ignore")
            name_match = "name=\"inspection\"" if "name=\"inspection\"" in disp else ("name=\"thermal\"" if "name=\"thermal\"" in disp else "")
            if not name_match:
                continue
            key = "inspection" if "inspection" in name_match else "thermal"
            filename = "uploaded.bin"
            if "filename=\"" in disp:
                filename = disp.split("filename=\"")[1].split("\"")[0] or filename
            files[key] = (filename, payload)

        if "inspection" not in files or "thermal" not in files:
            self._send_html(render_page("Both inspection and thermal files are required."), HTTPStatus.BAD_REQUEST)
            return

        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                in_name, in_data = files["inspection"]
                th_name, th_data = files["thermal"]

                inspection_path = tmp_dir / in_name
                thermal_path = tmp_dir / th_name
                inspection_path.write_bytes(in_data)
                thermal_path.write_bytes(th_data)

                inspection_text, inspection_notes = load_document(str(inspection_path))
                thermal_text, thermal_notes = load_document(str(thermal_path))

                ddr = build_ddr(inspection_text, thermal_text, ingestion_notes=inspection_notes + thermal_notes)
                markdown = render_markdown(ddr)

                pdf_path = tmp_dir / "main_ddr.pdf"
                render_simple_pdf(markdown, pdf_path)
                pdf_bytes = pdf_path.read_bytes()

            report_id = secrets.token_urlsafe(10)
            REPORT_STORE[report_id] = {"markdown": markdown, "pdf": pdf_bytes}
            self._send_html(render_page("Report generated successfully.", report_markdown=markdown, report_id=report_id))
        except Exception as exc:  # keep UI resilient
            self._send_html(render_page(f"Could not generate report: {exc}"), HTTPStatus.INTERNAL_SERVER_ERROR)


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), DDRUIHandler)
    print(f"UI running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
