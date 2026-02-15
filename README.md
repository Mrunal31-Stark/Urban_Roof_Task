# Applied AI Builder: DDR Report Generation

This repository now includes a **production-style DDR AI system** with:
- deterministic extraction and rule engines,
- audit logging in SQLite,
- JSON + PDF exports,
- a modern web UI for upload, processing trace, and report history.

## Architecture

```
Frontend (web/)      ->  app/main.py HTTP API
                        ->  Pipeline modules in app/core/
                        ->  Audit DB in output/ddr_audit.db
                        ->  Report artifacts in output/history/
```

Core pipeline stages:
1. `extractor.py` – converts inspection/thermal docs into structured observations.
2. `validator.py` – rejects empty/invalid observations.
3. `deduplicator.py` – merges near-duplicate findings (Jaccard threshold).
4. `conflict_engine.py` – contradiction checks (e.g., no-damage vs hotspot).
5. `severity_engine.py` – rule-based severity (no LLM guessing).
6. `root_cause_engine.py` – explicit root-cause statement extraction.
7. `report_builder.py` – assembles final DDR schema + confidence scores.

## Run web app

```bash
python3 app/main.py
```

Open: `http://localhost:8010`

## API endpoints

- `POST /api/upload` (multipart fields: `inspection`, `thermal`)
- `GET /api/history`
- `GET /api/report?id=<report_id>`
- `GET /api/download/json?id=<report_id>`
- `GET /api/download/pdf?id=<report_id>`

## CLI report generation (legacy path still supported)

```bash
python3 src/ddr_builder.py \
  --inspection examples/inspection_report_sample.txt \
  --thermal examples/thermal_report_sample.txt \
  --out output/main_ddr.md \
  --json output/main_ddr.json \
  --out-pdf output/main_ddr.pdf
```

## Tests

```bash
pytest -q
```
