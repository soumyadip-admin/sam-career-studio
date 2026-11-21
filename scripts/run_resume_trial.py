from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import shutil
import sqlite3
import statistics
import sys
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from resume_engine import (  # noqa: E402
    STARTEK_DATE_CORRECTION,
    analyze_job,
    build_docx,
    build_pdf,
    build_resume_payload,
    resume_plain_text,
)

SELECTED_IDS = [
    1458, 5532, 1429, 4911, 1543, 1424, 4909, 4897, 1430, 1459,
    4961, 4817, 1426, 4813, 1478, 5309, 4815, 4910, 1546, 1477,
    4816, 1548, 4908, 4896, 1476,
]
OUTPUT = Path("/home/user/SAM-Resume-Studio-25-job-trial-2026-11-20")

SAMPLE_JD = """Job Role - Data Analyst Fresher. Experience: 0-1 Year. Any Graduate.
Collect, clean, and analyze structured and unstructured data. Interpret data trends and patterns to generate actionable insights.
Create reports, dashboards, and data visualizations. Support business teams with analytical requirements. Perform data validation and quality checks.
Skills: Basic computer knowledge, Excel, Advanced Excel, Pivot Tables, VLOOKUP, Power Query, SQL, Python, Power BI, Tableau,
data entry, data management, EDA, statistical analysis, data interpretation, MySQL, PostgreSQL, data modeling and good communication skills."""

HARD_GAP_TERMS = {
    "Python": ("python", "pandas", "numpy", "matplotlib", "seaborn"),
    "Cloud": ("aws", "amazon web services", "azure", "gcp", "google cloud"),
    "Snowflake": ("snowflake",),
    "Databricks / Spark": ("databricks", "pyspark", "apache spark"),
    "Machine learning": ("machine learning", "scikit-learn"),
    "SAS": ("sas programming",),
    "Looker": ("looker", "lookml"),
    "Alteryx": ("alteryx",),
    "Qlik": ("qlikview", "qlik sense"),
    "Salesforce": ("salesforce",),
    "ServiceNow": ("servicenow",),
    "SAP": ("sap bw", "sap hana", "business objects"),
    "Hadoop": ("hadoop", "hive", "hdfs"),
    "SharePoint": ("sharepoint",),
    "Lean / Six Sigma": ("six sigma", "dmaic"),
    "French": ("french",),
    "Agile / Jira": ("agile", "scrum", "jira"),
}


def slug(value: str, limit: int = 74) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return (value[:limit] or "job").rstrip("-")


