import io
import unittest
import zipfile

from resume_engine import (
    STARTEK_DATE_CORRECTION,
    analyze_job,
    build_docx,
    build_pdf,
    build_resume_payload,
    resume_plain_text,
)


SAMPLE_JD = """
Job Role - Data Analyst Fresher. Experience: 0-1 Year. Any Graduate.
Collect, clean, and analyze structured and unstructured data. Interpret data trends
and patterns to generate actionable insights. Create reports, dashboards, and data
visualizations. Support business teams with analytical requirements. Perform data
validation and quality checks. Skills: Basic computer knowledge, Excel, Advanced
Excel, Pivot Tables, VLOOKUP, Power Query, SQL, Python, Power BI, Tableau, data
entry, data management, EDA, statistical analysis, data interpretation, MySQL,
PostgreSQL, data modeling and good communication skills.
"""


class ResumeEngineTests(unittest.TestCase):
    def test_sample_jd_reports_supported_and_missing_evidence(self):
        result = analyze_job("Data Analyst Fresher", "Sample employer", SAMPLE_JD)
        for label in ("Advanced Excel", "Power Query", "Power BI", "SQL", "Tableau", "Data cleaning & quality"):
            self.assertIn(label, result["matched"])
        self.assertIn("Python", result["missing"])
        self.assertIn("Specific SQL platform", result["partial"])
        self.assertEqual(result["required_years_range"], [0.0, 1.0])
        self.assertGreaterEqual(result["tailored_keyword_visibility"], result["original_keyword_visibility"])

    def test_missing_skills_are_not_inserted(self):
        result = analyze_job("Data Analyst", "Sample employer", SAMPLE_JD)
        payload = build_resume_payload("Data Analyst", "Sample employer", SAMPLE_JD, result)
        text = resume_plain_text(payload).lower()
        self.assertNotIn("python", text)
        self.assertNotIn("mysql", text)
        self.assertNotIn("postgresql", text)

    def test_corrected_startek_dates_appear_in_resume(self):
        result = analyze_job("Data Analyst", "Sample employer", SAMPLE_JD)
        payload = build_resume_payload("Data Analyst", "Sample employer", SAMPLE_JD, result)
        self.assertIn(STARTEK_DATE_CORRECTION, resume_plain_text(payload))
        self.assertNotIn("Dec 2025 - May 2026", resume_plain_text(payload))

    def test_docx_and_pdf_are_valid_downloads(self):
        docx, docx_result = build_docx("Data Analyst", "Sample employer", SAMPLE_JD)
        self.assertTrue(docx.startswith(b"PK"))
        with zipfile.ZipFile(io.BytesIO(docx)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("Sep 2026", xml)
            self.assertNotIn("May 2026", xml)
            self.assertNotIn("Python", xml)
        pdf, pdf_result = build_pdf("Data Analyst", "Sample employer", SAMPLE_JD)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(docx_result["analysis_id"], pdf_result["analysis_id"])

    def test_diagnostic_never_claims_a_guarantee(self):
        result = analyze_job("Data Analyst", "Sample employer", SAMPLE_JD)
        self.assertIn("No tool can guarantee", result["disclaimer"])
        self.assertLessEqual(result["score"], 96)


if __name__ == "__main__":
    unittest.main()
