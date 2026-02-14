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
        roof_items = ddr.area_wise_observations.get("Roof")
        self.assertIsNotNone(roof_items)
        self.assertEqual(len(ddr.property_issue_summary), 1)


if __name__ == "__main__":
    unittest.main()
