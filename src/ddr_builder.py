#!/usr/bin/env python3
"""Deterministic DDR report generator for inspection + thermal evidence."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

AREA_HINTS = [
    "electrical panel",
    "roof",
    "terrace",
    "basement",
    "ceiling",
    "wall",
    "bathroom",
    "kitchen",
    "bedroom",
    "living",
    "balcony",
    "drain",
    "hvac",
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
    "hotspot",
    "overheat",
]

CAUSE_HINTS = ["likely due to", "possible cause", "caused by", "because", "root cause", "source"]
ACTION_HINTS = ["recommend", "repair", "replace", "seal", "rectify", "monitor", "inspect", "retest"]


@dataclass
class Finding:
    source: str
    raw_line: str
    area: str
    issue: str
    tags: List[str]
    temperatures_c: List[float]


@dataclass
class DDR:
    property_issue_summary: List[str]
    area_wise_observations: Dict[str, List[str]]
    probable_root_cause: List[str]
    severity_assessment: Dict[str, str]
    recommended_actions: List[str]
    additional_notes: List[str]
    missing_or_unclear_information: List[str]
    conflicts_detected: List[str]


def _module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_json(path: Path) -> str:
    data = json.loads(_read_text(path))
    return json.dumps(data, indent=2)


def _read_csv(path: Path) -> str:
    rows: List[str] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
        for row in csv.reader(fh):
            clean = [cell.strip() for cell in row if cell.strip()]
            if clean:
                rows.append(" | ".join(clean))
    return "\n".join(rows)


def _read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def _ocr_image_bytes(image_bytes: bytes) -> str:
    if not (_module_exists("PIL") and _module_exists("pytesseract")):
        return ""
    from PIL import Image  # type: ignore
    import io
    import pytesseract  # type: ignore

    try:
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image) or ""
    except Exception:
        return ""


def _read_pdf_best_effort(path: Path) -> Tuple[str, List[str]]:
    notes: List[str] = []

    if _module_exists("pypdf"):
        import pypdf  # type: ignore

        chunks: List[str] = []
        with path.open("rb") as fh:
            reader = pypdf.PdfReader(fh)
            for page in reader.pages:
                chunks.append(page.extract_text() or "")
        text = "\n".join(chunks).strip()
        if text:
            notes.append("PDF parsed using pypdf text extraction.")
            return text, notes

    if _module_exists("fitz"):
        import fitz  # type: ignore

        doc = fitz.open(path)
        chunks: List[str] = []
        ocr_chunks: List[str] = []
        for page in doc:
            chunks.append(page.get_text("text") or "")
            for image_info in page.get_images(full=True):
                xref = image_info[0]
                image_data = doc.extract_image(xref)
                if image_data and "image" in image_data:
                    ocr_text = _ocr_image_bytes(image_data["image"])
                    if ocr_text.strip():
                        ocr_chunks.append(ocr_text)
        doc.close()
        text = "\n".join(chunks + ocr_chunks).strip()
        if text:
            notes.append("PDF parsed using fitz; OCR applied to embedded images when available.")
            return text, notes

    raw = path.read_bytes().decode("latin-1", errors="ignore")
    fallback = "\n".join(re.findall(r"\(([^\)]{8,})\)", raw)).strip()
    notes.append("PDF parsed in fallback mode; OCR stack recommended for scanned PDFs.")
    return fallback, notes


def _read_image_best_effort(path: Path) -> Tuple[str, List[str]]:
    if _module_exists("PIL") and _module_exists("pytesseract"):
        text = _ocr_image_bytes(path.read_bytes())
        if text.strip():
            return text, ["Image OCR completed using pytesseract."]
    return "", ["Image OCR unavailable (missing optional dependencies)."]


def load_document(path_str: str) -> Tuple[str, List[str]]:
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

    return path.read_bytes().decode("utf-8", errors="ignore"), ["Unknown extension: applied best-effort text decode."]


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip(" -•\t")).strip()


def _detect_area(text: str) -> str:
    lowered = text.lower()
    for hint in AREA_HINTS:
        if hint in lowered:
            return hint.title()
    return "General"


def _extract_temperatures(text: str) -> List[float]:
    matches = re.findall(r"(-?\d+(?:\.\d+)?)\s*(?:°\s*c|deg\s*c|celsius|\bc\b)", text.lower())
    return [float(match) for match in matches]


def _classify_issue(text: str) -> str:
    lowered = text.lower()
    for keyword in ISSUE_KEYWORDS:
        if keyword in lowered:
            return keyword
    return "observation"


def _tags(text: str) -> List[str]:
    lowered = text.lower()
    tags: List[str] = []

    negated_issue = re.search(r"\bno\b.{0,24}\b(crack|leak|seepage|damp|overheat)\b", lowered)
    if any(word in lowered for word in ISSUE_KEYWORDS) and not negated_issue:
        tags.append("issue")
    if any(word in lowered for word in CAUSE_HINTS):
        tags.append("cause")
    if any(word in lowered for word in ACTION_HINTS) or re.match(r"^(recommend|action|next step)\b", lowered):
        tags.append("action")
    if _extract_temperatures(text):
        tags.append("thermal")

    return tags or ["observation"]


def parse_document(content: str, source_name: str) -> List[Finding]:
    findings: List[Finding] = []
    for raw in content.splitlines():
        line = _normalize_line(raw)
        if len(line) < 6:
            continue
        if re.match(r"^(inspection date|thermal scan date|property)\b", line.lower()):
            continue

        findings.append(
            Finding(
                source=source_name,
                raw_line=line,
                area=_detect_area(line),
                issue=_classify_issue(line),
                tags=_tags(line),
                temperatures_c=_extract_temperatures(line),
            )
        )
    return findings


def _canonical(text: str) -> str:
    return re.sub(r"\W+", "", text.lower())


def _dedupe_lines(lines: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for line in lines:
        key = _canonical(line)
        if key and key not in seen:
            seen.add(key)
            out.append(line)
    return out


def _jaccard_similarity(a: str, b: str) -> float:
    a_words = {w for w in re.findall(r"[a-z0-9]+", a.lower()) if len(w) > 2}
    b_words = {w for w in re.findall(r"[a-z0-9]+", b.lower()) if len(w) > 2}
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)


def _merge_related_findings(findings: Sequence[Finding], similarity_threshold: float = 0.8) -> List[Finding]:
    merged: List[Finding] = []
    for finding in findings:
        merged_to_existing = False
        for idx, existing in enumerate(merged):
            if existing.area != finding.area:
                continue
            if existing.issue != finding.issue:
                continue
            sim = _jaccard_similarity(existing.raw_line, finding.raw_line)
            if sim >= similarity_threshold:
                merged[idx] = Finding(
                    source=f"{existing.source}, {finding.source}",
                    raw_line=f"{existing.raw_line} | {finding.raw_line}",
                    area=existing.area,
                    issue=existing.issue,
                    tags=sorted(set(existing.tags + finding.tags)),
                    temperatures_c=existing.temperatures_c + finding.temperatures_c,
                )
                merged_to_existing = True
                break
        if not merged_to_existing:
            merged.append(finding)
    return merged


def _find_conflicts(findings: Sequence[Finding]) -> List[str]:
    conflicts: List[str] = []
    by_area: Dict[str, List[Finding]] = {}
    for finding in findings:
        by_area.setdefault(finding.area, []).append(finding)

    for area, area_findings in by_area.items():
        temps = [temp for item in area_findings for temp in item.temperatures_c]
        if len(temps) >= 2 and (max(temps) - min(temps)) >= 15:
            conflicts.append(
                f"Temperature spread conflict in {area}: {min(temps):.1f}°C to {max(temps):.1f}°C."
            )

        has_moisture = any(any(k in item.raw_line.lower() for k in ["moisture", "damp", "leak"]) for item in area_findings)
        has_normal_temp = any(0 <= temp <= 40 for temp in temps)
        if has_moisture and has_normal_temp:
            conflicts.append(
                f"Moisture observed in {area} while thermal values include normal range readings."
            )

        inspection_no_damage = any(
            item.source.lower().startswith("inspection") and re.search(r"\bno\b.{0,20}\b(damage|issue|overheat|crack)\b", item.raw_line.lower())
            for item in area_findings
        )
        thermal_hotspot = any(
            item.source.lower().startswith("thermal") and any(temp >= 70 for temp in item.temperatures_c)
            for item in area_findings
        )
        if inspection_no_damage and thermal_hotspot:
            conflicts.append(
                f"Inspection indicates no damage in {area}, but thermal evidence shows hotspot >= 70°C."
            )

    return _dedupe_lines(conflicts)


def _severity(findings: Sequence[Finding]) -> Tuple[str, str]:
    all_text = " ".join(item.raw_line.lower() for item in findings)
    max_temp = max((temp for item in findings for temp in item.temperatures_c), default=None)

    if max_temp is not None and max_temp > 70:
        return "High", f"Elevated temperature ({max_temp:.1f}°C) exceeds safe operating guidance."
    if "crack" in all_text and any(word in all_text for word in ["moisture", "damp", "leak"]):
        return "High", "Structural crack appears with moisture indicators; escalation advised."
    if any(word in all_text for word in ["leak", "moisture", "damp", "hotspot", "overheat"]):
        return "Medium", "Documented water or thermal anomaly indicators are present."
    if any(word in all_text for word in ["stain", "cosmetic", "paint"]):
        return "Low", "Findings appear cosmetic based on available evidence."
    return "Low", "Limited evidence of material risk in supplied documents."


def build_ddr(inspection_text: str, thermal_text: str, ingestion_notes: List[str] | None = None) -> DDR:
    raw_findings = parse_document(inspection_text, "Inspection Report") + parse_document(thermal_text, "Thermal Report")
    findings = _merge_related_findings(raw_findings)

    issue_summary: List[str] = []
    root_causes: List[str] = []
    actions: List[str] = []
    notes = list(ingestion_notes or [])
    missing: List[str] = []
    area_map: Dict[str, List[str]] = {}

    for finding in findings:
        area_map.setdefault(finding.area, []).append(f"[{finding.source}] {finding.raw_line}")
        if "issue" in finding.tags:
            issue_summary.append(finding.raw_line)
        if "cause" in finding.tags:
            root_causes.append(finding.raw_line)
        if "action" in finding.tags:
            actions.append(finding.raw_line)

    conflicts = _find_conflicts(findings)
    notes.extend(conflicts)

    if not any(temp for finding in findings for temp in finding.temperatures_c):
        missing.append("Temperature readings: Not Available")
    if not root_causes:
        missing.append("Probable root cause statements: Not Available")
    if not actions:
        missing.append("Recommended actions in source docs: Not Available")
    if not area_map:
        missing.append("Area-level observations: Not Available")

    severity_level, severity_reason = _severity(findings)

    return DDR(
        property_issue_summary=_dedupe_lines(issue_summary) or ["Not Available"],
        area_wise_observations={a: _dedupe_lines(v) for a, v in sorted(area_map.items())} or {"General": ["Not Available"]},
        probable_root_cause=_dedupe_lines(root_causes) or ["Not Available"],
        severity_assessment={"level": severity_level, "reasoning": severity_reason},
        recommended_actions=_dedupe_lines(actions) or ["Not Available"],
        additional_notes=_dedupe_lines(notes) or ["Not Available"],
        missing_or_unclear_information=_dedupe_lines(missing) or ["Not Available"],
        conflicts_detected=_dedupe_lines(conflicts) or ["Not Available"],
    )


def _safe_list(items: List[str]) -> List[str]:
    clean = [item for item in items if item and item.strip()]
    return clean or ["Not Available"]


def _introduction_text(ddr: DDR) -> str:
    total_areas = len([a for a, vals in ddr.area_wise_observations.items() if vals and vals != ["Not Available"]])
    severity = ddr.severity_assessment.get("level", "Not Available")
    if total_areas == 0:
        return "Not Available"
    return (
        f"This report consolidates inspection and thermal findings for {total_areas} area(s). "
        f"Current overall severity is {severity}."
    )


def render_markdown(ddr: DDR) -> str:
    lines: List[str] = ["# Main DDR (Detailed Diagnostic Report)", ""]

    lines.append("## 1. Property Issue Summary")
    lines.extend(f"- {item}" for item in _safe_list(ddr.property_issue_summary))

    lines.append("\n## 2. Introduction")
    lines.append(_introduction_text(ddr))

    lines.append("\n## 3. Area-wise Observations")
    if not ddr.area_wise_observations:
        lines.append("Not Available")
    else:
        for area, items in ddr.area_wise_observations.items():
            lines.append(f"### {area}")
            lines.extend(f"- {item}" for item in _safe_list(items))

    lines.append("\n## 4. Probable Root Cause")
    lines.extend(f"- {item}" for item in _safe_list(ddr.probable_root_cause))

    lines.append("\n## 5. Severity Assessment (with reasoning)")
    lines.append(f"- Severity Level: {ddr.severity_assessment.get('level', 'Not Available')}")
    lines.append(f"- Reasoning: {ddr.severity_assessment.get('reasoning', 'Not Available')}")

    lines.append("\n## 6. Recommended Actions")
    lines.extend(f"- {item}" for item in _safe_list(ddr.recommended_actions))

    lines.append("\n## 7. Additional Notes")
    lines.extend(f"- {item}" for item in _safe_list(ddr.additional_notes))

    lines.append("\n## 8. Missing or Unclear Information")
    lines.extend(f"- {item}" for item in _safe_list(ddr.missing_or_unclear_information))

    lines.append("\n## 9. Conflicts Detected")
    lines.extend(f"- {item}" for item in _safe_list(ddr.conflicts_detected))

    return "\n".join(lines) + "\n"


def render_report_from_ddr_json(ddr_json: str) -> str:
    payload = json.loads(ddr_json)
    ddr = DDR(
        property_issue_summary=payload.get("property_issue_summary", []) or ["Not Available"],
        area_wise_observations=payload.get("area_wise_observations", {}) or {"General": ["Not Available"]},
        probable_root_cause=payload.get("probable_root_cause", []) or ["Not Available"],
        severity_assessment=payload.get("severity_assessment", {"level": "Not Available", "reasoning": "Not Available"}),
        recommended_actions=payload.get("recommended_actions", []) or ["Not Available"],
        additional_notes=payload.get("additional_notes", []) or ["Not Available"],
        missing_or_unclear_information=payload.get("missing_or_unclear_information", []) or ["Not Available"],
        conflicts_detected=payload.get("conflicts_detected", payload.get("conflicts", [])) or ["Not Available"],
    )
    return render_markdown(ddr)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_simple_pdf(text: str, output_path: Path) -> None:
    lines = text.splitlines() or [""]
    page_width, page_height = 595, 842
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
    page_obj_ids: List[int] = []
    content_obj_ids: List[int] = []

    for page_lines in pages:
        stream_lines = ["BT", "/F1 10 Tf", f"1 0 0 1 {margin} {page_height - margin} Tm", f"0 -{line_height} Td"]
        for line in page_lines:
            stream_lines.append(f"({_pdf_escape(line)}) Tj")
            stream_lines.append(f"0 -{line_height} Td")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines)
        content_obj = add_object(
            f"<< /Length {len(stream.encode('latin-1', errors='ignore'))} >>\nstream\n{stream}\nendstream"
        )
        content_obj_ids.append(content_obj)
        page_obj_ids.append(add_object("PENDING_PAGE"))

    kids_refs = " ".join(f"{obj_id} 0 R" for obj_id in page_obj_ids)
    pages_obj = add_object(f"<< /Type /Pages /Count {len(page_obj_ids)} /Kids [ {kids_refs} ] >>")

    for idx, page_obj_id in enumerate(page_obj_ids):
        page_dict = (
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_obj_ids[idx]} 0 R >>"
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DDR from inspection and thermal reports")
    parser.add_argument("--inspection", help="Path to inspection report")
    parser.add_argument("--thermal", help="Path to thermal report")
    parser.add_argument("--from-json", dest="from_json", help="Path to DDR JSON input for report-only rendering")
    parser.add_argument("--out", required=True, help="Output markdown path")
    parser.add_argument("--json", dest="json_out", help="Optional output JSON path")
    parser.add_argument("--out-pdf", dest="pdf_out", help="Optional output PDF path")
    args = parser.parse_args()

    if args.from_json:
        markdown = render_report_from_ddr_json(Path(args.from_json).read_text(encoding="utf-8"))
        ddr = None
    else:
        if not args.inspection or not args.thermal:
            raise ValueError("--inspection and --thermal are required unless --from-json is provided")
        inspection_text, inspection_notes = load_document(args.inspection)
        thermal_text, thermal_notes = load_document(args.thermal)
        ddr = build_ddr(inspection_text, thermal_text, ingestion_notes=inspection_notes + thermal_notes)
        markdown = render_markdown(ddr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")

    if args.json_out and ddr is not None:
        Path(args.json_out).write_text(json.dumps(asdict(ddr), indent=2), encoding="utf-8")
    if args.pdf_out:
        render_simple_pdf(markdown, Path(args.pdf_out))


if __name__ == "__main__":
    main()
