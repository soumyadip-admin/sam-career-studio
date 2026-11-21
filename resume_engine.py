"""Truth-preserving ATS analysis and resume generation for Soumyadip Sarkar.

The engine may reorder and rephrase only evidence in the supplied resume. It never
adds a missing technology, employer, degree, date, result, or application claim.
Scores are deterministic readiness diagnostics, not predictions from an employer ATS.
"""
from __future__ import annotations

import hashlib
import html
import io
import re
from dataclasses import dataclass
from typing import Iterable


PROFILE_VERSION = "supplied-resume-2026-11-20-r1"
STARTEK_DATE_CORRECTION = "Dec 2025 - Sep 2026"

CONTACT = {
    "name": "Soumyadip Sarkar",
    "phone": "6363793581",
    "email": "soumyadipsarkar2106@gmail.com",
    "location": "Bangalore, India",
    "portfolio": "https://soumyadip-admin.github.io/data-analyst-portfolio/",
}

EDUCATION = [
    {
        "degree": "Bachelor in Hospitality Management (BHSM)",
        "school": "Guru Nanak Institute of Hotel Management, Kolkata",
        "dates": "Jun 2016 - Dec 2019",
    }
]

COURSES = [
    "Google Data Analytics Professional Certificate, Coursera | Jun 2025 - Dec 2025",
    "Microsoft Excel - Advanced, Udemy | Jan 2025 - May 2025",
    "Accenture Data Analytics & Visualization Job Simulation | Dec 2024 - Jan 2025",
    "Power BI, Office Master | Aug 2024",
]

EXPERIENCE = [
    {
        "title": "Senior Operations Executive",
        "company": "Startek, Bangalore",
        "dates": STARTEK_DATE_CORRECTION,
        "bullets": [
            "Supported internet, TV, and mobile customers by handling queries, complaints, and technical issues.",
            "Processed activations, plan changes, billing queries, and service upgrades with a focus on accuracy.",
            "Worked toward sales targets by presenting suitable plans and add-ons.",
            "Recorded customer interactions in CRM and followed standard operating procedures to support service quality.",
        ],
    },
    {
        "title": "Customer Experience Agent",
        "company": "Alorica, Bangalore",
        "dates": "Sep 2024 - Jul 2025",
        "bullets": [
            "Managed and updated customer data using Excel and CRM tools, maintaining data integrity across 1,000+ customer records.",
            "Investigated and resolved data discrepancies through root-cause analysis, improving data quality by 15%.",
            "Generated reports and performance summaries for management review and data-informed decision-making.",
            "Documented billing and payment information in a structured format to keep records organized for analysis.",
        ],
    },
    {
        "title": "Customer Service Associate - Non Voice",
        "company": "Teleperformance, Kolkata",
        "dates": "Aug 2023 - Dec 2023",
        "bullets": [
            "Maintained detailed customer interaction and communication records in a structured database for quality analysis.",
            "Compiled and formatted performance data for quality-assurance reporting and process-improvement work.",
            "Assisted with data entry, validation, and organization of performance-tracking systems.",
        ],
    },
    {
        "title": "Technical Documentation & Data Analysis",
        "company": "Academic Content Writer, Kolkata",
        "dates": "Jan 2021 - Aug 2023",
        "bullets": [
            "Created technical content and presentations that communicated complex analytical concepts clearly.",
            "Adapted analytical material for different audiences, strengthening documentation, communication, and data-storytelling skills.",
        ],
    },
]

PROJECT = {
    "title": "Business Data Reporting & Dashboard Development",
    "dates": "Oct 2025 - Dec 2025",
    "bullets": [
        "Designed Power BI and Excel executive dashboards to track KPIs and system-performance metrics across automotive, financial, telecom, retail, and aviation datasets.",
        "Used SQL joins, aggregations, and window functions to extract, transform, and validate relational data across 700,000+ records; created calculated fields, measures, and validation rules in Power BI.",
        "Developed and automated a monthly performance-reporting suite, reducing manual reporting time by 30% through Excel macro automation and query optimization.",
        "Analyzed system-performance bottlenecks and documented indexing and query-optimization recommendations associated with 25% faster report generation.",
        "Implemented data-validation rules and audit trails that supported 99.5% data accuracy across reporting systems.",
    ],
}

BASE_SKILLS = [
    "Advanced Excel", "Pivot Tables", "VLOOKUP", "Excel Macros", "Excel Automation",
    "Power Query", "Power BI", "Dashboard Development", "Data Visualization",
    "SQL", "SQL Joins", "Window Functions", "Data Validation", "Tableau", "R",
    "Exploratory Data Analysis (EDA)", "Statistical Analysis", "ETL Processes",
    "Database Management", "Regression Analysis", "Performance Reporting",
    "Data Quality", "Data Entry", "CRM", "Technical Documentation", "Microsoft Office",
]