async def check_links(records: list[dict]) -> dict[int, dict]:
    limits = httpx.Limits(max_connections=8, max_keepalive_connections=4)
    timeout = httpx.Timeout(18.0, connect=10.0)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SAMCareerStudioQA/1.0; source-link-check)"}
    semaphore = asyncio.Semaphore(6)
    results: dict[int, dict] = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, limits=limits, headers=headers) as client:
        async def check(record: dict) -> None:
            async with semaphore:
                try:
                    async with client.stream("GET", record["url"]) as response:
                        status = response.status_code
                        classification = "reachable" if status < 400 else "access_restricted" if status in {401, 403, 405, 429} else "http_error"
                        results[record["id"]] = {
                            "status": status,
                            "classification": classification,
                            "final_url": str(response.url),
                            "error": None,
                        }
                except Exception as error:  # Network evidence is recorded, not hidden.
                    results[record["id"]] = {
                        "status": None,
                        "classification": "network_error",
                        "final_url": record["url"],
                        "error": f"{type(error).__name__}: {error}"[:300],
                    }
        await asyncio.gather(*(check(record) for record in records))
    return results


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    for folder in ("resumes/docx", "resumes/pdf", "job-descriptions", "analysis"):
        (OUTPUT / folder).mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(ROOT / "career_engine.db")
    con.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in SELECTED_IDS)
    raw = con.execute(
        f"""SELECT id,source,external_id,title,company,location,description,url,posted_at,
                   scraped_at,match_score,fit_tier,provenance
            FROM live_scraped_jobs WHERE id IN ({placeholders})""",
        SELECTED_IDS,
    ).fetchall()
    con.close()
    by_id = {row["id"]: dict(row) for row in raw}
    missing_ids = [value for value in SELECTED_IDS if value not in by_id]
    if missing_ids:
        raise RuntimeError(f"Selected job rows are missing: {missing_ids}")
    records = [by_id[value] for value in SELECTED_IDS]
    if len(records) != 25:
        raise RuntimeError(f"Expected 25 jobs, got {len(records)}")

    link_results = asyncio.run(check_links(records))
    summary_rows: list[dict] = []
    hard_gap_failures: list[str] = []
    for index, record in enumerate(records, 1):
        title = record["title"] or "Target role"
        company = record["company"] or "Company not supplied"
        description = record["description"] or ""
        analysis = analyze_job(title, company, description)
        analysis["source_job"] = {key: record[key] for key in record if key != "description"}
        analysis["source_link_check"] = link_results[record["id"]]
        analysis["job_description_sha256"] = __import__("hashlib").sha256(description.encode()).hexdigest()

        stem = f"{index:02d}_{slug(company, 34)}_{slug(title, 46)}"
        docx_bytes, docx_analysis = build_docx(title, company, description)
        pdf_bytes, pdf_analysis = build_pdf(title, company, description)
        if docx_analysis["analysis_id"] != analysis["analysis_id"] or pdf_analysis["analysis_id"] != analysis["analysis_id"]:
            raise AssertionError(f"Analysis mismatch for {stem}")
        if not docx_bytes.startswith(b"PK") or not pdf_bytes.startswith(b"%PDF"):
            raise AssertionError(f"Invalid generated file signature for {stem}")
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
            archive.testzip()
            xml = archive.read("word/document.xml").decode("utf-8")
            if "Sep 2026" not in xml or "May 2026" in xml:
                raise AssertionError(f"Startek correction missing from {stem}")

        payload = build_resume_payload(title, company, description, analysis)
        resume_text = resume_plain_text(payload).lower()
        for gap in analysis["missing"]:
            for term in HARD_GAP_TERMS.get(gap, ()):
                if term in resume_text:
                    hard_gap_failures.append(f"{stem}: missing {gap!r} leaked term {term!r}")

        docx_path = OUTPUT / "resumes/docx" / f"{stem}.docx"
        pdf_path = OUTPUT / "resumes/pdf" / f"{stem}.pdf"
        jd_path = OUTPUT / "job-descriptions" / f"{stem}.txt"
        analysis_path = OUTPUT / "analysis" / f"{stem}.json"
        docx_path.write_bytes(docx_bytes); pdf_path.write_bytes(pdf_bytes)
        jd_path.write_text(
            f"Title: {title}\nCompany: {company}\nLocation: {record['location']}\n"
            f"Source: {record['source']}\nPosted: {record['posted_at']}\nURL: {record['url']}\n\n{description}\n",
            encoding="utf-8",
        )
        analysis_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")

        check = link_results[record["id"]]
        summary_rows.append({
            "trial": index,
            "title": title,
            "company": company,
            "location": record["location"],
            "source": record["source"],
            "posted_at": record["posted_at"],
            "source_url": record["url"],
            "link_status": check["status"],
            "link_classification": check["classification"],
            "readiness_score": analysis["score"],
            "recommendation": analysis["recommendation"],
            "supported_keyword_coverage": analysis["breakdown"]["supported_keyword_coverage"],
            "original_keyword_visibility": analysis["original_keyword_visibility"],
            "tailored_keyword_visibility": analysis["tailored_keyword_visibility"],
            "experience_alignment": analysis["breakdown"]["experience_alignment"],
            "minimum_years_detected": analysis["required_years"],
            "matched": "; ".join(analysis["matched"]),
            "partial": "; ".join(analysis["partial"]),
            "gaps_not_added": "; ".join(analysis["missing"]),
            "docx": str(docx_path.relative_to(OUTPUT)),
            "pdf": str(pdf_path.relative_to(OUTPUT)),
        })

    if hard_gap_failures:
        raise AssertionError("Unsupported hard skills leaked into generated resumes:\n" + "\n".join(hard_gap_failures))

    with (OUTPUT / "trial-results.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary_rows[0]))
        writer.writeheader(); writer.writerows(summary_rows)
    (OUTPUT / "source-link-checks.json").write_text(json.dumps(link_results, indent=2), encoding="utf-8")
    sample_result = analyze_job("Data Analyst Fresher", "User-supplied sample", SAMPLE_JD)
    (OUTPUT / "sample-jd-validation.json").write_text(json.dumps(sample_result, indent=2, ensure_ascii=False), encoding="utf-8")

    scores = [row["readiness_score"] for row in summary_rows]
    reachable = sum(row["link_classification"] == "reachable" for row in summary_rows)
    restricted = sum(row["link_classification"] == "access_restricted" for row in summary_rows)
    errors = 25 - reachable - restricted
    rows_md = "\n".join(
        f"| {row['trial']:02d} | {row['title'].replace('|', '/')} | {row['company'].replace('|', '/')} | {row['readiness_score']}% | {row['tailored_keyword_visibility']}% | {row['gaps_not_added'].replace(';', ',') or 'None detected'} |"
        for row in summary_rows
    )
    report = f"""# 25-job Resume Studio trial results

Trial basis: 25 real job records captured by the live scanner on 17–19 November 2026 from public job sources.  
Corrected source fact used in all resumes: **Startek, Dec 2025 – Sep 2026**.

## Result

- Tailored resumes generated: **25 DOCX + 25 PDF**
- Analysis files generated: **25**
- Job-description snapshots: **25**
- Valid DOCX containers: **25/25**
- Valid PDF signatures: **25/25**
- Corrected Startek date present: **25/25**
- Old May 2026 Startek end date absent: **25/25**
- Unsupported hard-skill leakage checks: **passed 25/25**
- Source-link checks: **{reachable} reachable, {restricted} access-restricted by portal, {errors} network/HTTP errors**
- Readiness diagnostic: min **{min(scores)}%**, median **{statistics.median(scores):g}%**, max **{max(scores)}%**

A 403/429 classification means the portal restricted an automated check; it does not mean the listing URL is fabricated. Open the URL in a normal browser and verify availability before applying.

## Trial table

| # | Role | Company | Readiness | Tailored keyword visibility | Genuine gaps not inserted |
|---:|---|---|---:|---:|---|
{rows_md}

## Interpretation

The percentages are deterministic readiness diagnostics, not employer ATS scores. No tool can guarantee an ATS pass or interview. The engine improves ordering and visibility of supported evidence, preserves all employers/dates/results from the supplied resume, and keeps unsupported requirements in the gap report rather than inserting them.
"""
    (OUTPUT / "TRIAL_SUMMARY.md").write_text(report, encoding="utf-8")
    (OUTPUT / "README_FIRST.md").write_text(
        "# SAM Resume Studio 25-job trial\n\n"
        "Start with `TRIAL_SUMMARY.md`, then open `trial-results.csv`. Each numbered job has one DOCX, one PDF, the captured job description, and a detailed JSON analysis.\n\n"
        "The 25 jobs are trial inputs, not application claims. No application was submitted. Verify every live listing before applying.\n\n"
        "The source resume correction applied everywhere is: Startek — Dec 2025 to Sep 2026. No secret values are included.\n",
        encoding="utf-8",
    )
    (OUTPUT / "METHODOLOGY.md").write_text(
        "# Methodology\n\n"
        "1. Read job title, description, location and source URL from the live scanner database.\n"
        "2. Detect explicit experience, education and a controlled taxonomy of analytics/domain requirements.\n"
        "3. Mark each requirement matched, partial, or missing against only the supplied PDF resume.\n"
        "4. Generate a single-column resume with standard headings, no tables, icons, photo or text boxes.\n"
        "5. Reorder supported skills and existing bullets for the JD. Never insert a missing skill.\n"
        "6. Generate DOCX and PDF, validate file signatures/containers and assert the corrected Startek dates.\n"
        "7. Check source URLs over the internet and record reachable, portal-restricted or error status truthfully.\n\n"
        "Score formula: 60% supported JD keywords + 15% role alignment + 10% experience + 10% ATS-safe format + 5% education. Scores are diagnostics, never guarantees.\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(OUTPUT), "jobs": len(summary_rows), "docx": 25, "pdf": 25,
        "min_score": min(scores), "median_score": statistics.median(scores), "max_score": max(scores),
        "links": {"reachable": reachable, "access_restricted": restricted, "other_errors": errors},
        "startek_dates": STARTEK_DATE_CORRECTION,
    }, indent=2))


if __name__ == "__main__":
    main()
