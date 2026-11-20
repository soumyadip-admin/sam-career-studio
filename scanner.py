"""Fresh, policy-aware public job scanner for Sam Career Studio.

The scanner uses public pages/APIs only. It never bypasses login, CAPTCHA, bot
protection or a portal's access controls. Source dates are kept separate from
first-seen timestamps so a newly discovered old vacancy is not called "new".
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import html
import io
import json
import random
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "career_engine.db"
SCAN_LOCK = asyncio.Lock()
USER_AGENT = "SamCareerStudio/3.0 (+personal job research; contact: soumyadipsarkar2106@gmail.com)"
MAX_AGE_HOURS = 72
SHEET_LOOKBACK_DAYS = 7
JOBS_SHEET_ID = "1X6CE7ka9rbj-2xm8YdubQ9e3rzxOk_0KCpELvKRZxEE"
JOBS_SHEET_CSV = f"https://docs.google.com/spreadsheets/d/{JOBS_SHEET_ID}/export?format=csv&gid=0"
INDIA_LOCATION_TERMS = (
    "india", "kolkata", "calcutta", "bengaluru", "bangalore", "hyderabad",
    "gurugram", "gurgaon", "chennai", "mumbai", "pune", "new delhi", "delhi",
    "noida", "ghaziabad", "ahmedabad", "gandhinagar", "jaipur", "indore",
    "kochi", "cochin", "thiruvananthapuram", "trivandrum", "bhubaneswar",
    "chandigarh", "lucknow", "nagpur", "mysuru", "mysore", "coimbatore",
    "visakhapatnam", "vizag", "west bengal", "karnataka", "telangana",
    "maharashtra", "tamil nadu", "andhra pradesh", "uttar pradesh", "haryana",
    "gujarat", "rajasthan", "madhya pradesh", "odisha", "orissa", "kerala",
    "punjab", "assam", "bihar", "jharkhand", "chhattisgarh", "uttarakhand",
    "goa", "jammu", "srinagar",
)
FOREIGN_LOCATION_TERMS = (
    "united states", "usa", "u.s.", "canada", "united kingdom", " uk", "europe",
    "france", "germany", "netherlands", "ireland", "spain", "italy", "portugal",
    "singapore", "malaysia", "philippines", "indonesia", "vietnam", "thailand",
    "australia", "new zealand", "serbia", "croatia", "poland", "romania",
    "south africa", "brazil", "mexico", "united arab emirates", "uae", "dubai",
)
TARGET_ROLE_TERMS = (
    "data analyst", "data analytics", "business analyst", "business intelligence",
    "bi analyst", "power bi", "reporting analyst", "reporting and analytics",
    "reporting & analytics", "mis analyst", "mis executive", "operations analyst",
    "operations analytics", "data operations", "workforce analyst", "workforce analytics",
    "wfm analyst", "customer insights", "revenue analyst", "process excellence",
    "supply chain analyst", "supply chain data", "analytics analyst",
)

# Compact queries avoid hammering a public search endpoint. Bangalore is refreshed
# every hour; Kolkata and Hyderabad alternate. The full location matrix is covered
# every two hours, while public remote feeds refresh every hour.
SEARCH_QUERIES = [
    "Data Analyst", "Junior Data Analyst", "Business Data Analyst",
    "Business Intelligence Analyst", "Power BI Analyst", "Operations Analyst",
    "MIS Reporting Analyst", "Business Analyst", "Customer Insights Analyst",
    "Revenue Analyst", "Data Operations", "Workforce Analytics Analyst",
]

CALL_CENTER_TERMS = [
    "call center", "call centre", "contact center", "contact centre", "voice process",
    "non voice process", "non-voice process", "chat process", "chat support",
    "telecalling", "telecaller", "telesales", "inbound calling", "outbound calling",
    "bpo", "international bpo", "domestic bpo", "bpo process", "process associate",
    "customer support executive", "customer service executive", "customer care executive",
    "collections caller", "dialer", "cold calling",
]
PROFILE_TERMS = {
    "sql": 13, "power bi": 14, "dax": 9, "power query": 7, "excel": 8,
    "python": 9, "pandas": 6, "etl": 6, "data analyst": 13,
    "business intelligence": 12, "reporting": 8, "mis": 8, "operations analyst": 10,
    "workforce": 7, "wfm": 8, "forecast": 5, "dashboard": 6, "analytics": 7,
    "customer insights": 8, "revenue analyst": 8, "process excellence": 7,
    "data operations": 8, "statistics": 4, "stakeholder": 4,
}


def utcnow_dt() -> datetime:
    return datetime.now(timezone.utc)


def utcnow() -> str:
    return utcnow_dt().isoformat()


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def clean(text: object | None) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def strip_html(text: object | None) -> str:
    if not text:
        return ""
    return clean(BeautifulSoup(str(text), "html.parser").get_text(" "))[:7000]


def stable_id(source: str, url: str) -> str:
    return hashlib.sha1(f"{source}|{url}".encode()).hexdigest()[:20]


def parse_datetime(value: object | None) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000
            return datetime.fromtimestamp(number, tz=timezone.utc)
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def relative_date(text: str) -> datetime | None:
    value = clean(text).lower()
    now = utcnow_dt()
    if not value:
        return None
    if any(token in value for token in ("just now", "today", "few seconds")):
        return now
    match = re.search(r"(\d+)\s*(minute|hour|day|week)", value)
    if not match:
        return None
    amount = int(match.group(1)); unit = match.group(2)
    delta = {"minute": timedelta(minutes=amount), "hour": timedelta(hours=amount),
             "day": timedelta(days=amount), "week": timedelta(weeks=amount)}[unit]
    return now - delta


def canonical_sheet_url(value: str) -> str:
    """Remove tracking parameters while preserving a working application URL."""
    try:
        parts = urlsplit(clean(value))
        if parts.scheme not in {"http", "https"}:
            return ""
        return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))
    except ValueError:
        return ""


def parse_sheet_timestamp(value: str) -> datetime | None:
    try:
        local = datetime.strptime(clean(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return local.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def is_fresh(posted_at: object | None) -> tuple[bool, bool, str | None]:
    posted = parse_datetime(posted_at)
    if not posted:
        return True, False, None  # current source listing, but age is not verified
    fresh = utcnow_dt() - posted <= timedelta(hours=MAX_AGE_HOURS)
    return fresh, True, posted.isoformat()


def exclusion_reason(title: str, description: str = "") -> str | None:
    """Exclude prohibited work without treating every employer mention of BPO as the role.

    A bare 'BPO' remains a hard exclusion in the title. Descriptions require a process-
    specific phrase such as voice process, call centre or customer-support executive.
    """
    title_hay = clean(title).lower().replace("–", "-")
    description_hay = clean(description).lower().replace("–", "-")
    for term in CALL_CENTER_TERMS:
        if term in title_hay:
            return f"Excluded call-centre/BPO term in title: {term}"
    description_terms = [term for term in CALL_CENTER_TERMS if term not in {"bpo"}]
    for term in description_terms:
        if term in description_hay:
            return f"Excluded call-centre/BPO process in description: {term}"
    return None


def target_role_allowed(title: str) -> bool:
    """Keep realistic analyst/BI/MIS/reporting transition titles only."""
    value = clean(title).lower().replace("–", "-")
    return bool(value and any(term in value for term in TARGET_ROLE_TERMS))


def location_allowed(location: str, source: str = "") -> bool:
    """Keep India roles and genuinely geography-open remote work.

    Search APIs can return overseas vacancies even when queried for India. An empty or
    broad APAC/Asia location is not enough evidence that an Indian applicant is eligible.
    """
    value = clean(location).lower().replace("–", "-")
    if not value:
        return False
    if any(term in value for term in INDIA_LOCATION_TERMS):
        return True
    remote_open = any(term in value for term in ("remote", "worldwide", "anywhere"))
    explicitly_global = any(term in value for term in ("worldwide", "anywhere", "global"))
    explicitly_foreign = any(term in value for term in FOREIGN_LOCATION_TERMS)
    if remote_open and (explicitly_global or not explicitly_foreign):
        return True
    return False


def match_score(title: str, description: str = "") -> int:
    """Transparent profile relevance; no salary or employer preference is used."""
    title_l = title.lower(); hay = f"{title} {description}".lower()
    score = 12
    for term, points in PROFILE_TERMS.items():
        if term in hay:
            score += points + (3 if term in title_l else 0)
    target_titles = ("data analyst", "business intelligence", "bi analyst", "operations analyst",
                     "reporting analyst", "mis analyst", "customer insight", "revenue analyst",
                     "data operations", "process excellence", "power bi analyst", "wfm analyst")
    if any(term in title_l for term in target_titles):
        score += 30
    unrelated_specialisms = ("cybersecurity", "security operations", "software engineer", "software developer",
                              "support engineer", "network engineer", "devops", "atlassian administrator",
                              "legal counsel", "account executive", "sales engineer")
    if any(term in title_l for term in unrelated_specialisms):
        score -= 28
    minimum_years = None
    experience_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*>?\s*(\d+(?:\.\d+)?)\s*(?:years|yrs)", hay)
    if experience_match:
        minimum_years = float(experience_match.group(1))
    else:
        single_experience = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)", hay)
        if single_experience:
            minimum_years = float(single_experience.group(1))
    if minimum_years is not None:
        if minimum_years >= 6:
            score -= 60
        elif minimum_years >= 4:
            score -= 50
        elif minimum_years > 2.5:
            score -= 20
    if re.search(r"\b(director|vice president|chief|head of)\b", title_l):
        score -= 35
    elif re.search(r"\b(principal|staff)\b", title_l):
        score -= 20
    elif re.search(r"\b(lead|manager)\b", title_l):
        score -= 16
    elif re.search(r"\bsenior|\bsr\.?\b", title_l):
        score -= 12
    if minimum_years is not None and minimum_years >= 4:
        score = min(score, 49)
    return max(1, min(score, 98))


def fit_tier(score: int) -> str:
    return "Recommended" if score >= 55 else "Explore"


def normal_job(**values) -> dict:
    return values


async def linkedin_jobs(client: httpx.AsyncClient, local_location: str) -> tuple[list[dict], list[str]]:
    jobs, errors = [], []
    endpoint = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    locations = ["Bangalore", local_location, "Remote"] if local_location != "Bangalore" else ["Bangalore", "Remote"]
    for role in SEARCH_QUERIES:
        for location in locations:
            try:
                response = await client.get(endpoint, params={"keywords": role, "location": location, "start": 0})
                if response.status_code == 429:
                    errors.append(f"LinkedIn/{role}/{location}: rate limited; remaining requests paced")
                    await asyncio.sleep(8)
                    continue
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                for card in soup.select("div.base-card"):
                    title_el = card.select_one(".base-search-card__title")
                    company_el = card.select_one(".base-search-card__subtitle")
                    location_el = card.select_one(".job-search-card__location")
                    link_el = card.select_one("a.base-card__full-link")
                    time_el = card.select_one("time")
                    if not title_el or not link_el:
                        continue
                    url = (link_el.get("href") or "").split("?")[0]
                    if not url.startswith("http"):
                        continue
                    title = clean(title_el.get_text())
                    id_match = re.search(r"-(\d+)$", url)
                    jobs.append(normal_job(
                        source="LinkedIn", external_id=id_match.group(1) if id_match else stable_id("LinkedIn", url),
                        title=title, company=clean(company_el.get_text()) if company_el else "",
                        location=clean(location_el.get_text()) if location_el else location,
                        role_query=role, description="", url=url,
                        posted_at=time_el.get("datetime") if time_el else None,
                        salary_text=None, employment_type=None,
                        provenance="LinkedIn public guest jobs result",
                    ))
                await asyncio.sleep(1.35 + random.random() * .5)
            except Exception as exc:
                errors.append(f"LinkedIn/{role}/{location}: {type(exc).__name__}: {str(exc)[:100]}")
    return jobs, errors


async def shine_jobs(client: httpx.AsyncClient, local_location: str) -> tuple[list[dict], list[str]]:
    jobs, errors = [], []
    locations = ["bangalore", local_location.lower()] if local_location.lower() != "bangalore" else ["bangalore"]
    for role in SEARCH_QUERIES:
        role_slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
        for location in locations:
            url = f"https://www.shine.com/job-search/{role_slug}-jobs-in-{location}"
            try:
                response = await client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                for card in soup.select("article[itemtype='https://schema.org/ListItem']"):
                    title_el = card.select_one("h2 a")
                    company_el = card.select_one("[class*='result-card_company']")
                    posted_el = card.select_one("[class*='result-card_posted']")
                    meta = [clean(x.get_text()) for x in card.select("[class*='result-card_meta-text']")]
                    href = title_el.get("href") if title_el else None
                    if not href:
                        source_meta = card.select_one("meta[itemprop='url']")
                        href = source_meta.get("content") if source_meta else None
                    if not title_el or not href:
                        continue
                    posted = relative_date(posted_el.get_text() if posted_el else "")
                    skills = ", ".join(clean(x.get_text()) for x in card.select("[class*='result-card_skills-item']"))
                    full_url = urljoin("https://www.shine.com", href).split("?")[0]
                    id_match = re.search(r"/(\d+)$", full_url)
                    jobs.append(normal_job(
                        source="Shine", external_id=id_match.group(1) if id_match else stable_id("Shine", full_url),
                        title=clean(title_el.get_text()), company=clean(company_el.get_text()) if company_el else "",
                        location=meta[2] if len(meta) > 2 else location.title(), role_query=role,
                        description=skills, url=full_url, posted_at=posted.isoformat() if posted else None,
                        salary_text=meta[1] if len(meta) > 1 else None,
                        employment_type=meta[0] if meta else None,
                        provenance="Shine public search result page",
                    ))
                await asyncio.sleep(.35)
            except Exception as exc:
                errors.append(f"Shine/{role}/{location}: {type(exc).__name__}: {str(exc)[:100]}")
    return jobs, errors


async def instahyre_jobs(client: httpx.AsyncClient) -> tuple[list[dict], list[str]]:
    jobs, errors = [], []
    endpoint = "https://www.instahyre.com/api/v1/job_search"
    for role in SEARCH_QUERIES:
        try:
            response = await client.get(endpoint, params={"skills": role, "search": "true", "limit": 35},
                                        headers={"Referer": "https://www.instahyre.com/search-jobs/"})
            response.raise_for_status()
            for item in response.json().get("objects", []):
                employer = item.get("employer") or {}
                url = item.get("public_url")
                if not url:
                    continue
                jobs.append(normal_job(
                    source="Instahyre", external_id=str(item.get("id") or stable_id("Instahyre", url)),
                    title=clean(item.get("title")), company=clean(employer.get("company_name")),
                    location=clean(item.get("locations")), role_query=role,
                    description=", ".join(item.get("keywords") or []), url=url, posted_at=None,
                    salary_text=None, employment_type="Full-time",
                    provenance="Instahyre public job-search API; source does not publish posting age",
                ))
            await asyncio.sleep(.25)
        except Exception as exc:
            errors.append(f"Instahyre/{role}: {type(exc).__name__}: {str(exc)[:120]}")
    return jobs, errors


async def jobs_sheet_jobs(client: httpx.AsyncClient) -> tuple[list[dict], list[str]]:
    """Import recent, deduplicated tracker rows without mislabeling tracker time as posting time.

    The supplied sheet has no header row. Its 11 columns are mapped explicitly as:
    application id, tracker timestamp, portal, title, company, URL, location,
    salary text, tracker score, status and tags. The timestamp records a tracker
    event/application, not the vacancy's publication date, so posted_at stays null.
    """
    try:
        response = await client.get(JOBS_SHEET_CSV, timeout=45.0)
        response.raise_for_status()
        cutoff = utcnow_dt() - timedelta(days=SHEET_LOOKBACK_DAYS)
        newest_by_url: dict[str, tuple[datetime, list[str]]] = {}
        malformed = 0
        for record in csv.reader(io.StringIO(response.text)):
            if len(record) < 11:
                malformed += 1
                continue
            observed = parse_sheet_timestamp(record[1])
            url = canonical_sheet_url(record[5])
            if not observed or observed < cutoff or not url:
                continue
            current = newest_by_url.get(url)
            if current is None or observed > current[0]:
                newest_by_url[url] = (observed, record)

        jobs: list[dict] = []
        for url, (observed, record) in newest_by_url.items():
            application_id, _, portal, title, company, _, location, salary, tracker_score, status, tags = record[:11]
            portal = clean(portal) or "Unknown portal"
            salary = clean(salary)
            jobs.append(normal_job(
                source="Google Sheet Tracker",
                external_id=clean(application_id) or stable_id("Google Sheet Tracker", url),
                title=clean(title), company=clean(company), location=clean(location),
                role_query="Application Tracker", url=url, posted_at=None,
                description=(f"Tracker status: {clean(status) or 'not supplied'}. "
                             f"Tracker tags: {clean(tags) or 'none'}. "
                             f"Original portal: {portal}. Tracker score: {clean(tracker_score) or 'not supplied'}."),
                salary_text=None if salary.lower() in {"", "not disclosed", "nan"} else salary,
                employment_type=None, source_observed_at=observed.isoformat(),
                provenance=("Public Job Application Tracker Google Sheet; deduplicated by canonical URL. "
                            "The tracker timestamp is not a job-posting date."),
            ))
        errors = [f"Google Sheet Tracker: ignored {malformed} malformed rows"] if malformed else []
        return jobs, errors
    except Exception as exc:
        return [], [f"Google Sheet Tracker: {type(exc).__name__}: {str(exc)[:160]}"]


def _jobspy_sync(local_location: str) -> tuple[list[dict], list[str]]:
    """Use JobSpy's public adapters for Naukri, Indeed India and Glassdoor India."""
    try:
        from jobspy import scrape_jobs
    except Exception as exc:
        return [], [f"JobSpy import: {type(exc).__name__}: {str(exc)[:120]}"]
    jobs: list[dict] = []; errors: list[str] = []
    source_names = {"naukri": "Naukri", "indeed": "Indeed India", "glassdoor": "Glassdoor India"}
    terms = ["Data Analyst", "Business Intelligence Analyst", "Operations Analyst", "Reporting Analyst"]
    locations = ["Bangalore, India", f"{local_location}, India"]
    for term in terms:
        for location in locations:
            try:
                frame = scrape_jobs(
                    site_name=["naukri", "indeed", "glassdoor"], search_term=term,
                    location=location, results_wanted=40, hours_old=MAX_AGE_HOURS,
                    country_indeed="India", verbose=0,
                )
                for _, item in frame.iterrows():
                    source_key = clean(item.get("site")).lower()
                    source = source_names.get(source_key, source_key.title())
                    url = clean(item.get("job_url"))
                    if not url:
                        continue
                    description = clean(item.get("description"))
                    skills = clean(item.get("skills"))
                    experience = clean(item.get("experience_range"))
                    if skills and skills.lower() != "nan":
                        description = f"{description} Skills: {skills}"
                    salary = None
                    min_amount, max_amount = item.get("min_amount"), item.get("max_amount")
                    if str(min_amount) != "nan" or str(max_amount) != "nan":
                        salary = f"{clean(item.get('currency'))} {clean(min_amount)}–{clean(max_amount)} {clean(item.get('interval'))}".strip()
                    job_type = clean(item.get("job_type"))
                    if experience and experience.lower() != "nan":
                        job_type = f"{job_type} · {experience}".strip(" ·")
                    jobs.append(normal_job(
                        source=source, external_id=clean(item.get("id")) or stable_id(source, url),
                        title=clean(item.get("title")), company=clean(item.get("company")),
                        location=clean(item.get("location")) or location, role_query=term,
                        description=description if description.lower() != "nan" else "", url=url,
                        posted_at=item.get("date_posted"), salary_text=salary,
                        employment_type=job_type if job_type.lower() != "nan" else None,
                        provenance=f"{source} public search result via the open-source JobSpy adapter",
                    ))
            except Exception as exc:
                errors.append(f"JobSpy/{term}/{location}: {type(exc).__name__}: {str(exc)[:120]}")
    return jobs, errors


