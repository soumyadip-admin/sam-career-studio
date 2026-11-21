import unittest
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]


class ResumeUIContractTests(unittest.TestCase):
    def test_resume_navigation_form_results_and_downloads_exist(self):
        soup = BeautifulSoup((ROOT / "templates/index.html").read_text(), "html.parser")
        required_ids = {
            "resume", "resumeForm", "resumeTitle", "resumeCompany", "resumeSourceUrl",
            "resumeDescription", "buildResume", "resumeResult", "resumeMatched",
            "resumePartial", "resumeMissing", "downloadResumeDocx", "downloadResumePdf",
        }
        existing = {element.get("id") for element in soup.find_all(id=True)}
        self.assertTrue(required_ids.issubset(existing), required_ids - existing)
        resume_link = soup.select_one('nav a[href="#resume"]')
        self.assertIsNotNone(resume_link)
        self.assertEqual(resume_link.get_text(strip=True), "Resume")

    def test_front_end_binds_analysis_and_both_download_buttons(self):
        script = (ROOT / "static/app.js").read_text()
        self.assertIn("/api/resume/analyze", script)
        self.assertIn("/api/resume/download", script)
        self.assertIn("downloadTailoredResume('docx')", script)
        self.assertIn("downloadTailoredResume('pdf')", script)


if __name__ == "__main__":
    unittest.main()
