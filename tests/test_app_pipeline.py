import unittest
from uuid import uuid4

from app.core.extractor import extract_observations
from app.db.models import get_report_run
from app.db.session import init_db
from app.routes.upload import run_pipeline


class TestAppPipeline(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_pipeline_generates_conflicts_and_confidence(self):
        inspection = "Roof area no damage observed. Roof area moisture present near joint."
        thermal = "Roof hotspot 82 C detected during scan."
        report = run_pipeline(
            report_id=f"test-report-{uuid4().hex}",
            inspection_text=inspection,
            thermal_text=thermal,
            ingestion_notes=["PDF parsed in fallback mode; OCR stack recommended for scanned PDFs."],
        )
        payload = report.to_dict()
        self.assertIn("conflicts", payload)
        self.assertEqual(payload["severity_assessment"]["level"], "High")
        self.assertIn("extraction", payload["confidence_scores"])

    def test_audit_row_is_persisted(self):
        report_id = f"test-report-{uuid4().hex}"
        inspection = "Bathroom wall moisture visible"
        thermal = "Bathroom wall 36 C reading"
        run_pipeline(
            report_id=report_id,
            inspection_text=inspection,
            thermal_text=thermal,
            ingestion_notes=[],
        )
        stored = get_report_run(report_id)
        self.assertIsNotNone(stored)
        self.assertIn("report_json", stored)

    def test_extractor_outputs_observations(self):
        obs = extract_observations("Roof damp patch", "Roof 34 C")
        self.assertGreaterEqual(len(obs), 2)


if __name__ == "__main__":
    unittest.main()
