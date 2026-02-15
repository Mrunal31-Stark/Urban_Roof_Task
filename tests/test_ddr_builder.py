import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.ddr_builder import build_ddr, load_document, render_markdown, render_simple_pdf


class TestDDRBuilder(unittest.TestCase):
    def test_required_sections_and_missing_defaults(self):
        ddr = build_ddr("", "")
        md = render_markdown(ddr)
        self.assertIn("## 1. Property Issue Summary", md)
        self.assertIn("## 7. Missing or Unclear Information", md)
        self.assertIn("Not Available", md)

    def test_merge_and_conflict_detection(self):
        inspection = "Roof area no damage observed.\nRoof area moisture near flashing."
        thermal = "Roof hotspot recorded at 78 C."
        ddr = build_ddr(inspection, thermal)
        notes = "\n".join(ddr.additional_notes)
        self.assertIn("hotspot >= 70", notes)
        self.assertEqual(ddr.severity_assessment["level"], "High")

    def test_load_document_multiple_formats(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)

            txt = base / "inspection.txt"
            txt.write_text("Roof leak observed", encoding="utf-8")
            text, notes = load_document(str(txt))
            self.assertIn("Roof leak", text)
            self.assertEqual(notes, [])

            js = base / "thermal.json"
            js.write_text(json.dumps({"temp": "34 C anomaly"}), encoding="utf-8")
            text, _ = load_document(str(js))
            self.assertIn("34 C anomaly", text)

            csv_file = base / "obs.csv"
            csv_file.write_text("area,observation\nroof,damp patch", encoding="utf-8")
            text, _ = load_document(str(csv_file))
            self.assertIn("damp patch", text)

            docx = base / "report.docx"
            xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?><w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>Bathroom wall moisture found</w:t></w:r></w:p></w:body></w:document>"""
            with zipfile.ZipFile(docx, "w") as zf:
                zf.writestr("word/document.xml", xml)
            text, _ = load_document(str(docx))
            self.assertIn("Bathroom wall moisture", text)

    def test_render_simple_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "ddr.pdf"
            render_simple_pdf("# Title\n- line", out)
            data = out.read_bytes()
            self.assertTrue(data.startswith(b"%PDF-1.4"))


if __name__ == "__main__":
    unittest.main()
