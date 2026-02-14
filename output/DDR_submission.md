# Applied AI Builder Submission

## Working output
- Generated DDR markdown: `output/main_ddr.md`
- Generated DDR JSON: `output/main_ddr.json`

## How to run
```bash
python3 src/ddr_builder.py \
  --inspection examples/inspection_report_sample.txt \
  --thermal examples/thermal_report_sample.txt \
  --out output/main_ddr.md \
  --json output/main_ddr.json
```

## Generalization
The workflow is reusable across similar inspection + thermal documents because it:
- normalizes noisy line-by-line content
- identifies issue/cause/action/thermal signals
- merges area observations across documents
- de-duplicates repeated statements
- flags conflicts and missing information