async def jobspy_jobs(local_location: str) -> tuple[list[dict], list[str]]:
    return await asyncio.to_thread(_jobspy_sync, local_location)


LEVER_BOARDS = ("meesho", "cred", "zeta", "paytm")
GREENHOUSE_BOARDS = ("groww", "inmobi", "twilio", "rubrik", "okta", "mongodb", "stripe", "databricks", "highradius")


async def employer_board_jobs(client: httpx.AsyncClient) -> tuple[list[dict], list[str]]:
    """Ingest public, direct-employer Lever and Greenhouse posting feeds."""
    jobs: list[dict] = []; errors: list[str] = []
    for board in LEVER_BOARDS:
        try:
            response = await client.get(f"https://api.lever.co/v0/postings/{board}", params={"mode": "json"})
            response.raise_for_status()
            for item in response.json():
                categories = item.get("categories") or {}
                url = item.get("hostedUrl") or item.get("applyUrl")
                title = clean(item.get("text"))
                location = clean(categories.get("location"))
                if not target_role_allowed(title) or not location_allowed(location, "Employer Direct"):
                    continue
                jobs.append(normal_job(
                    source="Employer Direct", external_id=clean(item.get("id")) or stable_id(board, url or ""),
                    title=title, company=board.replace("-", " ").title(),
                    location=location, role_query="Target analytics roles",
                    description=clean(item.get("descriptionPlain") or item.get("descriptionBodyPlain") or item.get("additionalPlain")),
                    url=url, posted_at=item.get("createdAt"), salary_text=None,
                    employment_type=clean(categories.get("commitment")) or None,
                    provenance=f"Direct employer Lever feed: {board}",
                ))
        except Exception as exc:
            errors.append(f"Lever/{board}: {type(exc).__name__}: {str(exc)[:100]}")
    for board in GREENHOUSE_BOARDS:
        try:
            response = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", params={"content": "true"})
            response.raise_for_status()
            for item in response.json().get("jobs", []):
                url = item.get("absolute_url")
                title = clean(item.get("title"))
                location = clean((item.get("location") or {}).get("name"))
                if not target_role_allowed(title) or not location_allowed(location, "Employer Direct"):
                    continue
                jobs.append(normal_job(
                    source="Employer Direct", external_id=str(item.get("id") or stable_id(board, url or "")),
                    title=title, company=clean(item.get("company_name")) or board.title(),
                    location=location, role_query="Target analytics roles",
                    description=strip_html(html.unescape(str(item.get("content") or ""))), url=url,
                    posted_at=item.get("first_published") or item.get("updated_at"), salary_text=None,
                    employment_type=None, provenance=f"Direct employer Greenhouse feed: {board}",
                ))
        except Exception as exc:
            errors.append(f"Greenhouse/{board}: {type(exc).__name__}: {str(exc)[:100]}")
    return [job for job in jobs if job.get("url") and job.get("title")], errors


