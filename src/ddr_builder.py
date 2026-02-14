#!/usr/bin/env python3
"""DDR report generator from inspection + thermal reports.

Design goals:
- deterministic and auditable extraction (no hidden hallucinations)
- conflict and missing-data handling
- reusable for similarly structured technical reports
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple


SECTION_NAMES = [
    "Property Issue Summary",
    "Area-wise Observations",
    "Probable Root Cause",
    "Severity Assessment",
    "Recommended Actions",
    "Additional Notes",
    "Missing or Unclear Information",
]

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

CAUSE_HINTS = [
    "likely due to",
    "possible cause",
    "caused by",
    "because",
    "root cause",
    "source",
]

ACTION_HINTS = [
    "recommend",
    "repair",
    "replace",
    "seal",
    "rectify",
    "monitor",
    "inspection advised",
    "clean",
    "retest",
]

SEVERITY_SCORES = {
    "critical": 4,
    "high": 3,
    "moderate": 2,
    "low": 1,
}


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


def normalize_line(line: str) -> str:
    line = line.strip(" -•\t")
    line = re.sub(r"\s+", " ", line)
    return line.strip()


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
    if any(k in lowered for k in ACTION_HINTS):
        tags.append("action")
    if re.match(r"^(recommend|action|next step)\b", lowered):
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
        area = detect_area(line)
        tags = tag_line(line)
        findings.append(Finding(source=source_name, raw_line=line, area=area, tags=tags))
    return findings


def dedupe_lines(lines: List[str]) -> List[str]:
    seen = set()
    output = []
    for line in lines:
        key = re.sub(r"\W+", "", line.lower())
        if key and key not in seen:
            seen.add(key)
            output.append(line)
    return output


def find_conflicts(findings: List[Finding]) -> List[str]:
    conflicts = []
    by_area: Dict[str, List[Finding]] = {}
    for f in findings:
        by_area.setdefault(f.area, []).append(f)

    for area, area_findings in by_area.items():
        temps = []
        for f in area_findings:
            temps.extend(extract_temperature(f.raw_line))
        if len(temps) >= 2:
            spread = max(temps) - min(temps)
            if spread >= 15:
                conflicts.append(
                    f"Temperature readings for {area} vary significantly ({min(temps):.1f}°C to {max(temps):.1f}°C)."
                )
    return conflicts


def severity_from_findings(findings: List[Finding]) -> Tuple[str, str]:
    score = 1
    rationale = []
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

    label = {v: k.title() for k, v in SEVERITY_SCORES.items()}.get(score, "Low")
    reason = "; ".join(rationale) if rationale else "limited evidence of damage in source documents"
    return label, reason


def build_ddr(inspection_text: str, thermal_text: str) -> DDR:
    findings = parse_document(inspection_text, "Inspection Report") + parse_document(
        thermal_text, "Thermal Report"
    )

    area_map: Dict[str, List[str]] = {}
    issue_summary = []
    root_causes = []
    actions = []
    notes = []
    missing = []

    for f in findings:
        area_map.setdefault(f.area, []).append(f"[{f.source}] {f.raw_line}")
        text = f.raw_line
        if "issue" in f.tags:
            issue_summary.append(text)
        if "cause" in f.tags:
            root_causes.append(text)
        if "action" in f.tags:
            actions.append(text)
        if "thermal" in f.tags:
            notes.append(f"Thermal input captured: {text}")

    conflicts = find_conflicts(findings)
    notes.extend([f"Conflict noted: {c}" for c in conflicts])

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
        area_wise_observations={
            area: dedupe_lines(lines) for area, lines in sorted(area_map.items())
        }
        or {"General": ["Not Available"]},
        probable_root_cause=dedupe_lines(root_causes) or ["Not Available"],
        severity_assessment={"level": severity_label, "reasoning": severity_reason},
        recommended_actions=dedupe_lines(actions) or ["Not Available"],
        additional_notes=dedupe_lines(notes) or ["Not Available"],
        missing_or_unclear_information=dedupe_lines(missing) or ["Not Available"],
    )


def render_markdown(ddr: DDR) -> str:
    lines: List[str] = ["# Main DDR (Detailed Diagnostic Report)", ""]
    lines.append("## 1. Property Issue Summary")
    for item in ddr.property_issue_summary:
        lines.append(f"- {item}")

    lines.append("\n## 2. Area-wise Observations")
    for area, items in ddr.area_wise_observations.items():
        lines.append(f"### {area}")
        for item in items:
            lines.append(f"- {item}")

    lines.append("\n## 3. Probable Root Cause")
    for item in ddr.probable_root_cause:
        lines.append(f"- {item}")

    lines.append("\n## 4. Severity Assessment (with reasoning)")
    lines.append(f"- Severity Level: {ddr.severity_assessment['level']}")
    lines.append(f"- Reasoning: {ddr.severity_assessment['reasoning']}")

    lines.append("\n## 5. Recommended Actions")
    for item in ddr.recommended_actions:
        lines.append(f"- {item}")

    lines.append("\n## 6. Additional Notes")
    for item in ddr.additional_notes:
        lines.append(f"- {item}")

    lines.append("\n## 7. Missing or Unclear Information")
    for item in ddr.missing_or_unclear_information:
        lines.append(f"- {item}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DDR from inspection and thermal reports")
    parser.add_argument("--inspection", required=True, help="Path to inspection report text file")
    parser.add_argument("--thermal", required=True, help="Path to thermal report text file")
    parser.add_argument("--out", required=True, help="Output markdown file")
    parser.add_argument("--json", dest="json_out", help="Optional output JSON path")
    args = parser.parse_args()

    inspection_text = Path(args.inspection).read_text(encoding="utf-8")
    thermal_text = Path(args.thermal).read_text(encoding="utf-8")

    ddr = build_ddr(inspection_text, thermal_text)
    markdown = render_markdown(ddr)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(asdict(ddr), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
