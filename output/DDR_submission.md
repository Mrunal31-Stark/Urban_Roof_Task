# Applied AI Builder Submission

## Working output
- DDR markdown: `output/main_ddr.md`
- DDR JSON: `output/main_ddr.json`
- DDR PDF: `output/main_ddr.pdf`

## How to run
```bash
python3 src/ddr_builder.py \
  --inspection <inspection_file> \
  --thermal <thermal_file> \
  --out output/main_ddr.md \
  --json output/main_ddr.json \
  --out-pdf output/main_ddr.pdf
```

## Input compatibility
Supported: `.txt`, `.md`, `.log`, `.json`, `.csv`, `.tsv`, `.docx`, `.pdf`, and image files.

For image-heavy/scanned PDFs, OCR is used only when optional dependencies are available. Otherwise fallback parsing is used and limitations are documented in report notes.

## Generalization
The workflow is reusable across similar inspection + thermal documents because it:
- normalizes noisy content
- identifies issue/cause/action/thermal signals
- merges area observations across documents
- de-duplicates repeated statements
- flags conflicts and missing information