async def remotive_jobs(client: httpx.AsyncClient) -> tuple[list[dict], list[str]]:
    try:
        response = await client.get("https://remotive.com/api/remote-jobs", params={"limit": 200})
        response.raise_for_status(); results = []
        for item in response.json().get("jobs", []):
            url = item.get("url"); desc = strip_html(item.get("description"))
            results.append(normal_job(
                source="Remotive", external_id=str(item.get("id") or stable_id("Remotive", url or "")),
                title=clean(item.get("title")), company=clean(item.get("company_name")),
                location=clean(item.get("candidate_required_location") or "Remote"),
                role_query="All non-call-centre remote", description=desc, url=url,
                posted_at=item.get("publication_date"), salary_text=clean(item.get("salary")) or None,
                employment_type=item.get("job_type"), provenance="Remotive public jobs API",
            ))
        return [x for x in results if x["url"]], []
    except Exception as exc:
        return [], [f"Remotive: {type(exc).__name__}: {str(exc)[:160]}"]


async def jobicy_jobs(client: httpx.AsyncClient) -> tuple[list[dict], list[str]]:
    try:
        response = await client.get("https://jobicy.com/api/v2/remote-jobs", params={"count": 100})
        response.raise_for_status(); results = []
        for item in response.json().get("jobs", []):
            url = item.get("url") or item.get("jobUrl")
            job_type = item.get("jobType")
            results.append(normal_job(
                source="Jobicy", external_id=str(item.get("id") or stable_id("Jobicy", url or "")),
                title=clean(item.get("jobTitle")), company=clean(item.get("companyName")),
                location=clean(item.get("jobGeo") or "Remote"), role_query="All non-call-centre remote",
                description=strip_html(item.get("jobDescription")), url=url, posted_at=item.get("pubDate"),
                salary_text=None, employment_type=", ".join(job_type) if isinstance(job_type, list) else job_type,
                provenance="Jobicy public jobs API",
            ))
        return [x for x in results if x["url"] and x["title"]], []
    except Exception as exc:
        return [], [f"Jobicy: {type(exc).__name__}: {str(exc)[:160]}"]


