#!/usr/bin/env python3
from __future__ import annotations

import json
import secrets
import sys
import shutil
import webbrowser
import os
from pathlib import Path
from http import HTTPStatus

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

THIS_DIR = Path(__file__).resolve().parent
ROOT_DIR = THIS_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure these imports work; if not, dependencies might be missing
try:
    from app.db.session import init_db
    from app.routes.report import get_history, get_report
    from app.routes.upload import build_processing_trace, run_pipeline
    from src.ddr_builder import load_document, render_simple_pdf
except ImportError as e:
    print(f"Error importing app modules: {e}")
    sys.exit(1)

WEB_DIR = ROOT_DIR / "web"
OUTPUT_DIR = Path("output/history")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="DDR AI Report Generator")

# CORS middleware to allow frontend access if needed (though we serve static files)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Index file not found")
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

@app.get("/index.html", response_class=HTMLResponse)
async def read_index():
    return await read_root()

@app.get("/app.js")
async def read_js():
    return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")

@app.get("/styles.css")
async def read_css():
    return FileResponse(WEB_DIR / "styles.css", media_type="text/css")

@app.get("/api/processing-trace")
async def get_processing_trace():
    return {"trace": build_processing_trace()}

@app.get("/api/history")
async def get_history_api():
    return {"items": get_history()}

@app.get("/api/report")
async def get_report_api(id: str):
    record = get_report(id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")
    return record

@app.get("/api/download/pdf")
async def download_pdf(id: str):
    file_path = OUTPUT_DIR / f"{id}.pdf"
    if not file_path.exists():
         raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/pdf", filename=f"report_{id}.pdf")

@app.get("/api/download/json")
async def download_json(id: str):
    file_path = OUTPUT_DIR / f"{id}.json"
    if not file_path.exists():
         raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/json", filename=f"report_{id}.json")

@app.post("/api/upload")
async def upload_files(inspection: UploadFile = File(...), thermal: UploadFile = File(...)):
    # 1. Create a temp directory
    report_id = secrets.token_hex(8)
    temp_dir = OUTPUT_DIR / f"tmp_{report_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 2. Save uploaded files
        inspection_path = temp_dir / (inspection.filename or "inspection.bin")
        thermal_path = temp_dir / (thermal.filename or "thermal.bin")

        with inspection_path.open("wb") as buffer:
            shutil.copyfileobj(inspection.file, buffer)
        with thermal_path.open("wb") as buffer:
            shutil.copyfileobj(thermal.file, buffer)

        # 3. Process documents
        # load_document returns (text, notes_list)
        inspection_text, inspection_notes = load_document(str(inspection_path))
        thermal_text, thermal_notes = load_document(str(thermal_path))

        # 4. Run Pipeline
        report = run_pipeline(report_id, inspection_text, thermal_text, inspection_notes + thermal_notes)

        # 5. Save Artifacts
        report_json_path = OUTPUT_DIR / f"{report_id}.json"
        report_pdf_path = OUTPUT_DIR / f"{report_id}.pdf"
        
        report_json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        render_simple_pdf(json.dumps(report.to_dict(), indent=2), report_pdf_path)

        return {
            "report_id": report_id,
            "report": report.to_dict(),
            "downloads": {
                "json": f"/api/download/json?id={report_id}",
                "pdf": f"/api/download/pdf?id={report_id}",
            },
        }

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        print(f"Pipeline failed: {exc}") # Log to console
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(exc)}")
    finally:
        # Cleanup temp dir
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8010))
    print(f"DDR AI App running at http://localhost:{port}")
    
    # Try to open browser (only if localhost/127.0.0.1 effectively)
    # Using a separate thread or just attempting before run
    try:
        webbrowser.open(f"http://localhost:{port}")
    except:
        pass

    # For production/deployment, uvicorn.run is fine.
    # reload=True is good for dev, can be removed for prod. 
    # Use 0.0.0.0 for container/network access.
    uvicorn.run(app, host=host, port=port)