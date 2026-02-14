# Applied AI Builder: DDR Report Generation

This repository provides a **working AI workflow** that converts two raw technical inputs:
- inspection observations
- thermal scan findings

into a structured **Main DDR (Detailed Diagnostic Report)**.

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
  --json output/main_ddr.json
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