async def arbeitnow_jobs(client: httpx.AsyncClient) -> tuple[list[dict], list[str]]:
    try:
        response = await client.get("https://www.arbeitnow.com/api/job-board-api")
        response.raise_for_status(); results = []
        for item in response.json().get("data", []):
            url = item.get("url")
            location = clean(item.get("location") or ("Remote" if item.get("remote") else ""))
            results.append(normal_job(
                source="Arbeitnow", external_id=str(item.get("slug") or stable_id("Arbeitnow", url or "")),
                title=clean(item.get("title")), company=clean(item.get("company_name")), location=location,
                role_query="All non-call-centre", description=strip_html(item.get("description")), url=url,
                posted_at=item.get("created_at"), salary_text=None,
                employment_type=", ".join(item.get("job_types") or []),
                provenance="Arbeitnow public job-board API",
            ))
        return [x for x in results if x["url"]], []
    except Exception as exc:
        return [], [f"Arbeitnow: {type(exc).__name__}: {str(exc)[:160]}"]


async def remoteok_jobs(client: httpx.AsyncClient) -> tuple[list[dict], list[str]]:
    try:
        response = await client.get("https://remoteok.com/api")
        response.raise_for_status(); payload = response.json(); results = []
        for item in payload[1:]:
            url = item.get("url") or item.get("apply_url")
            salary = None
            if item.get("salary_min") or item.get("salary_max"):
                salary = f"{item.get('salary_min') or '?'}–{item.get('salary_max') or '?'} (source units)"
            results.append(normal_job(
                source="RemoteOK", external_id=str(item.get("id") or stable_id("RemoteOK", url or "")),
                title=clean(item.get("position")), company=clean(item.get("company")),
                location=clean(item.get("location") or "Remote / Worldwide"),
                role_query="All non-call-centre remote", description=strip_html(item.get("description")),
                url=url, posted_at=item.get("date") or item.get("epoch"), salary_text=salary,
                employment_type="Remote", provenance="RemoteOK public API; source link retained per API terms",
            ))
        return [x for x in results if x["url"]], []
    except Exception as exc:
        return [], [f"RemoteOK: {type(exc).__name__}: {str(exc)[:160]}"]