# Baseline text is used only to measure how visible a JD phrase was before tailoring.
BASE_RESUME_TEXT = " ".join(
    [CONTACT["name"], "Senior Process Executive", *BASE_SKILLS, *(COURSES),
     EDUCATION[0]["degree"], PROJECT["title"], *PROJECT["bullets"]]
    + [part for role in EXPERIENCE for part in [role["title"], role["company"], *role["bullets"]]]
)


@dataclass(frozen=True)
class SkillRule:
    label: str
    aliases: tuple[str, ...]
    support: float
    evidence: str
    resume_terms: tuple[str, ...]
    weight: int = 3


SKILL_RULES = [
    SkillRule("Advanced Excel", ("advanced excel", "microsoft excel", "ms excel", "excel", "pivot table", "pivot tables", "vlookup", "xlookup"), 1.0, "Advanced Excel, Pivot Tables, VLOOKUP, macros and automation are stated in the supplied resume.", ("Advanced Excel", "Pivot Tables", "VLOOKUP", "Excel Macros", "Excel Automation"), 5),
    SkillRule("Power Query", ("power query", "m language"), 1.0, "Power Query is stated in the supplied resume.", ("Power Query",), 4),
    SkillRule("Power BI", ("power bi", "powerbi", "dax"), 1.0, "Power BI dashboard development and measures are stated in the supplied resume and project.", ("Power BI", "Dashboard Development"), 5),
    SkillRule("SQL", ("sql", "sql queries", "joins", "window functions"), 1.0, "SQL queries, joins and window functions are stated in the supplied resume and project.", ("SQL", "SQL Joins", "Window Functions"), 5),
    SkillRule("Specific SQL platform", ("mysql", "postgresql", "postgres", "sql server", "oracle sql"), 0.55, "The resume supports SQL generally but does not name this specific database platform.", ("SQL",), 3),
    SkillRule("Tableau", ("tableau",), 1.0, "Tableau is stated in the supplied resume.", ("Tableau",), 3),
    SkillRule("R", ("r programming", "r language", "rstudio", "dplyr", "ggplot2", "tidyverse"), 1.0, "R, dplyr, ggplot2 and tidyverse are stated in the supplied resume.", ("R",), 3),
    SkillRule("Python", ("python", "pandas", "numpy", "matplotlib", "seaborn"), 0.0, "Python is not stated in the supplied PDF resume, so the engine does not add it.", (), 4),
    SkillRule("Data cleaning & quality", ("data cleaning", "data cleansing", "clean data", "data quality", "quality checks", "data validation", "validate data", "reconciliation"), 1.0, "Data discrepancy resolution, validation rules and data-quality results are stated in the resume.", ("Data Validation", "Data Quality"), 5),
    SkillRule("Data analysis & interpretation", ("data analysis", "data analytics", "analyze data", "analyse data", "data interpretation", "interpret data", "trends and patterns", "actionable insights", "business insights", "root cause analysis"), 1.0, "Analysis, root-cause work, trend interpretation and decision support are supported by the resume.", ("Exploratory Data Analysis (EDA)", "Statistical Analysis"), 5),
    SkillRule("Data visualization", ("data visualization", "data visualisation", "visualization", "visualisation", "charts", "graphs"), 1.0, "Data Visualization is stated in the resume and supported by dashboard work.", ("Data Visualization",), 4),
    SkillRule("Dashboards", ("dashboard", "dashboards", "kpi dashboard", "interactive dashboard"), 1.0, "Power BI and Excel executive dashboard development is stated in the project.", ("Dashboard Development", "Power BI"), 5),
    SkillRule("Reporting & MIS", ("reporting", "reports", "mis reporting", "management information system", "performance summary", "kpi", "key performance indicator"), 1.0, "Performance reports, management summaries, KPI dashboards and monthly reporting are stated in the resume.", ("Performance Reporting", "Dashboard Development"), 5),
    SkillRule("Data entry & processing", ("data entry", "data processing", "computer operator", "backend operations", "back office", "back-office"), 1.0, "Data entry, structured records and backend/CRM operations are supported by employment history.", ("Data Entry", "CRM"), 2),
    SkillRule("Data management", ("data management", "database management", "manage data", "data manipulation", "data extraction"), 1.0, "Database management, SQL extraction and structured-record management are stated in the resume.", ("Database Management", "SQL"), 4),
    SkillRule("ETL", ("etl", "extract transform load", "data pipeline", "data transformation"), 1.0, "ETL Processes and SQL-based extract/transform/validation work are stated in the resume.", ("ETL Processes", "SQL"), 4),
    SkillRule("Exploratory data analysis", ("exploratory data analysis", "eda"), 1.0, "Exploratory Data Analysis is stated in the supplied resume.", ("Exploratory Data Analysis (EDA)",), 4),
    SkillRule("Statistical analysis", ("statistical analysis", "statistics", "regression analysis", "hypothesis testing", "a/b testing", "ab testing"), 0.9, "Statistical Analysis and Regression Analysis are stated; hypothesis/A-B testing is not separately evidenced.", ("Statistical Analysis", "Regression Analysis"), 4),
    SkillRule("Business intelligence", ("business intelligence", "bi reporting", "bi analyst"), 1.0, "Power BI, dashboards, KPI reporting and data visualization support business-intelligence work.", ("Power BI", "Dashboard Development", "Performance Reporting"), 4),
    SkillRule("Communication", ("communication", "communicate", "presentation", "presentations", "data storytelling", "storytelling"), 1.0, "Technical content, presentations, data storytelling and communication are stated in the resume.", ("Technical Documentation",), 3),
    SkillRule("Cross-functional collaboration", ("cross-functional", "stakeholder", "business teams", "collaboration", "collaborate"), 0.85, "Cross-functional collaboration and management reporting are stated, but formal stakeholder ownership is not claimed.", ("Technical Documentation", "Performance Reporting"), 3),
    SkillRule("Problem solving", ("problem solving", "problem-solving", "analytical thinking", "root cause", "troubleshooting"), 1.0, "Analytical problem-solving and root-cause analysis are stated in the resume.", ("Data Quality",), 3),
    SkillRule("Computer & office tools", ("basic computer", "computer knowledge", "microsoft office", "ms office", "word", "outlook", "access"), 1.0, "Microsoft Office Suite is stated in the resume.", ("Microsoft Office",), 2),
    SkillRule("CRM", ("crm", "customer relationship management"), 1.0, "CRM record maintenance is stated in employment history.", ("CRM",), 2),
    SkillRule("Data modeling", ("data modeling", "data modelling", "dimensional model", "star schema", "data model"), 0.35, "Power BI calculated fields and measures are stated, but formal data-modeling evidence is limited.", ("Power BI",), 4),
    SkillRule("Forecasting & WFM", ("forecast", "forecasting", "workforce management", "wfm", "capacity planning", "shrinkage", "occupancy", "erlang"), 0.0, "Forecasting/WFM is not stated in the supplied PDF resume.", (), 4),
    SkillRule("Cloud", ("aws", "amazon web services", "azure", "gcp", "google cloud", "cloud platform"), 0.0, "No cloud platform is stated in the supplied resume.", (), 4),
    SkillRule("Snowflake", ("snowflake",), 0.0, "Snowflake is not stated in the supplied resume.", (), 4),
    SkillRule("Databricks / Spark", ("databricks", "pyspark", "apache spark"), 0.0, "Databricks/Spark is not stated in the supplied resume.", (), 4),
    SkillRule("Machine learning", ("machine learning", "scikit-learn", "predictive modeling", "predictive modelling"), 0.0, "Machine learning is not stated in the supplied resume.", (), 4),
    SkillRule("SAS", ("sas", "sas programming"), 0.0, "SAS is not stated in the supplied resume.", (), 3),
    SkillRule("Looker", ("looker", "lookml"), 0.0, "Looker is not stated in the supplied resume.", (), 3),
    SkillRule("VBA", ("vba", "visual basic for applications"), 0.65, "Excel macros are stated, but VBA is not named explicitly.", ("Excel Macros", "Excel Automation"), 3),
    SkillRule("Alteryx", ("alteryx",), 0.0, "Alteryx is not stated in the supplied resume.", (), 3),
    SkillRule("Qlik", ("qlik", "qlikview", "qlik sense"), 0.0, "Qlik is not stated in the supplied resume.", (), 3),
    SkillRule("Salesforce", ("salesforce",), 0.0, "Salesforce is not stated in the supplied resume.", (), 3),
    SkillRule("ServiceNow", ("servicenow", "service now"), 0.0, "ServiceNow is not stated in the supplied resume.", (), 3),
    SkillRule("SAP", ("sap", "sap bw", "sap hana", "business objects"), 0.0, "SAP is not stated in the supplied resume.", (), 4),
    SkillRule("APIs / JSON", ("rest api", "restful api", "api integration", "json", "xml"), 0.0, "API/JSON/XML work is not stated in the supplied resume.", (), 3),
    SkillRule("Hadoop", ("hadoop", "hive", "hdfs"), 0.0, "Hadoop is not stated in the supplied resume.", (), 3),
    SkillRule("SharePoint", ("sharepoint",), 0.0, "SharePoint is not stated in the supplied resume.", (), 2),
    SkillRule("Lean / Six Sigma", ("lean six sigma", "six sigma", "lean methodology", "dmaic"), 0.0, "Lean/Six Sigma is not stated in the supplied resume.", (), 3),
    SkillRule("Finance / FP&A", ("financial analysis", "financial planning", "fp&a", "accounting", "general ledger", "variance analysis", "p&l", "balance sheet"), 0.0, "Formal finance/accounting experience is not stated in the supplied resume.", (), 4),
    SkillRule("Supply chain / procurement", ("supply chain", "procurement", "vendor management", "inventory planning", "logistics"), 0.0, "Supply-chain/procurement domain experience is not stated in the supplied resume.", (), 4),
    SkillRule("Product analytics", ("product analytics", "product metrics", "user behavior", "user behaviour", "funnel analysis", "retention analysis"), 0.0, "Formal product-analytics experience is not stated in the supplied resume.", (), 4),
    SkillRule("Marketing analytics", ("marketing analytics", "digital marketing", "campaign analysis", "ad operations", "google analytics", "adobe analytics"), 0.0, "Marketing/ad-platform analytics is not stated in the supplied resume.", (), 4),
    SkillRule("Risk / compliance", ("risk management", "risk analysis", "regulatory", "compliance", "audit", "sox"), 0.0, "Formal risk, compliance or audit experience is not stated in the supplied resume.", (), 4),
    SkillRule("HR analytics", ("hr analytics", "people analytics", "human resources", "talent acquisition", "payroll"), 0.0, "HR/people-analytics experience is not stated in the supplied resume.", (), 4),
    SkillRule("Research", ("market research", "research methodology", "primary research", "secondary research", "survey design"), 0.35, "Technical research and documentation are supported, but formal market-research methods are not stated.", ("Technical Documentation",), 3),
    SkillRule("EHS domain", ("environment health and safety", "ehs", "environmental health", "safety audit"), 0.0, "Environment, health and safety domain experience is not stated in the supplied resume.", (), 4),
    SkillRule("French", ("french language", "fluent french", "french speaker", "french"), 0.0, "French is not listed; the resume states English, Bengali and Hindi.", (), 3),
    SkillRule("Git", ("git", "github", "version control"), 0.35, "A GitHub-hosted portfolio exists, but Git/version-control proficiency is not stated in the resume.", (), 2),
    SkillRule("Agile / Jira", ("agile", "scrum", "jira"), 0.0, "Agile/Jira is not stated in the supplied resume.", (), 2),
]

