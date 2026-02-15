from __future__ import annotations

from typing import Dict

from app.core.deduplicator import deduplicate_observations
from app.core.extractor import extract_observations
from app.core.report_builder import build_report
from app.core.validator import validate_observations
from app.db.models import store_report_run
from app.schemas.ddr_schema import DDRSchema
from app.utils.ocr import ocr_notes_for_ingestion


def run_pipeline(report_id: str, inspection_text: str, thermal_text: str, ingestion_notes: list[str]) -> DDRSchema:
    observations = extract_observations(inspection_text, thermal_text)
    observations = validate_observations(observations)
    observations = deduplicate_observations(observations)

    if not observations:
        raise ValueError("Extraction failed: no observations detected from uploaded files.")

    ocr_confidence, normalized_notes = ocr_notes_for_ingestion(ingestion_notes)
    report = build_report(observations=observations, ingestion_notes=normalized_notes, ocr_confidence=ocr_confidence)

    store_report_run(
        report_id=report_id,
        inspection_text=inspection_text,
        thermal_text=thermal_text,
        extraction_count=len(observations),
        conflicts_count=0 if report.conflicts == ["Not Available"] else len(report.conflicts),
        severity=report.severity_assessment["level"],
        report_payload=report.to_dict(),
    )

    return report


def build_processing_trace() -> Dict[str, str]:
    return {
        "step_1": "Extracting Text",
        "step_2": "Detecting Observations",
        "step_3": "Checking Conflicts",
        "step_4": "Building Report",
    }