async def himalayas_jobs(client: httpx.AsyncClient) -> tuple[list[dict], list[str]]:
    try:
        response = await client.get("https://himalayas.app/jobs/api", params={"limit": 100})
        response.raise_for_status(); results = []
        for item in response.json().get("jobs", []):
            url = item.get("applicationLink")
            restrictions = item.get("locationRestrictions") or []
            location = ", ".join(restrictions) if restrictions else "Remote / Worldwide"
            salary = None
            if item.get("minSalary") or item.get("maxSalary"):
                salary = f"{item.get('currency') or ''} {item.get('minSalary') or '?'}–{item.get('maxSalary') or '?'} {item.get('salaryPeriod') or ''}".strip()
            results.append(normal_job(
                source="Himalayas", external_id=str(item.get("guid") or stable_id("Himalayas", url or "")),
                title=clean(item.get("title")), company=clean(item.get("companyName")), location=location,
                role_query="All non-call-centre remote", description=strip_html(item.get("description")),
                url=url, posted_at=item.get("pubDate"), salary_text=salary,
                employment_type=item.get("employmentType"), provenance="Himalayas public jobs API",
            ))
        return [x for x in results if x["url"]], []
    except Exception as exc:
        return [], [f"Himalayas: {type(exc).__name__}: {str(exc)[:160]}"]


