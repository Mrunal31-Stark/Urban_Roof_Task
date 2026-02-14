# Applied AI Builder: DDR Report Generation

This repository provides a working AI workflow that converts raw inspection + thermal evidence into a structured **Main DDR (Detailed Diagnostic Report)**.

## Does it work with all files, including PDF with thermal images?
**Direct answer:**
- It now supports most common report formats and generates structured output in **Markdown, JSON, and PDF**.
- PDF output uses proper styled rendering with **colored headings/subheadings** (not raw markdown-style text dump).
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

## Run
```bash
python3 src/ddr_builder.py \
  --inspection examples/inspection_report_sample.txt \
  --thermal examples/thermal_report_sample.txt \
  --out output/main_ddr.md \
  --json output/main_ddr.json \
  --out-pdf output/main_ddr.pdf \
  --images examples/thermal_1.jpg examples/thermal_2.jpg
```

## Deliverables in this repo
- Workflow implementation: `src/ddr_builder.py`
- Sample raw input docs: `examples/*.txt`
- Generated outputs: `output/main_ddr.md`, `output/main_ddr.json`, `output/main_ddr.pdf`
- Basic tests: `tests/test_ddr_builder.py`


### Optional image pages in PDF
Use `--images` to append inspection/thermal photos to the PDF report. If Pillow is installed, images are embedded as appendix pages; otherwise, caption placeholders are added.


## Minimal UI (Upload -> View -> Download PDF)
A minimal web UI is available so users can:
1. Upload **Inspection** file
2. Upload **Thermal** file
3. View generated report directly in browser
4. Download final report as PDF

Run UI:
```bash
python3 src/ui_app.py
```
Then open `http://localhost:8000`.