EXCLUDED_TERMS = (
    "call center", "call centre", "voice process", "chat process", "telecalling",
    "telecaller", "customer support executive", "customer service executive", "bpo process",
)
MIXED_ROLE_TERMS = ("data entry", "back office", "back-office", "computer operator", "operations executive")
PREFERRED_ROLE_TERMS = (
    "data analyst", "data analytics", "business intelligence", "bi analyst", "reporting analyst",
    "mis analyst", "operations analyst", "data operations", "business analyst", "insights analyst",
)


def _normalize(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", value).strip()


def _contains(text: str, term: str) -> bool:
    term = term.lower().strip()
    if not term:
        return False
    # Short technical tokens need word boundaries; phrases use normalized substring matching.
    if re.fullmatch(r"[a-z0-9+#.]{1,4}", term):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))
    return term in text


def _extract_year_requirement(text: str) -> tuple[float | None, float | None]:
    """Extract candidate experience screens, not a company's age or product history."""
    values: list[tuple[float, float]] = []
    range_patterns = (
        r"(?:experience|exp)[^\d]{0,24}(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:years|yrs|year)",
        r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:years|yrs|year)(?:\s+of)?\s+(?:relevant\s+|professional\s+|work\s+)?experience",
    )
    def employment_context(match: re.Match) -> bool:
        prefix = text[max(0, match.start() - 120):match.start()]
        # Avoid company-history phrases such as “an organization with 14 years of experience”.
        return not bool(re.search(r"(?:company|organisation|organization|firm|business|foundation)\b[^.!?]{0,70}$", prefix))

    for pattern in range_patterns:
        for match in re.finditer(pattern, text):
            if employment_context(match):
                values.append((float(match.group(1)), float(match.group(2))))
    single_patterns = (
        r"(?:experience|exp)[^\d]{0,24}(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs|year)",
        r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs|year)(?:\s+of)?\s+(?:relevant\s+|professional\s+|work\s+)?experience",
        r"(?:minimum|min\.?|at least)\s+(\d+(?:\.\d+)?)\s*(?:years|yrs|year)",
    )
    for pattern in single_patterns:
        for match in re.finditer(pattern, text):
            if employment_context(match):
                number = float(match.group(1)); values.append((number, number))
    if not values:
        return None, None
    # Multiple role-specific requirements can appear; the strictest explicit minimum is safest.
    return max(v[0] for v in values), max(v[1] for v in values)