async def github_project_trends(client: httpx.AsyncClient) -> tuple[int, list[str]]:
    query = '"data analyst" portfolio (sql OR powerbi OR python) in:name,description,readme'
    try:
        response = await client.get("https://api.github.com/search/repositories", params={
            "q": query, "sort": "updated", "order": "desc", "per_page": 12,
        }, headers={"Accept": "application/vnd.github+json"})
        response.raise_for_status(); stamp = utcnow(); con = db(); count = 0
        for item in response.json().get("items", []):
            con.execute("""INSERT INTO project_trends(source,external_id,title,description,url,stars,language,updated_at,fetched_at)
                VALUES('GitHub',?,?,?,?,?,?,?,?) ON CONFLICT(source,external_id) DO UPDATE SET
                title=excluded.title,description=excluded.description,url=excluded.url,stars=excluded.stars,
                language=excluded.language,updated_at=excluded.updated_at,fetched_at=excluded.fetched_at""",
                (str(item["id"]), item["full_name"], clean(item.get("description"))[:500], item["html_url"],
                 int(item.get("stargazers_count") or 0), item.get("language"), item.get("updated_at"), stamp))
            count += 1
        con.commit(); con.close(); return count, []
    except Exception as exc:
        return 0, [f"GitHub trends: {type(exc).__name__}: {str(exc)[:160]}"]


