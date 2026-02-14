import unittest

from src.ui_app import render_page


class TestUIApp(unittest.TestCase):
    def test_render_page_has_upload_form(self):
        html = render_page()
        self.assertIn('name="inspection"', html)
        self.assertIn('name="thermal"', html)

    def test_render_page_shows_report_and_download(self):
        html = render_page('ok', report_markdown='# DDR', report_id='abc123')
        self.assertIn('Generated DDR Report', html)
        self.assertIn('/download?id=abc123', html)


if __name__ == '__main__':
    unittest.main()