def _role_alignment(title: str, text: str) -> int:
    opening = f"{title} {text[:1600]}".lower()
    title_lower = title.lower()
    if any(_contains(opening, term) for term in EXCLUDED_TERMS):
        return 15
    if any(_contains(title_lower, term) for term in PREFERRED_ROLE_TERMS):
        score = 96
    elif any(term in title_lower for term in ("analyst", "analytics", "reporting", "data", "operations")):
        score = 72
    elif any(term in opening for term in PREFERRED_ROLE_TERMS):
        score = 62
    else:
        score = 38
    # The supplied resume does not claim seniority in a formal analytics role.
    if re.search(r"\b(senior|sr\.?|lead|manager|principal|director|head|l3|l4)\b", title_lower):
        score = min(score, 55)
    return score


def _experience_alignment(min_years: float | None) -> int:
    # The source resume states 2.5+ years of customer-support/BPO experience. The score treats
    # that as transferable overall experience, never as 2.5 years in a formal Data Analyst job.
    if min_years is None:
        return 75
    if min_years <= 1:
        return 100
    if min_years <= 2.5:
        return 90
    if min_years <= 3:
        return 74
    if min_years <= 4:
        return 48
    if min_years <= 6:
        return 22
    return 8


def _education_alignment(text: str) -> tuple[int, str]:
    if any(term in text for term in ("any graduate", "bachelor's degree", "bachelors degree", "undergraduate degree", "graduate")):
        return 100, "Bachelor's degree present"
    if any(term in text for term in ("computer science", "statistics degree", "mathematics degree", "engineering degree", "b.tech", "btech")):
        return 55, "Bachelor's degree present, but the requested field is not the candidate's hospitality-management degree"
    if any(term in text for term in ("postgraduate", "master's degree", "masters degree", "mba")):
        return 35, "No postgraduate degree is stated"
    return 80, "No explicit degree screen detected"