async def verify_project_sources(client: httpx.AsyncClient) -> tuple[int, list[str]]:
    con = db(); projects = con.execute("SELECT id,dataset_url FROM projects").fetchall(); con.close()
    sem = asyncio.Semaphore(5); results: list[tuple[int, str]] = []
    async def check(row: sqlite3.Row):
        async with sem:
            try:
                res = await client.get(row["dataset_url"])
                status = "reachable" if res.status_code < 400 else ("access_restricted" if res.status_code in (401,403,429) else f"http_{res.status_code}")
            except Exception:
                status = "unreachable"
            results.append((row["id"], status))
    await asyncio.gather(*(check(row) for row in projects))
    con = db(); stamp = utcnow()
    for pid, status in results:
        con.execute("UPDATE projects SET source_status=?,source_checked_at=? WHERE id=?", (status, stamp, pid))
    con.commit(); con.close()
    return sum(status == "reachable" for _, status in results), []


def db_scalar(value):
    if value is None or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(clean(item) for item in value if item is not None)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def upsert_jobs(jobs: list[dict]) -> tuple[int, int, int]:
    con = db(); stamp = utcnow(); new_count = seen = excluded = 0
    try:
        unique: dict[str, dict] = {}
        for raw in jobs:
            job = {key: db_scalar(value) for key, value in raw.items()}
            url = clean(job.get("url"))
            if not url.startswith("http"):
                continue
            existing = unique.get(url)
            # A dated/direct source wins over the sheet tracker when both reference the same vacancy.
            if existing and clean(job.get("source")) == "Google Sheet Tracker" and clean(existing.get("source")) != "Google Sheet Tracker":
                continue
            unique[url] = job
        for url, job in unique.items():
            title = clean(job.get("title")); description = clean(job.get("description"))
            reason = exclusion_reason(title, description)
            if not reason and not target_role_allowed(title):
                reason = "Outside target analyst/BI/MIS/reporting roles"
            if not reason and not location_allowed(clean(job.get("location")), clean(job.get("source"))):
                reason = "Outside India target locations or verified remote eligibility"
            fresh, verified, normalized_posted = is_fresh(job.get("posted_at"))
            if reason:
                excluded += 1
            score = match_score(title, f"{description} {clean(job.get('employment_type'))}")
            active = int(not reason and fresh)
            exists = con.execute("SELECT id,source FROM live_scraped_jobs WHERE url=?", (url,)).fetchone()
            incoming_source = clean(job.get("source"))
            if exists and incoming_source == "Google Sheet Tracker" and clean(exists["source"]) != "Google Sheet Tracker":
                # Do not downgrade richer direct-source provenance or posting-date confidence.
                seen += 1
                continue
            source_observed_at = job.get("source_observed_at")
            if exists:
                con.execute("""UPDATE live_scraped_jobs SET source=?,external_id=?,title=?,company=?,location=?,
                    role_query=?,description=?,posted_at=COALESCE(?,posted_at),
                    source_observed_at=COALESCE(?,source_observed_at),last_seen_at=?,scraped_at=?,
                    match_score=?,is_active=?,provenance=?,salary_text=COALESCE(?,salary_text),
                    employment_type=COALESCE(?,employment_type),freshness_verified=?,fit_tier=?,excluded_reason=?
                    WHERE url=?""", (
                        job.get("source"), job.get("external_id"), title, job.get("company"), job.get("location"),
                        job.get("role_query"), description, normalized_posted, source_observed_at, stamp, stamp,
                        score, active, job.get("provenance"), job.get("salary_text"), job.get("employment_type"),
                        int(verified), fit_tier(score), reason, url,
                    ))
            else:
                con.execute("""INSERT INTO live_scraped_jobs(source,external_id,title,company,location,role_query,
                    description,posted_at,source_observed_at,first_seen_at,last_seen_at,match_score,is_active,
                    provenance,salary_text,employment_type,freshness_verified,fit_tier,excluded_reason,url,scraped_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                        job.get("source"), job.get("external_id"), title, job.get("company"), job.get("location"),
                        job.get("role_query"), description, normalized_posted, source_observed_at, stamp, stamp,
                        score, active, job.get("provenance"), job.get("salary_text"), job.get("employment_type"),
                        int(verified), fit_tier(score), reason, url, stamp,
                    ))
                new_count += 1
            seen += 1
        # Backfill freshness confidence for records from an earlier schema version.
        con.execute("""UPDATE live_scraped_jobs SET freshness_verified=1
                       WHERE posted_at IS NOT NULL AND posted_at!='' AND source!='Instahyre'""")
        cutoff = (utcnow_dt() - timedelta(hours=MAX_AGE_HOURS)).isoformat()
        unknown_cutoff = (utcnow_dt() - timedelta(hours=6)).isoformat()
        con.execute("UPDATE live_scraped_jobs SET is_active=0 WHERE freshness_verified=1 AND posted_at < ?", (cutoff,))
        con.execute("UPDATE live_scraped_jobs SET is_active=0 WHERE freshness_verified=0 AND last_seen_at < ?", (unknown_cutoff,))
        con.execute("UPDATE live_scraped_jobs SET is_active=0 WHERE excluded_reason IS NOT NULL")
        con.commit(); return seen, new_count, excluded
    except Exception:
        con.rollback(); raise
    finally:
        con.close()


async def run_full_scan() -> dict:
    """Refresh sources incrementally, committing the Sheet fallback first.

    A heavy or blocked portal must never leave a newly started free Render instance with
    an empty radar. Each source is saved independently, so partial progress survives.
    """
    if SCAN_LOCK.locked():
        return {"status": "already_running"}
    async with SCAN_LOCK:
        started = utcnow(); con = db()
        cur = con.execute("INSERT INTO scanner_runs(started_at,status) VALUES(?,'running')", (started,))
        run_id = cur.lastrowid; con.commit(); con.close()
        try:
            local_location = "Kolkata"
            errors: list[str] = []
            succeeded = seen = new = excluded = 0
            timeout = httpx.Timeout(45.0, connect=12.0)

            def save_source(label: str, source_jobs: list[dict]) -> None:
                nonlocal seen, new, excluded, succeeded
                if not source_jobs:
                    return
                try:
                    source_seen, source_new, source_excluded = upsert_jobs(source_jobs)
                    seen += source_seen; new += source_new; excluded += source_excluded
                    succeeded += 1
                    print(f"Scanner run {run_id}: saved {source_seen} records from {label}")
                except Exception as exc:
                    errors.append(f"{label} save: {type(exc).__name__}: {str(exc)[:160]}")

            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"},
                follow_redirects=True,
                timeout=timeout,
            ) as client:
                # Commit the public tracker before slower web sources. These records stay
                # age-unknown and are never represented as freshly posted vacancies.
                try:
                    sheet_jobs, sheet_errors = await jobs_sheet_jobs(client)
                    errors += sheet_errors
                    save_source("Google Sheet Tracker", sheet_jobs)
                except Exception as exc:
                    errors.append(f"Google Sheet Tracker: {type(exc).__name__}: {str(exc)[:160]}")

                # Run sources sequentially to keep memory below free-host limits. A source
                # failure is isolated and does not roll back already committed records.
                source_fetchers = [
                    ("LinkedIn", lambda: linkedin_jobs(client, local_location)),
                    ("Shine", lambda: shine_jobs(client, local_location)),
                    ("Instahyre", lambda: instahyre_jobs(client)),
                    ("Naukri/Indeed/Glassdoor", lambda: jobspy_jobs(local_location)),
                    ("Remotive", lambda: remotive_jobs(client)),
                    ("Jobicy", lambda: jobicy_jobs(client)),
                    ("Arbeitnow", lambda: arbeitnow_jobs(client)),
                    ("RemoteOK", lambda: remoteok_jobs(client)),
                    ("Himalayas", lambda: himalayas_jobs(client)),
                    ("Employer Direct", lambda: employer_board_jobs(client)),
                ]
                for label, fetcher in source_fetchers:
                    try:
                        source_jobs, source_errors = await fetcher()
                        errors += source_errors
                        save_source(label, source_jobs)
                    except Exception as exc:
                        errors.append(f"{label}: {type(exc).__name__}: {str(exc)[:160]}")

                trend_count, trend_errors = await github_project_trends(client)
                errors += trend_errors
                if trend_count:
                    succeeded += 1
                project_count, project_errors = await verify_project_sources(client)
                errors += project_errors
                if project_count:
                    succeeded += 1

            completed = utcnow()
            status = "completed" if succeeded >= 8 and seen > 0 else "partial"
            con = db()
            con.execute("""UPDATE scanner_runs SET completed_at=?,status=?,sources_attempted=13,
                        sources_succeeded=?,jobs_seen=?,jobs_new=?,error_log=? WHERE id=?""",
                        (completed, status, succeeded, seen, new, "\n".join(errors)[:8000], run_id))
            con.execute("INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES('last_scan_at',?,?)", (completed, completed))
            live_named = {"LinkedIn", "Naukri", "Indeed India", "Instahyre", "Glassdoor India", "Shine"}
            for name in live_named:
                label = "live_public_feed" if name != "Instahyre" else "live_public_feed_age_unknown"
                con.execute("UPDATE portals SET last_status=?,last_checked_at=? WHERE name=?", (label, completed, name))
            placeholders = ",".join("?" for _ in live_named)
            con.execute(f"UPDATE portals SET last_status='search_launcher_only',last_checked_at=? WHERE name NOT IN ({placeholders})",
                        (completed, *live_named))
            con.commit(); con.close()
            print(f"Scanner run {run_id}: {status}, {seen} seen, {new} new, {excluded} excluded")
            return {"status": status, "run_id": run_id, "jobs_seen": seen, "jobs_new": new,
                    "excluded": excluded, "sources_succeeded": succeeded, "errors": errors[:8]}
        except Exception as exc:
            completed = utcnow(); message = f"{type(exc).__name__}: {str(exc)[:1000]}"
            con = db(); con.execute("""UPDATE scanner_runs SET completed_at=?,status='failed',sources_attempted=13,
                        error_log=? WHERE id=?""", (completed, message, run_id)); con.commit(); con.close()
            print(f"Scanner run {run_id} failed safely: {message}")
            return {"status": "failed", "run_id": run_id, "error": message}
