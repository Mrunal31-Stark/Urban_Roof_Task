import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.ddr_builder import build_ddr, load_document, render_markdown
import unittest

from src.ddr_builder import build_ddr, render_markdown


class TestDDRBuilder(unittest.TestCase):
    def test_required_sections_and_missing_defaults(self):
        ddr = build_ddr("", "")
        md = render_markdown(ddr)
        self.assertIn("## 1. Property Issue Summary", md)
        self.assertIn("## 7. Missing or Unclear Information", md)
        self.assertIn("Not Available", md)

    def test_dedup_and_area_merge(self):
        inspection = "Roof terrace shows damp patches.\nRoof terrace shows damp patches."
        thermal = "Area roof terrace recorded 33 C anomaly."
        ddr = build_ddr(inspection, thermal)
        self.assertIsNotNone(ddr.area_wise_observations.get("Roof"))
        self.assertEqual(len(ddr.property_issue_summary), 1)

    def test_load_document_multiple_formats(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)

            txt = base / "inspection.txt"
            txt.write_text("Roof leak observed", encoding="utf-8")
            self.assertIn("Roof leak", load_document(str(txt)))

            js = base / "thermal.json"
            js.write_text(json.dumps({"temp": "34 C anomaly"}), encoding="utf-8")
            self.assertIn("34 C anomaly", load_document(str(js)))

            csv_file = base / "obs.csv"
            csv_file.write_text("area,observation\nroof,damp patch", encoding="utf-8")
            self.assertIn("damp patch", load_document(str(csv_file)))

            docx = base / "report.docx"
            xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?><w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>Bathroom wall moisture found</w:t></w:r></w:p></w:body></w:document>"""
            with zipfile.ZipFile(docx, "w") as zf:
                zf.writestr("word/document.xml", xml)
            self.assertIn("Bathroom wall moisture", load_document(str(docx)))

        roof_items = ddr.area_wise_observations.get("Roof")
        self.assertIsNotNone(roof_items)
        self.assertEqual(len(ddr.property_issue_summary), 1)


if __name__ == "__main__":
    unittest.main()
