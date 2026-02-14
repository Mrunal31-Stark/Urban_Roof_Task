#!/usr/bin/env python3
"""DDR report generator from inspection + thermal reports.

Features:
- deterministic and auditable extraction (no hidden hallucinations)
- conflict and missing-data handling
- multi-format ingestion (with optional OCR for image-heavy PDFs)
- markdown/json output + built-in PDF report rendering
Design goals:
- deterministic and auditable extraction (no hidden hallucinations)
- conflict and missing-data handling
- reusable for similarly structured technical reports
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass
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

CAUSE_HINTS = ["likely due to", "possible cause", "caused by", "because", "root cause", "source"]
ACTION_HINTS = ["recommend", "repair", "replace", "seal", "rectify", "monitor", "clean", "retest"]
SEVERITY_SCORES = {"critical": 4, "high": 3, "moderate": 2, "low": 1}

ACTION_HINTS = ["recommend", "repair", "replace", "seal", "rectify", "monitor", "clean", "retest"]

SEVERITY_SCORES = {"critical": 4, "high": 3, "moderate": 2, "low": 1}
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


def _module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


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
    return re.sub(r"<[^>]+>", "", xml)


def _ocr_image_bytes(image_bytes: bytes) -> str:
    """OCR for image bytes when optional deps are available."""
    if not (_module_exists("PIL") and _module_exists("pytesseract")):
        return ""

    from PIL import Image  # type: ignore
    import pytesseract  # type: ignore
    import io

    try:
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image) or ""
    except Exception:
        return ""


def _read_pdf_best_effort(path: Path) -> Tuple[str, List[str]]:
    """Return text and ingestion notes.

    Strategy order:
    1) pypdf text extraction if available.
    2) fitz text extraction + optional OCR on embedded images.
    3) raw regex fallback from PDF bytes (limited reliability).
    """
    notes: List[str] = []

    if _module_exists("pypdf"):
        import pypdf  # type: ignore

        text_chunks = []
        with path.open("rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text_chunks.append(page.extract_text() or "")
        text = "\n".join(text_chunks).strip()
        if text:
            notes.append("PDF parsed using pypdf text extraction.")
            return text, notes

    if _module_exists("fitz"):
        import fitz  # type: ignore

        doc = fitz.open(path)
        text_chunks = []
        ocr_chunks = []
        for page in doc:
            text_chunks.append(page.get_text("text") or "")
            for image_info in page.get_images(full=True):
                xref = image_info[0]
                image_data = doc.extract_image(xref)
                if image_data and "image" in image_data:
                    ocr_text = _ocr_image_bytes(image_data["image"])
                    if ocr_text.strip():
                        ocr_chunks.append(ocr_text)
        doc.close()

        all_text = "\n".join(text_chunks + ocr_chunks).strip()
        if all_text:
            notes.append("PDF parsed using fitz; OCR applied on embedded images when available.")
            return all_text, notes

    raw = path.read_bytes().decode("latin-1", errors="ignore")
    candidates = re.findall(r"\(([^\)]{8,})\)", raw)
    fallback_text = "\n".join(candidates).strip()
    notes.append(
        "PDF parsed in fallback mode. If the file is image-only/scanned, install OCR stack (pytesseract + Pillow + fitz) for better extraction."
    )
    return fallback_text, notes


def _read_image_best_effort(path: Path) -> Tuple[str, List[str]]:
    notes: List[str] = []
    if _module_exists("PIL") and _module_exists("pytesseract"):
        text = _ocr_image_bytes(path.read_bytes())
        if text.strip():
            notes.append("Image OCR completed using pytesseract.")
            return text, notes
    notes.append("Image OCR unavailable (missing optional dependencies).")
    return "", notes


def load_document(path_str: str) -> Tuple[str, List[str]]:
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
        return _read_text(path), []
    if suffix == ".json":
        return _read_json(path), []
    if suffix in {".csv", ".tsv"}:
        return _read_csv(path), []
    if suffix == ".docx":
        return _read_docx(path), []
    if suffix == ".pdf":
        return _read_pdf_best_effort(path)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        return _read_image_best_effort(path)

    return path.read_bytes().decode("utf-8", errors="ignore"), ["Unknown file extension: applied best-effort text decode."]


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip(" -•\t")).strip()
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
    if any(k in lowered for k in ACTION_HINTS) or re.match(r"^(recommend|action|next step)\b", lowered):
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
        findings.append(Finding(source=source_name, raw_line=line, area=detect_area(line), tags=tag_line(line)))
        area = detect_area(line)
        tags = tag_line(line)
        findings.append(Finding(source=source_name, raw_line=line, area=area, tags=tags))
    return findings


def dedupe_lines(lines: List[str]) -> List[str]:
    seen, output = set(), []
    seen = set()
    output = []
    for line in lines:
        key = re.sub(r"\W+", "", line.lower())
        if key and key not in seen:
            seen.add(key)
            output.append(line)
    return output


def find_conflicts(findings: List[Finding]) -> List[str]:
    conflicts, by_area = [], {}
    for finding in findings:
        by_area.setdefault(finding.area, []).append(finding)

    for area, area_findings in by_area.items():
        temps: List[float] = []
        for finding in area_findings:
            temps.extend(extract_temperature(finding.raw_line))
        if len(temps) >= 2 and (max(temps) - min(temps)) >= 15:
            conflicts.append(f"Temperature readings for {area} vary significantly ({min(temps):.1f}°C to {max(temps):.1f}°C).")
    conflicts = []
    by_area: Dict[str, List[Finding]] = {}
    for f in findings:
        by_area.setdefault(f.area, []).append(f)

    for area, area_findings in by_area.items():
        temps: List[float] = []
        for f in area_findings:
            temps.extend(extract_temperature(f.raw_line))
        if len(temps) >= 2 and (max(temps) - min(temps)) >= 15:
            conflicts.append(f"Temperature readings for {area} vary significantly ({min(temps):.1f}°C to {max(temps):.1f}°C).")
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
    rationale: List[str] = []
    all_text = " ".join(f.raw_line.lower() for f in findings)

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

    label = {v: k.title() for k, v in SEVERITY_SCORES.items()}[score]
    reason = "; ".join(rationale) if rationale else "limited evidence of damage in source documents"
    return label, reason


def build_ddr(inspection_text: str, thermal_text: str, ingestion_notes: List[str] | None = None) -> DDR:
    return label, ("; ".join(rationale) if rationale else "limited evidence of damage in source documents")


def build_ddr(inspection_text: str, thermal_text: str) -> DDR:
    findings = parse_document(inspection_text, "Inspection Report") + parse_document(thermal_text, "Thermal Report")

    area_map: Dict[str, List[str]] = {}
    issue_summary: List[str] = []
    root_causes: List[str] = []
    actions: List[str] = []
    notes: List[str] = ingestion_notes[:] if ingestion_notes else []
    missing: List[str] = []

    for finding in findings:
        area_map.setdefault(finding.area, []).append(f"[{finding.source}] {finding.raw_line}")
        if "issue" in finding.tags:
            issue_summary.append(finding.raw_line)
        if "cause" in finding.tags:
            root_causes.append(finding.raw_line)
        if "action" in finding.tags:
            actions.append(finding.raw_line)
        if "thermal" in finding.tags:
            notes.append(f"Thermal input captured: {finding.raw_line}")

    notes.extend([f"Conflict noted: {item}" for item in find_conflicts(findings)])
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
        area_wise_observations={area: dedupe_lines(items) for area, items in sorted(area_map.items())}
        area_wise_observations={a: dedupe_lines(v) for a, v in sorted(area_map.items())} or {"General": ["Not Available"]},
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
    lines.extend(f"- {item}" for item in ddr.property_issue_summary)
    lines.extend(f"- {x}" for x in ddr.property_issue_summary)
    for item in ddr.property_issue_summary:
        lines.append(f"- {item}")

    lines.append("\n## 2. Area-wise Observations")
    for area, items in ddr.area_wise_observations.items():
        lines.append(f"### {area}")
        lines.extend(f"- {item}" for item in items)

    lines.append("\n## 3. Probable Root Cause")
    lines.extend(f"- {item}" for item in ddr.probable_root_cause)
        lines.extend(f"- {x}" for x in items)

    lines.append("\n## 3. Probable Root Cause")
    lines.extend(f"- {x}" for x in ddr.probable_root_cause)
        for item in items:
            lines.append(f"- {item}")

    lines.append("\n## 3. Probable Root Cause")
    for item in ddr.probable_root_cause:
        lines.append(f"- {item}")

    lines.append("\n## 4. Severity Assessment (with reasoning)")
    lines.append(f"- Severity Level: {ddr.severity_assessment['level']}")
    lines.append(f"- Reasoning: {ddr.severity_assessment['reasoning']}")

    lines.append("\n## 5. Recommended Actions")
    lines.extend(f"- {item}" for item in ddr.recommended_actions)

    lines.append("\n## 6. Additional Notes")
    lines.extend(f"- {item}" for item in ddr.additional_notes)

    lines.append("\n## 7. Missing or Unclear Information")
    lines.extend(f"- {item}" for item in ddr.missing_or_unclear_information)
    return "\n".join(lines) + "\n"


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_simple_pdf(text: str, output_path: Path) -> None:
    """Write a simple single-font PDF from plain text without external dependencies."""
    lines = text.splitlines() or [""]
    page_width, page_height = 595, 842  # A4 points
    margin, line_height = 50, 14
    max_lines = max(1, (page_height - 2 * margin) // line_height)

    pages: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if len(current) >= max_lines:
            pages.append(current)
            current = []
        current.append(line[:140])
    if current:
        pages.append(current)

    objects: List[bytes] = []

    def add_object(payload: str) -> int:
        objects.append(payload.encode("latin-1", errors="ignore"))
        return len(objects)

    font_obj = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_obj_ids = []
    content_obj_ids = []
    for page_lines in pages:
        stream_lines = ["BT", "/F1 10 Tf", f"1 0 0 1 {margin} {page_height - margin} Tm", f"0 -{line_height} Td"]
        for line in page_lines:
            stream_lines.append(f"({_pdf_escape(line)}) Tj")
            stream_lines.append(f"0 -{line_height} Td")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines)
        content_obj = add_object(f"<< /Length {len(stream.encode('latin-1', errors='ignore'))} >>\nstream\n{stream}\nendstream")
        content_obj_ids.append(content_obj)
        page_obj = add_object("PENDING_PAGE")
        page_obj_ids.append(page_obj)

    kids_refs = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    pages_obj = add_object(f"<< /Type /Pages /Count {len(page_obj_ids)} /Kids [ {kids_refs} ] >>")

    for i, page_obj_id in enumerate(page_obj_ids):
        page_dict = (
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_obj_ids[i]} 0 R >>"
        )
        objects[page_obj_id - 1] = page_dict.encode("latin-1")

    catalog_obj = add_object(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("latin-1"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_obj} 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("latin-1")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf)
    lines.extend(f"- {x}" for x in ddr.recommended_actions)

    lines.append("\n## 6. Additional Notes")
    lines.extend(f"- {x}" for x in ddr.additional_notes)

    lines.append("\n## 7. Missing or Unclear Information")
    lines.extend(f"- {x}" for x in ddr.missing_or_unclear_information)
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
    parser.add_argument("--inspection", required=True, help="Path to inspection report")
    parser.add_argument("--thermal", required=True, help="Path to thermal report")
    parser.add_argument("--out", required=True, help="Output markdown path")
    parser.add_argument("--json", dest="json_out", help="Optional output JSON path")
    parser.add_argument("--out-pdf", dest="pdf_out", help="Optional output PDF path")
    args = parser.parse_args()

    inspection_text, inspection_notes = load_document(args.inspection)
    thermal_text, thermal_notes = load_document(args.thermal)
    ddr = build_ddr(inspection_text, thermal_text, ingestion_notes=inspection_notes + thermal_notes)

    markdown = render_markdown(ddr)
    parser.add_argument("--inspection", required=True, help="Path to inspection report file (txt/json/csv/docx/pdf)")
    parser.add_argument("--thermal", required=True, help="Path to thermal report file (txt/json/csv/docx/pdf)")
    parser.add_argument("--inspection", required=True, help="Path to inspection report text file")
    parser.add_argument("--thermal", required=True, help="Path to thermal report text file")
    parser.add_argument("--out", required=True, help="Output markdown file")
    parser.add_argument("--json", dest="json_out", help="Optional output JSON path")
    args = parser.parse_args()

    inspection_text = load_document(args.inspection)
    thermal_text = load_document(args.thermal)

    ddr = build_ddr(inspection_text, thermal_text)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(render_markdown(ddr), encoding="utf-8")
    inspection_text = Path(args.inspection).read_text(encoding="utf-8")
    thermal_text = Path(args.thermal).read_text(encoding="utf-8")

    ddr = build_ddr(inspection_text, thermal_text)
    markdown = render_markdown(ddr)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(asdict(ddr), indent=2), encoding="utf-8")
    if args.pdf_out:
        render_simple_pdf(markdown, Path(args.pdf_out))


if __name__ == "__main__":
    main()
