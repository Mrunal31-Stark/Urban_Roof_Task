# Applied AI Builder: DDR Report Generation

This repository provides a working AI workflow that converts raw inspection + thermal evidence into a structured **Main DDR (Detailed Diagnostic Report)**.

## Does it work with all files, including PDF with thermal images?
**Direct answer:**
- It now supports most common report formats and generates structured output in **Markdown, JSON, and PDF**.
- For **PDFs that contain images/scans**, extraction quality depends on OCR availability.

### Supported inputs
- `.txt`, `.md`, `.log`
- `.json`
- `.csv`, `.tsv`
- `.docx`
- `.pdf` (text extraction + optional OCR path)
- image files (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`) via optional OCR

### PDF + thermal image handling
- If optional libraries are present (`fitz` + `Pillow` + `pytesseract`), embedded image OCR is used.
- If those libraries are missing, parser runs in fallback mode and records this limitation in **Additional Notes**.
- Missing/unreadable info is explicitly reported as `Not Available`.

## DDR output sections
1. Property Issue Summary
2. Area-wise Observations
3. Probable Root Cause
4. Severity Assessment (with reasoning)
5. Recommended Actions
6. Additional Notes
7. Missing or Unclear Information

## Solution design
`src/ddr_builder.py` implements a deterministic workflow:
1. **Document loading**: multi-format input handling with graceful best-effort fallback.
2. **Document parsing**: line normalization + tagging (`issue`, `cause`, `action`, `thermal`, `observation`).
3. **Area detection**: maps lines to likely property zones.
4. **Signal fusion**: combines findings from both documents by area.
5. **Conflict detection**: checks per-area temperature spread.
6. **Severity scoring**: derives Low/Moderate/High/Critical with plain-language reasoning.
7. **Output rendering**: exports markdown report (+ optional JSON).
1. **Document parsing**: line-based normalization + tagging (`issue`, `cause`, `action`, `thermal`, `observation`)
2. **Area detection**: maps lines to likely property zones (Roof, Ceiling, Bathroom, etc.)
3. **Signal fusion**: combines findings from both documents by area
4. **Conflict detection**: checks per-area temperature spread and reports likely conflict
5. **Severity scoring**: derives Low/Moderate/High/Critical with plain-language reasoning
6. **Output rendering**: exports markdown report (+ optional JSON)

## Run
```bash
python3 src/ddr_builder.py \
  --inspection examples/inspection_report_sample.txt \
  --thermal examples/thermal_report_sample.txt \
  --out output/main_ddr.md \
  --json output/main_ddr.json \
  --out-pdf output/main_ddr.pdf
```

## Deliverables in this repo
- Workflow implementation: `src/ddr_builder.py`
- Sample raw input docs: `examples/*.txt`
- Generated DDR output: `output/main_ddr.md`, `output/main_ddr.json`
- Basic tests: `tests/test_ddr_builder.py`

## Notes on extensibility
- Current parser is rule-based for reliability and traceability.
- It can be upgraded with an LLM extraction stage while keeping the same schema.
- The command interface and DDR schema are reusable for similar inspection domains.