def _detected_rules(context: str) -> list[dict]:
    detected = []
    for rule in SKILL_RULES:
        hits = sorted({alias for alias in rule.aliases if _contains(context, alias)}, key=lambda value: (-len(value), value))
        if not hits:
            continue
        status = "matched" if rule.support >= 0.75 else "partial" if rule.support > 0 else "gap"
        detected.append({
            "label": rule.label,
            "keywords": hits,
            "status": status,
            "support": rule.support,
            "evidence": rule.evidence,
            "resume_terms": list(rule.resume_terms),
            "weight": rule.weight,
        })
    return detected


def _keyword_score(detected: list[dict]) -> int:
    total = sum(item["weight"] for item in detected)
    earned = sum(item["weight"] * item["support"] for item in detected)
    return round(100 * earned / total) if total else 35


def _visibility_score(text: str, detected: list[dict]) -> int:
    if not detected:
        return 35
    hay = _normalize(text).lower()
    total = sum(item["weight"] for item in detected)
    visible = 0.0
    for item in detected:
        if item["status"] == "gap":
            continue
        aliases = item["keywords"]
        canonical = item["label"].lower()
        if _contains(hay, canonical) or any(_contains(hay, term) for term in aliases):
            visible += item["weight"] * item["support"]
        elif any(_contains(hay, term.lower()) for term in item["resume_terms"]):
            visible += item["weight"] * item["support"] * 0.8
    return round(100 * visible / total)


def _rank_items(items: Iterable[str], terms: Iterable[str]) -> list[str]:
    terms = {term.lower() for term in terms if len(term.strip()) > 1}
    def rank(item: str) -> tuple[int, int]:
        lower = item.lower()
        hits = sum(1 for term in terms if term in lower)
        return hits, len(item)
    return sorted(items, key=rank, reverse=True)


def _clean_title(title: str) -> str:
    value = _normalize(title)[:120] or "Data Analyst"
    value = re.sub(r"\b(fresher|freshers)\b", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" -|,")
    return value or "Data Analyst"


