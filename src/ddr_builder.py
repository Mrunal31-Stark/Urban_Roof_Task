#!/usr/bin/env python3
"""DDR report generator from inspection + thermal reports.

Design goals:
- deterministic and auditable extraction (no hidden hallucinations)
- conflict and missing-data handling
- reusable for similarly structured technical reports
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple


AREA_HINTS = [
    "roof",
    "terrace",
    "ceiling",
    "wall",
    "bathroom",
    "kitchen",
    "bedroom",
    "living",
    "balcony",
    "drain",
    "parapet",
    "water tank",
    "staircase",
]

ISSUE_KEYWORDS = [
    "leak",
    "damp",
    "crack",
    "seepage",
    "stain",
    "fungus",
    "mold",
    "moisture",
    "corrosion",
    "rust",
    "delamination",
    "blister",
]

CAUSE_HINTS = ["likely due to", "possible cause", "caused by", "because", "root cause", "source"]

ACTION_HINTS = ["recommend", "repair", "replace", "seal", "rectify", "monitor", "clean", "retest"]

SEVERITY_SCORES = {"critical": 4, "high": 3, "moderate": 2, "low": 1}


@dataclass
class Finding:
    source: str
    raw_line: str
    area: str
    tags: List[str]


@dataclass
class DDR:
    property_issue_summary: List[str]
    area_wise_observations: Dict[str, List[str]]
    probable_root_cause: List[str]
    severity_assessment: Dict[str, str]
    recommended_actions: List[str]
    additional_notes: List[str]
    missing_or_unclear_information: List[str]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_json(path: Path) -> str:
    data = json.loads(_read_text(path))
    return json.dumps(data, indent=2)


def _read_csv(path: Path) -> str:
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        for row in csv.reader(f):
            if any(cell.strip() for cell in row):
                rows.append(" | ".join(cell.strip() for cell in row if cell.strip()))
    return "\n".join(rows)


def _read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return xml


def _read_pdf_best_effort(path: Path) -> str:
    data = path.read_bytes().decode("latin-1", errors="ignore")
    # Best-effort extraction; works for many text-based PDFs, not scanned images.
    candidates = re.findall(r"\(([^\)]{8,})\)", data)
    return "\n".join(candidates)


def load_document(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".log"}:
        return _read_text(path)
    if suffix == ".json":
        return _read_json(path)
    if suffix in {".csv", ".tsv"}:
        return _read_csv(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".pdf":
        return _read_pdf_best_effort(path)

    # Unknown format: attempt text decode so user files still get a best-effort pass.
    return path.read_bytes().decode("utf-8", errors="ignore")


def normalize_line(line: str) -> str:
    line = line.strip(" -•\t")
    return re.sub(r"\s+", " ", line).strip()


def detect_area(text: str) -> str:
    lowered = text.lower()
    for hint in AREA_HINTS:
        if hint in lowered:
            return hint.title()
    return "General"


def extract_temperature(text: str) -> List[float]:
    matches = re.findall(r"(-?\d+(?:\.\d+)?)\s*(?:°\s*c|deg\s*c|celsius|\bc\b)", text.lower())
    return [float(m) for m in matches]


def tag_line(text: str) -> List[str]:
    lowered = text.lower()
    tags = []
    negated_issue = re.search(r"\bno\b.{0,20}\b(crack|leak|seepage|damp)\b", lowered)
    if any(k in lowered for k in ISSUE_KEYWORDS) and not negated_issue and not lowered.startswith("recommend"):
        tags.append("issue")
    if any(k in lowered for k in CAUSE_HINTS):
        tags.append("cause")
    if any(k in lowered for k in ACTION_HINTS) or re.match(r"^(recommend|action|next step)\b", lowered):
        tags.append("action")
    if extract_temperature(text):
        tags.append("thermal")
    return tags or ["observation"]


def parse_document(content: str, source_name: str) -> List[Finding]:
    findings: List[Finding] = []
    for raw in content.splitlines():
        line = normalize_line(raw)
        if len(line) < 8:
            continue
        if re.match(r"^(inspection date|thermal scan date|property)\b", line.lower()):
            continue
        findings.append(Finding(source=source_name, raw_line=line, area=detect_area(line), tags=tag_line(line)))
    return findings


def dedupe_lines(lines: List[str]) -> List[str]:
    seen, output = set(), []
    for line in lines:
        key = re.sub(r"\W+", "", line.lower())
        if key and key not in seen:
            seen.add(key)
            output.append(line)
    return output


def find_conflicts(findings: List[Finding]) -> List[str]:
    conflicts, by_area = [], {}
    for f in findings:
        by_area.setdefault(f.area, []).append(f)

    for area, area_findings in by_area.items():
        temps: List[float] = []
        for f in area_findings:
            temps.extend(extract_temperature(f.raw_line))
        if len(temps) >= 2 and (max(temps) - min(temps)) >= 15:
            conflicts.append(f"Temperature readings for {area} vary significantly ({min(temps):.1f}°C to {max(temps):.1f}°C).")
    return conflicts


def severity_from_findings(findings: List[Finding]) -> Tuple[str, str]:
    score = 1
    rationale: List[str] = []
    all_text = " ".join(f.raw_line.lower() for f in findings)

    if any(word in all_text for word in ["active leak", "major crack", "electrical hazard", "unsafe"]):
        score = max(score, 4)
        rationale.append("critical safety/structural indicators were detected")
    if "structural crack" in all_text and "no structural crack" not in all_text:
        score = max(score, 4)
        rationale.append("possible structural crack indicators were detected")
    if any(word in all_text for word in ["leak", "seepage", "heavy damp", "saturation"]):
        score = max(score, 3)
        rationale.append("water ingress indicators are present")
    if any(word in all_text for word in ["damp", "stain", "fungus", "mold", "thermal anomaly"]):
        score = max(score, 2)
        rationale.append("moisture/thermal anomalies were identified")

    label = {v: k.title() for k, v in SEVERITY_SCORES.items()}[score]
    return label, ("; ".join(rationale) if rationale else "limited evidence of damage in source documents")


def build_ddr(inspection_text: str, thermal_text: str) -> DDR:
    findings = parse_document(inspection_text, "Inspection Report") + parse_document(thermal_text, "Thermal Report")

    area_map: Dict[str, List[str]] = {}
    issue_summary: List[str] = []
    root_causes: List[str] = []
    actions: List[str] = []
    notes: List[str] = []
    missing: List[str] = []

    for f in findings:
        area_map.setdefault(f.area, []).append(f"[{f.source}] {f.raw_line}")
        if "issue" in f.tags:
            issue_summary.append(f.raw_line)
        if "cause" in f.tags:
            root_causes.append(f.raw_line)
        if "action" in f.tags:
            actions.append(f.raw_line)
        if "thermal" in f.tags:
            notes.append(f"Thermal input captured: {f.raw_line}")

    notes.extend([f"Conflict noted: {c}" for c in find_conflicts(findings)])

    if not issue_summary:
        missing.append("Issue descriptions: Not Available")
    if not root_causes:
        missing.append("Probable root cause statements: Not Available")
    if not actions:
        missing.append("Recommended actions in source docs: Not Available")
    if not area_map:
        missing.append("Area-level observations: Not Available")

    severity_label, severity_reason = severity_from_findings(findings)

    return DDR(
        property_issue_summary=dedupe_lines(issue_summary) or ["Not Available"],
        area_wise_observations={a: dedupe_lines(v) for a, v in sorted(area_map.items())} or {"General": ["Not Available"]},
        probable_root_cause=dedupe_lines(root_causes) or ["Not Available"],
        severity_assessment={"level": severity_label, "reasoning": severity_reason},
        recommended_actions=dedupe_lines(actions) or ["Not Available"],
        additional_notes=dedupe_lines(notes) or ["Not Available"],
        missing_or_unclear_information=dedupe_lines(missing) or ["Not Available"],
    )


def render_markdown(ddr: DDR) -> str:
    lines: List[str] = ["# Main DDR (Detailed Diagnostic Report)", ""]
    lines.append("## 1. Property Issue Summary")
    lines.extend(f"- {x}" for x in ddr.property_issue_summary)

    lines.append("\n## 2. Area-wise Observations")
    for area, items in ddr.area_wise_observations.items():
        lines.append(f"### {area}")
        lines.extend(f"- {x}" for x in items)

    lines.append("\n## 3. Probable Root Cause")
    lines.extend(f"- {x}" for x in ddr.probable_root_cause)

    lines.append("\n## 4. Severity Assessment (with reasoning)")
    lines.append(f"- Severity Level: {ddr.severity_assessment['level']}")
    lines.append(f"- Reasoning: {ddr.severity_assessment['reasoning']}")

    lines.append("\n## 5. Recommended Actions")
    lines.extend(f"- {x}" for x in ddr.recommended_actions)

    lines.append("\n## 6. Additional Notes")
    lines.extend(f"- {x}" for x in ddr.additional_notes)

    lines.append("\n## 7. Missing or Unclear Information")
    lines.extend(f"- {x}" for x in ddr.missing_or_unclear_information)
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DDR from inspection and thermal reports")
    parser.add_argument("--inspection", required=True, help="Path to inspection report file (txt/json/csv/docx/pdf)")
    parser.add_argument("--thermal", required=True, help="Path to thermal report file (txt/json/csv/docx/pdf)")
    parser.add_argument("--out", required=True, help="Output markdown file")
    parser.add_argument("--json", dest="json_out", help="Optional output JSON path")
    args = parser.parse_args()

    inspection_text = load_document(args.inspection)
    thermal_text = load_document(args.thermal)

    ddr = build_ddr(inspection_text, thermal_text)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(render_markdown(ddr), encoding="utf-8")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(asdict(ddr), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
