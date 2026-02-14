# Applied AI Builder: DDR Report Generation

This repository provides a **working AI workflow** that converts raw technical inputs into a structured **Main DDR (Detailed Diagnostic Report)**.

## Will it work with any file they provide?
**Practical answer:** it works reliably for common report formats and gives best-effort parsing for unknown ones.

### Supported input formats
- `.txt`, `.md`, `.log`
- `.json`
- `.csv`, `.tsv`
- `.docx` (native XML extraction, no external package required)
- `.pdf` (best-effort text extraction for text-based PDFs)

### Important limitation
- Scanned/image-only PDFs (no embedded text) cannot be perfectly parsed without OCR.
- For missing or unreadable data, output explicitly marks fields as **Not Available** (as required).

## What this solves
The pipeline is designed for imperfect real-world reports:
- extracts usable observations from both documents
- merges overlapping points and de-duplicates repeated findings
- flags conflicting data (e.g., large thermal variance in same area)
- explicitly marks missing items as **Not Available**
- outputs a client-friendly report with a fixed structure

## DDR output structure
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

## Run
```bash
python3 src/ddr_builder.py \
  --inspection examples/inspection_report_sample.txt \
  --thermal examples/thermal_report_sample.txt \
  --out output/main_ddr.md \
  --json output/main_ddr.json
```

## Deliverables in this repo
- Workflow implementation: `src/ddr_builder.py`
- Sample raw input docs: `examples/*.txt`
- Generated DDR output: `output/main_ddr.md`, `output/main_ddr.json`
- Basic tests: `tests/test_ddr_builder.py`