def build_resume_payload(job_title: str, company: str, description: str, analysis: dict | None = None) -> dict:
    analysis = analysis or analyze_job(job_title, company, description)
    matched_rules = [item for item in analysis["requirements"] if item["status"] == "matched"]
    partial_rules = [item for item in analysis["requirements"] if item["status"] == "partial"]
    keyword_terms = [term for item in matched_rules + partial_rules for term in item["keywords"]]
    target = _clean_title(job_title)

    priority_skills: list[str] = []
    for item in matched_rules + partial_rules:
        for term in item["resume_terms"]:
            if term and term not in priority_skills:
                priority_skills.append(term)
    for skill in BASE_SKILLS:
        if skill not in priority_skills:
            priority_skills.append(skill)
    priority_skills = priority_skills[:30]

    highlighted = [item["label"] for item in matched_rules[:6]]
    if not highlighted:
        highlighted = ["Advanced Excel", "Power BI", "SQL", "data validation", "performance reporting"]
    natural = ", ".join(highlighted[:-1]) + (f" and {highlighted[-1]}" if len(highlighted) > 1 else highlighted[0])
    summary = (
        f"Data analytics candidate with operations experience and hands-on reporting projects using {natural}. "
        "Built Power BI and Excel dashboards, used SQL to extract and validate data, and translated findings into management reporting. "
        "Google Data Analytics certified, with documented experience in data quality, root-cause analysis, and technical communication."
    )

    tailored_experience = []
    for index, role in enumerate(EXPERIENCE):
        ranked = _rank_items(role["bullets"], keyword_terms)
        keep = 2 if index in (0, 2, 3) else min(4, len(ranked))
        tailored_experience.append({**role, "bullets": ranked[:keep]})
    project_bullets = _rank_items(PROJECT["bullets"], keyword_terms)[:4]

    return {
        "name": CONTACT["name"],
        "headline": target,
        "contact": CONTACT,
        "summary": summary,
        "skills": priority_skills,
        "experience": tailored_experience,
        "project": {**PROJECT, "bullets": project_bullets},
        "education": EDUCATION,
        "courses": COURSES,
        "languages": "English | Bengali | Hindi",
        "target_company": _normalize(company),
        "profile_version": PROFILE_VERSION,
        "startek_dates": STARTEK_DATE_CORRECTION,
    }


def resume_plain_text(payload: dict) -> str:
    lines = [
        payload["name"], payload["headline"],
        f'{CONTACT["phone"]} | {CONTACT["email"]} | {CONTACT["location"]}',
        CONTACT["portfolio"], "PROFESSIONAL SUMMARY", payload["summary"],
        "CORE SKILLS", " | ".join(payload["skills"]), "PROFESSIONAL EXPERIENCE",
    ]
    for role in payload["experience"]:
        lines.extend([f'{role["title"]} | {role["company"]} | {role["dates"]}', *role["bullets"]])
    lines.extend(["PROJECTS", f'{payload["project"]["title"]} | {payload["project"]["dates"]}', *payload["project"]["bullets"], "EDUCATION"])
    for item in payload["education"]:
        lines.append(f'{item["degree"]} | {item["school"]} | {item["dates"]}')
    lines.extend(["CERTIFICATIONS & COURSES", *payload["courses"], "LANGUAGES", payload["languages"]])
    return "\n".join(lines)


def analyze_job(job_title: str, company: str, description: str) -> dict:
    normalized = _normalize(description)
    if len(normalized) < 30:
        raise ValueError("Paste at least 30 characters from a real job description.")
    title = _clean_title(job_title)
    context = f"{title} {normalized}".lower()
    detected = _detected_rules(context)
    skill_score = _keyword_score(detected)
    role_score = _role_alignment(title, normalized)
    min_years, max_years = _extract_year_requirement(context)
    experience_score = _experience_alignment(min_years)
    education_score, education_note = _education_alignment(context)
    mixed_hits = [term for term in MIXED_ROLE_TERMS if _contains(context, term)]
    excluded_hits = [term for term in EXCLUDED_TERMS if _contains(context, term)]

    weighted = round(skill_score * 0.60 + role_score * 0.15 + experience_score * 0.10 + 95 * 0.10 + education_score * 0.05)
    if excluded_hits:
        weighted = min(weighted, 25)
    recommendation = "Strong tailoring candidate" if weighted >= 80 else "Moderate fit - review gaps" if weighted >= 65 else "Stretch role - verify requirements" if weighted >= 45 else "Low fit / excluded role"

    fingerprint = hashlib.sha256(f"{title}|{_normalize(company)}|{normalized}".encode("utf-8")).hexdigest()[:12]
    preliminary = {
        "analysis_id": fingerprint,
        "scoring_version": "truthful-resume-jd-v1",
        "profile_version": PROFILE_VERSION,
        "job_title": title,
        "company": _normalize(company),
        "score": max(1, min(weighted, 96)),
        "recommendation": recommendation,
        "breakdown": {
            "supported_keyword_coverage": skill_score,
            "skill_coverage": skill_score,
            "role_alignment": role_score,
            "experience_alignment": experience_score,
            "ats_formatting": 95,
            "education_alignment": education_score,
        },
        "formula": "60% supported JD keywords + 15% role alignment + 10% experience + 10% ATS-safe format + 5% education",
        "requirements": detected,
        "matched": [item["label"] for item in detected if item["status"] == "matched"],
        "partial": [item["label"] for item in detected if item["status"] == "partial"],
        "missing": [item["label"] for item in detected if item["status"] == "gap"],
        "required_detected": [item["label"] for item in detected],
        "detected_evidence": {item["label"]: item["keywords"] for item in detected},
        "required_years": min_years,
        "required_years_range": [min_years, max_years] if min_years is not None else None,
        "education_note": education_note,
        "eligibility_warning": f"Excluded-role wording detected: {', '.join(excluded_hits)}." if excluded_hits else None,
        "mixed_role_warning": f"This posting mixes analytics with lower-value operations keywords: {', '.join(mixed_hits)}. Verify the daily work before applying." if mixed_hits else None,
        "source_correction": f"Startek employment is fixed to {STARTEK_DATE_CORRECTION} in every generated resume.",
        "disclaimer": "No tool can guarantee an ATS pass or interview. This diagnostic measures supported keyword coverage and ATS-safe structure; missing skills are reported and never invented.",
    }
    resume = build_resume_payload(title, company, normalized, preliminary)
    tailored_text = resume_plain_text(resume)
    preliminary["original_keyword_visibility"] = _visibility_score(BASE_RESUME_TEXT, detected)
    preliminary["tailored_keyword_visibility"] = _visibility_score(tailored_text, detected)
    preliminary["tailored_headline"] = resume["headline"]
    preliminary["summary_preview"] = resume["summary"]
    preliminary["tailored_skills"] = resume["skills"]
    preliminary["tailored_bullets"] = resume["project"]["bullets"][:3]
    preliminary["learning_priorities"] = preliminary["missing"][:5]
    preliminary["ats_checks"] = [
        "Single-column layout", "Standard section headings", "No tables, text boxes, icons, photo, or header-only contact data",
        "JD keywords included only when supported by the supplied resume", "Corrected Startek dates: Dec 2025 - Sep 2026",
    ]
    return preliminary


def build_docx(job_title: str, company: str, description: str) -> tuple[bytes, dict]:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.section import WD_SECTION
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    analysis = analyze_job(job_title, company, description)
    data = build_resume_payload(job_title, company, description, analysis)
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.52); section.bottom_margin = Inches(0.52)
    section.left_margin = Inches(0.62); section.right_margin = Inches(0.62)
    section.page_width = Inches(8.27); section.page_height = Inches(11.69)

    normal = document.styles["Normal"]
    normal.font.name = "Arial"; normal.font.size = Pt(9.1)
    normal.paragraph_format.space_after = Pt(2.2)
    normal.paragraph_format.line_spacing = 1.02
    for style_name in ("Title", "Heading 1", "Heading 2"):
        style = document.styles[style_name]
        style.font.name = "Arial"; style.font.color.rgb = RGBColor(32, 32, 32)
    document.core_properties.title = f'{data["name"]} - {data["headline"]}'
    document.core_properties.subject = f'Truthfully tailored resume for {company or job_title}'
    document.core_properties.author = data["name"]
    document.core_properties.keywords = ", ".join(analysis["matched"])[:255]

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(data["name"]); r.bold = True; r.font.name = "Arial"; r.font.size = Pt(20)
    p.paragraph_format.space_after = Pt(0)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(data["headline"]); r.bold = True; r.font.size = Pt(11); r.font.color.rgb = RGBColor(190, 82, 28)
    p.paragraph_format.space_after = Pt(1)
    p = document.add_paragraph(f'{CONTACT["phone"]} | {CONTACT["email"]} | {CONTACT["location"]}')
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after = Pt(0)
    p = document.add_paragraph(CONTACT["portfolio"]); p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def section_heading(text: str) -> None:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(4); paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(text.upper()); run.bold = True; run.font.size = Pt(10); run.font.color.rgb = RGBColor(190, 82, 28)
        ppr = paragraph._p.get_or_add_pPr(); border = OxmlElement("w:pBdr"); bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "5"); bottom.set(qn("w:space"), "1"); bottom.set(qn("w:color"), "B8B8B8")
        border.append(bottom); ppr.append(border)

    def bullet(text: str) -> None:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.left_indent = Inches(0.18); paragraph.paragraph_format.first_line_indent = Inches(-0.14)
        paragraph.paragraph_format.space_after = Pt(1.3)
        paragraph.add_run(text)

    def role_line(left: str, right: str) -> None:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.keep_with_next = True; paragraph.paragraph_format.space_before = Pt(2); paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(left); run.bold = True
        paragraph.add_run(f" | {right}").italic = True

    section_heading("Professional Summary")
    document.add_paragraph(data["summary"])
    section_heading("Core Skills")
    document.add_paragraph(" | ".join(data["skills"]))
    section_heading("Professional Experience")
    for role in data["experience"]:
        role_line(f'{role["title"]} - {role["company"]}', role["dates"])
        for value in role["bullets"]:
            bullet(value)
    section_heading("Projects")
    role_line(data["project"]["title"], data["project"]["dates"])
    for value in data["project"]["bullets"]:
        bullet(value)
    section_heading("Education")
    for item in data["education"]:
        role_line(f'{item["degree"]} - {item["school"]}', item["dates"])
    section_heading("Certifications & Courses")
    for value in data["courses"]:
        bullet(value)
    section_heading("Languages")
    document.add_paragraph(data["languages"])

    output = io.BytesIO(); document.save(output)
    return output.getvalue(), analysis


def build_pdf(job_title: str, company: str, description: str) -> tuple[bytes, dict]:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, KeepTogether

    analysis = analyze_job(job_title, company, description)
    data = build_resume_payload(job_title, company, description, analysis)
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=11*mm, bottomMargin=11*mm,
                                 title=f'{data["name"]} - {data["headline"]}', author=data["name"])
    styles = getSampleStyleSheet()
    body = ParagraphStyle("ResumeBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.1, spaceAfter=2.2)
    small = ParagraphStyle("ResumeSmall", parent=body, fontSize=7.8, leading=9.4)
    name_style = ParagraphStyle("ResumeName", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18, leading=20, alignment=TA_CENTER, spaceAfter=1)
    headline_style = ParagraphStyle("Headline", parent=body, fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=colors.HexColor("#B94F1A"), alignment=TA_CENTER, spaceAfter=1)
    contact_style = ParagraphStyle("Contact", parent=small, alignment=TA_CENTER, spaceAfter=1)
    heading = ParagraphStyle("Section", parent=body, fontName="Helvetica-Bold", fontSize=9.3, leading=11, textColor=colors.HexColor("#B94F1A"), spaceBefore=4, spaceAfter=2, borderWidth=0, borderPadding=0)
    role_style = ParagraphStyle("Role", parent=body, fontName="Helvetica-Bold", fontSize=8.4, leading=10, spaceBefore=2, spaceAfter=0)

    def ptext(value: str) -> str:
        return html.escape(value).replace("&amp;", "&amp;")
    def bullets(values: Iterable[str]):
        return ListFlowable([ListItem(Paragraph(ptext(value), small), leftIndent=8) for value in values], bulletType="bullet", start="circle", leftIndent=13, bulletFontSize=5, spaceAfter=1)
    def section_title(value: str):
        return [Paragraph(ptext(value.upper()), heading), Spacer(1, 0.5*mm)]

    story = [
        Paragraph(ptext(data["name"]), name_style),
        Paragraph(ptext(data["headline"]), headline_style),
        Paragraph(ptext(f'{CONTACT["phone"]} | {CONTACT["email"]} | {CONTACT["location"]}'), contact_style),
        Paragraph(ptext(CONTACT["portfolio"]), contact_style),
    ]
    story += section_title("Professional Summary") + [Paragraph(ptext(data["summary"]), body)]
    story += section_title("Core Skills") + [Paragraph(ptext(" | ".join(data["skills"])), small)]
    story += section_title("Professional Experience")
    for role in data["experience"]:
        line = f'<b>{html.escape(role["title"])} - {html.escape(role["company"])}</b> | <i>{html.escape(role["dates"])}</i>'
        story.append(KeepTogether([Paragraph(line, role_style), bullets(role["bullets"])]))
    story += section_title("Projects")
    story.append(KeepTogether([Paragraph(f'<b>{html.escape(data["project"]["title"])}</b> | <i>{html.escape(data["project"]["dates"])}</i>', role_style), bullets(data["project"]["bullets"])]))
    story += section_title("Education")
    for item in data["education"]:
        story.append(Paragraph(f'<b>{html.escape(item["degree"])}</b> - {html.escape(item["school"])} | <i>{html.escape(item["dates"])}</i>', body))
    story += section_title("Certifications & Courses") + [bullets(data["courses"])]
    story += section_title("Languages") + [Paragraph(ptext(data["languages"]), body)]
    document.build(story)
    return output.getvalue(), analysis


def safe_filename(job_title: str, company: str, extension: str) -> str:
    stem = f"Soumyadip_Sarkar_{company or job_title}_{job_title}_ATS"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_.")
    return f"{stem[:130] or 'Soumyadip_Sarkar_Tailored_Resume'}.{extension}"
