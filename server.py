from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, HttpUrl

from init_db import DB_PATH, init_db
from scanner import SCAN_LOCK, run_full_scan

BASE_DIR = Path(__file__).resolve().parent
BUILD_ID = "2026.11.19-pwa.2"
APP_ACCESS_KEY = os.getenv("APP_ACCESS_KEY", "").strip()
VALID_STATUSES = ["Interested", "Applied", "Assessment", "Interview", "HR Round", "Selected"]
LOCATION_GROUPS = {"preferred", "kolkata", "bengaluru", "hyderabad", "remote", "other-india"}
LOCATION_SQL = """CASE
    WHEN lower(COALESCE(location,'')) LIKE '%kolkata%' OR lower(COALESCE(location,'')) LIKE '%calcutta%' THEN 'Kolkata'
    WHEN lower(COALESCE(location,'')) LIKE '%bengaluru%' OR lower(COALESCE(location,'')) LIKE '%bangalore%' THEN 'Bengaluru'
    WHEN lower(COALESCE(location,'')) LIKE '%hyderabad%' THEN 'Hyderabad'
    WHEN lower(COALESCE(location,'')) LIKE '%remote%' OR lower(COALESCE(location,'')) LIKE '%worldwide%'
         OR lower(COALESCE(location,'')) LIKE '%anywhere%' THEN 'Remote'
    ELSE 'Other India' END"""
TRANSITION_ROLE_SQL = """(
    lower(title) LIKE '%data analyst%' OR lower(title) LIKE '%business analyst%'
    OR lower(title) LIKE '%business intelligence%' OR lower(title) LIKE '%bi analyst%'
    OR lower(title) LIKE '%power bi%' OR lower(title) LIKE '%reporting analyst%'
    OR lower(title) LIKE '%mis analyst%' OR lower(title) LIKE '%mis executive%'
    OR lower(title) LIKE '%operations analyst%' OR lower(title) LIKE '%data operations%'
    OR lower(title) LIKE '%workforce analyst%' OR lower(title) LIKE '%workforce analytics%'
    OR lower(title) LIKE '%customer insights%' OR lower(title) LIKE '%revenue analyst%'
    OR lower(title) LIKE '%process excellence%' OR lower(title) LIKE '%supply chain%analyst%'
)"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def rows(query: str, params=()) -> list[dict]:
    con = connect(); result = [dict(r) for r in con.execute(query, params).fetchall()]; con.close(); return result


def one(query: str, params=()) -> dict | None:
    con = connect(); r = con.execute(query, params).fetchone(); con.close(); return dict(r) if r else None


def add_location_group(where: list[str], params: list, location_group: str) -> None:
    """Add a normalized location filter shared by the radar, shortlist and Jarvis."""
    group = (location_group or "preferred").strip().lower()
    if group not in LOCATION_GROUPS:
        raise HTTPException(422, "Unknown location group")
    if group != "preferred":
        labels = {"kolkata": "Kolkata", "bengaluru": "Bengaluru", "hyderabad": "Hyderabad",
                  "remote": "Remote", "other-india": "Other India"}
        where.append(f"({LOCATION_SQL})=?")
        params.append(labels[group])


def transition_reason(job: dict) -> str:
    hay = f"{job.get('title','')} {job.get('description','')}".lower()
    matches = []
    for label, terms in [
        ("SQL", ("sql",)), ("Power BI", ("power bi", "dax")),
        ("Excel/reporting", ("excel", "reporting", "mis")),
        ("operations analytics", ("operations", "process excellence", "root cause")),
        ("WFM analytics", ("workforce", "forecast", "capacity planning")),
        ("Python", ("python", "pandas")),
    ]:
        if any(term in hay for term in terms):
            matches.append(label)
    evidence = ", ".join(matches[:3]) or "transferable analytics and operations experience"
    return f"Domain-switch fit: {evidence}. Verify the JD and experience requirement before applying."


def recommendation_rows(location_group: str = "preferred", role: str = "", limit: int = 20) -> list[dict]:
    """Return current, preferred transition roles; dated and realistic records rank first."""
    base_where = ["is_active=1", "excluded_reason IS NULL", TRANSITION_ROLE_SQL,
                  "(freshness_verified=1 OR source='Google Sheet Tracker')"]
    base_params: list = []
    add_location_group(base_where, base_params, location_group)
    if role:
        base_where.append("(title LIKE ? OR role_query LIKE ? OR description LIKE ?)")
        base_params += [f"%{role}%", f"%{role}%", f"%{role}%"]
    seniority = ["lower(title) NOT LIKE '%senior%'", "lower(title) NOT LIKE 'sr %'",
                 "lower(title) NOT LIKE '%director%'", "lower(title) NOT LIKE '%vice president%'",
                 "lower(title) NOT LIKE '% avp%'", "lower(title) NOT LIKE '% vp%'",
                 "lower(title) NOT LIKE '%principal%'", "lower(title) NOT LIKE '%manager%'",
                 "lower(title) NOT LIKE '%head of%'", "lower(title) NOT LIKE '%lead %'"]
    order = """freshness_verified DESC,
        CASE WHEN datetime(posted_at)>=datetime('now','-24 hours') THEN 0 ELSE 1 END,
        match_score DESC,COALESCE(posted_at,source_observed_at,last_seen_at) DESC"""
    strict_where = [*base_where, *seniority]
    data = rows(f"""SELECT *,({LOCATION_SQL}) AS location_group
        FROM live_scraped_jobs WHERE {' AND '.join(strict_where)} ORDER BY {order} LIMIT ?""",
                (*base_params, limit))
    # Sparse locations can legitimately have fewer junior/mid-level results. Fill only the
    # remaining slots with broader transition roles, while preserving truthful ranking.
    if len(data) < limit:
        seen_ids = {item['id'] for item in data}
        broader = rows(f"""SELECT *,({LOCATION_SQL}) AS location_group
            FROM live_scraped_jobs WHERE {' AND '.join(base_where)} ORDER BY {order} LIMIT ?""",
                       (*base_params, limit * 2))
        data.extend(item for item in broader if item['id'] not in seen_ids)
        data = data[:limit]
    for item in data:
        item["transition_reason"] = transition_reason(item)
    return data


def search_url(template: str, role: str, location: str) -> str:
    role_slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
    location_slug = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-")
    return template.format(role=quote(role), location=quote(location), role_slug=role_slug, location_slug=location_slug)


async def scheduler():
    """Check every five minutes and refresh public feeds hourly."""
    while True:
        await asyncio.sleep(300)
        last = one("SELECT value FROM settings WHERE key='last_scan_at'")
        interval = one("SELECT value FROM settings WHERE key='scan_interval_hours'")
        interval_seconds = float(interval["value"] if interval else 1) * 3600
        due = True
        if last and last["value"]:
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(last["value"])
                due = age.total_seconds() >= interval_seconds
            except ValueError:
                pass
        if due and not SCAN_LOCK.locked():
            await run_full_scan()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(scheduler())
    count = one("SELECT COUNT(*) AS n FROM live_scraped_jobs")
    last = one("SELECT value FROM settings WHERE key='last_scan_at'")
    due = not count or count["n"] == 0 or not last or not last["value"]
    if not due:
        try:
            due = (datetime.now(timezone.utc) - datetime.fromisoformat(last["value"])).total_seconds() >= 3600
        except ValueError:
            due = True
    if due:
        asyncio.create_task(run_full_scan())
    yield
    task.cancel()


app = FastAPI(title="Sam Career Studio", version="3.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.middleware("http")
async def optional_app_key(request: Request, call_next):
    """Protect personal APIs on a public host when APP_ACCESS_KEY is configured."""
    if APP_ACCESS_KEY and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        if request.headers.get("x-app-key", "") != APP_ACCESS_KEY:
            return JSONResponse({"detail": "App access key required"}, status_code=401)
    return await call_next(request)


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    company: str = Field(min_length=1, max_length=160)
    location: str = Field(default="", max_length=120)
    portal: str = Field(default="Direct", max_length=80)
    url: HttpUrl
    status: str = "Interested"
    notes: str = Field(default="", max_length=2000)
    live_job_id: int | None = None


class JobPatch(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=2000)


class SkillPatch(BaseModel):
    mastery: int = Field(ge=0, le=100)


class ATSRequest(BaseModel):
    job_description: str = Field(min_length=30, max_length=30000)
    job_title: str = Field(default="Target role", max_length=200)


class JarvisRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest():
    return FileResponse(BASE_DIR / "static" / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        BASE_DIR / "static" / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "build": BUILD_ID, "database": DB_PATH.exists(),
            "scanner_running": SCAN_LOCK.locked(), "access_key_required": bool(APP_ACCESS_KEY), "utc": now()}


@app.get("/api/profile")
def profile():
    record = one("SELECT data_json,updated_at FROM profile WHERE id=1")
    return {**json.loads(record["data_json"]), "updated_at": record["updated_at"]}


@app.get("/api/metrics")
def metrics():
    live = one("""SELECT COUNT(*) total,
        SUM(CASE WHEN is_active=1 AND freshness_verified=1 AND excluded_reason IS NULL
                 AND datetime(posted_at) >= datetime('now','-24 hours') THEN 1 ELSE 0 END) active,
        SUM(CASE WHEN is_active=1 AND freshness_verified=1 AND excluded_reason IS NULL THEN 1 ELSE 0 END) active_72h,
        SUM(CASE WHEN is_active=1 AND freshness_verified=0 AND excluded_reason IS NULL THEN 1 ELSE 0 END) age_unknown,
        SUM(CASE WHEN is_active=1 AND source='Google Sheet Tracker' AND excluded_reason IS NULL THEN 1 ELSE 0 END) sheet_tracked,
        SUM(CASE WHEN excluded_reason IS NOT NULL THEN 1 ELSE 0 END) excluded,
        MAX(scraped_at) last_refresh,
        ROUND(AVG(CASE WHEN is_active=1 AND freshness_verified=1 AND excluded_reason IS NULL
                       AND datetime(posted_at) >= datetime('now','-24 hours') THEN match_score END)) avg_match
        FROM live_scraped_jobs""")
    pipeline = rows("SELECT status,COUNT(*) count FROM jobs GROUP BY status")
    projects = one("SELECT COUNT(*) total,SUM(CASE WHEN source_status='reachable' THEN 1 ELSE 0 END) reachable FROM projects")
    skills = one("SELECT ROUND(AVG(mastery)) avg_mastery FROM skills")
    run = one("SELECT * FROM scanner_runs ORDER BY id DESC LIMIT 1")
    return {"live_jobs": live or {"total":0,"active":0,"last_refresh":None,"avg_match":None},
            "pipeline": {r["status"]: r["count"] for r in pipeline}, "projects": projects,
            "skill_average": skills["avg_mastery"], "last_run": run, "scanner_running": SCAN_LOCK.locked()}


@app.get("/api/portals")
def portals(role: str = "Data Analyst", location: str = "Bangalore"):
    result = rows("SELECT * FROM portals WHERE enabled=1 ORDER BY id")
    for item in result:
        item["search_url"] = search_url(item["url_template"], role, location)
        if item["name"] == "Instahyre":
            item["coverage_label"] = "Live feed · age unavailable"
            item["coverage_note"] = "Public API is current but does not expose posting dates; hidden from the strict 72-hour view."
        elif item["live_ingestion"]:
            item["coverage_label"] = "Live dated feed"
            item["coverage_note"] = "Public results are ingested with source-provided age/date."
        else:
            item["coverage_label"] = "Search launcher"
            item["coverage_note"] = "Portal blocks or does not offer an unauthenticated public listing API."
    return result


@app.get("/api/roles")
def roles():
    return rows("SELECT * FROM target_roles WHERE active=1 ORDER BY id")


@app.get("/api/jobs")
def get_jobs():
    return rows("SELECT * FROM jobs ORDER BY CASE status " + " ".join(f"WHEN '{s}' THEN {i}" for i,s in enumerate(VALID_STATUSES)) + " END, updated_at DESC")


@app.post("/api/jobs", status_code=201)
def create_job(payload: JobCreate):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(422, "Invalid pipeline status")
    existing = one("SELECT * FROM jobs WHERE url=?", (str(payload.url),))
    if existing:
        return existing
    listing_type, verified, posted, salary = "manual", 0, None, None
    if payload.live_job_id:
        live = one("SELECT * FROM live_scraped_jobs WHERE id=?", (payload.live_job_id,))
        if not live:
            raise HTTPException(404, "Live job not found")
        listing_type, verified, posted, salary = "live_import", 1, live["posted_at"], live["salary_text"]
    ts = now(); con = connect()
    cur = con.execute("""INSERT INTO jobs(title,company,location,portal,url,status,notes,listing_type,verified,
                    source_job_id,posted_at,salary_text,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (payload.title,payload.company,payload.location,payload.portal,str(payload.url),payload.status,
                     payload.notes,listing_type,verified,payload.live_job_id,posted,salary,ts,ts))
    jid = cur.lastrowid; con.commit(); con.close()
    return one("SELECT * FROM jobs WHERE id=?", (jid,))


@app.patch("/api/jobs/{job_id}")
def patch_job(job_id: int, payload: JobPatch):
    job = one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job: raise HTTPException(404, "Pipeline job not found")
    status = payload.status if payload.status is not None else job["status"]
    notes = payload.notes if payload.notes is not None else job["notes"]
    if status not in VALID_STATUSES: raise HTTPException(422, "Invalid pipeline status")
    con = connect(); con.execute("UPDATE jobs SET status=?,notes=?,updated_at=? WHERE id=?", (status,notes,now(),job_id)); con.commit(); con.close()
    return one("SELECT * FROM jobs WHERE id=?", (job_id,))


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int):
    con = connect(); cur = con.execute("DELETE FROM jobs WHERE id=?", (job_id,)); con.commit(); con.close()
    if not cur.rowcount: raise HTTPException(404, "Pipeline job not found")
    return {"deleted": True}


@app.get("/api/scraper/live")
def live_jobs(role: str = "", source: str = "", location: str = "", location_group: str = "preferred",
              min_score: int = 0, freshness: str = Query("today", pattern="^(today|verified|all_current)$"),
              sort: str = Query("fresh", pattern="^(fresh|match)$"), limit: int = Query(100, ge=1, le=500)):
    base_where = ["is_active=1", "excluded_reason IS NULL"]; base_params: list = []
    if freshness in {"today", "verified"}:
        base_where.append("freshness_verified=1")
    if freshness == "today":
        base_where.append("datetime(posted_at) >= datetime('now','-24 hours')")
    if role:
        base_where.append("(role_query LIKE ? OR title LIKE ? OR description LIKE ?)")
        base_params += [f"%{role}%", f"%{role}%", f"%{role}%"]
    if source:
        base_where.append("source=?"); base_params.append(source)
    if location:
        base_where.append("location LIKE ?"); base_params.append(f"%{location}%")
    base_where.append("match_score>=?"); base_params.append(min_score)

    # Counts deliberately ignore the selected location segment so every location chip
    # remains useful and shows how many records are available under the other filters.
    location_counts = rows(f"""SELECT ({LOCATION_SQL}) location_group,COUNT(*) count
        FROM live_scraped_jobs WHERE {' AND '.join(base_where)}
        GROUP BY ({LOCATION_SQL}) ORDER BY count DESC""", tuple(base_params))

    where = list(base_where); params = list(base_params)
    add_location_group(where, params, location_group)
    order = ("match_score DESC,COALESCE(posted_at,source_observed_at,first_seen_at) DESC" if sort == "match"
             else "freshness_verified DESC,COALESCE(posted_at,source_observed_at,first_seen_at) DESC,match_score DESC")
    total = one(f"SELECT COUNT(*) count FROM live_scraped_jobs WHERE {' AND '.join(where)}", tuple(params))["count"]
    data = rows(f"""SELECT *,({LOCATION_SQL}) AS location_group FROM live_scraped_jobs
        WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ?""", (*params, limit))

    fallback = False
    fallback_reason = None
    # Never show a misleading empty screen when the scanner is temporarily empty but the supplied
    # tracker sheet has current records. These are visibly labeled as tracker events, not fresh posts.
    if not data and freshness in {"today", "verified"} and source in {"", "Google Sheet Tracker"}:
        fallback_where = ["is_active=1", "excluded_reason IS NULL", "source='Google Sheet Tracker'", "match_score>=?"]
        fallback_params: list = [min_score]
        if role:
            fallback_where.append("(role_query LIKE ? OR title LIKE ? OR description LIKE ?)")
            fallback_params += [f"%{role}%", f"%{role}%", f"%{role}%"]
        if location:
            fallback_where.append("location LIKE ?"); fallback_params.append(f"%{location}%")
        add_location_group(fallback_where, fallback_params, location_group)
        total = one(f"SELECT COUNT(*) count FROM live_scraped_jobs WHERE {' AND '.join(fallback_where)}",
                    tuple(fallback_params))["count"]
        data = rows(f"""SELECT *,({LOCATION_SQL}) AS location_group FROM live_scraped_jobs
            WHERE {' AND '.join(fallback_where)}
            ORDER BY datetime(source_observed_at) DESC,match_score DESC LIMIT ?""", (*fallback_params, limit))
        fallback = bool(data)
        if fallback:
            fallback_reason = ("No source-dated vacancies matched these filters. Showing deduplicated Google Sheet "
                               "tracker records instead; their timestamps are application/tracker events, not posting dates.")
            location_counts = rows(f"""SELECT ({LOCATION_SQL}) location_group,COUNT(*) count
                FROM live_scraped_jobs WHERE is_active=1 AND excluded_reason IS NULL
                AND source='Google Sheet Tracker' AND match_score>=?
                GROUP BY ({LOCATION_SQL}) ORDER BY count DESC""", (min_score,))

    if fallback:
        source_counts = [{"source": "Google Sheet Tracker", "count": len(data)}]
        freshness_label = "Tracker fallback · posting age unavailable"
    else:
        source_counts = rows(f"""SELECT source,COUNT(*) count FROM live_scraped_jobs
            WHERE {' AND '.join(where)} GROUP BY source ORDER BY count DESC""", tuple(params))
        freshness_label = {"today": "Posted in the past 24 hours", "verified": "Source-dated within 72 hours",
                           "all_current": "Current source results; undated listings explicitly labeled"}[freshness]
    return {"items": data, "count": total, "returned": len(data), "source_counts": source_counts,
            "location_counts": location_counts, "selected_location": location_group,
            "freshness": freshness_label, "fallback": fallback, "fallback_reason": fallback_reason,
            "integrity_note": "Call-centre/BPO-process roles are excluded. Default results were posted in the past 24 hours; the 72-hour view is optional. Always verify availability on the original page.",
            "score_note": "Profile match is a transparent capability relevance heuristic. Salary is not used as a filter or score."}


@app.get("/api/recommendations")
def recommendations(location_group: str = "preferred", role: str = "", limit: int = Query(20, ge=20, le=60)):
    items = recommendation_rows(location_group=location_group, role=role, limit=limit)
    counts = rows(f"""SELECT ({LOCATION_SQL}) location_group,COUNT(*) count
        FROM live_scraped_jobs WHERE is_active=1 AND excluded_reason IS NULL
        AND {TRANSITION_ROLE_SQL} AND (freshness_verified=1 OR source='Google Sheet Tracker')
        GROUP BY ({LOCATION_SQL}) ORDER BY count DESC""")
    dated = sum(1 for item in items if item.get("freshness_verified"))
    return {"items": items, "count": len(items), "location_counts": counts,
            "selected_location": location_group, "dated_count": dated,
            "note": "A live domain-transition shortlist derived from current source records. Tracker-only rows are visibly labeled and never presented as freshly posted."}


@app.post("/api/jarvis")
async def jarvis(payload: JarvisRequest):
    """No-cost voice/text command assistant backed by the live local job database."""
    query = re.sub(r"\s+", " ", payload.query.strip().lower())
    location_group = "preferred"
    for tokens, group in [
        (("kolkata", "calcutta"), "kolkata"), (("bangalore", "bengaluru"), "bengaluru"),
        (("hyderabad",), "hyderabad"), (("remote", "work from home", "wfh"), "remote"),
        (("other india", "india wide", "anywhere in india"), "other-india"),
    ]:
        if any(token in query for token in tokens):
            location_group = group; break

    role = ""
    role_map = [
        (("power bi", "dax"), "Power BI"), (("business intelligence", "bi analyst"), "Business Intelligence"),
        (("business analyst",), "Business Analyst"), (("mis", "reporting"), "Reporting Analyst"),
        (("operations analyst",), "Operations Analyst"), (("workforce", "wfm"), "Workforce Analytics"),
        (("customer insight",), "Customer Insights"), (("revenue",), "Revenue Analyst"),
        (("data operations",), "Data Operations"), (("supply chain",), "Supply Chain"),
        (("data analyst", "analytics job"), "Data Analyst"),
    ]
    for terms, value in role_map:
        if any(term in query for term in terms):
            role = value; break

    if any(term in query for term in ("refresh", "sync", "update jobs", "scan now")):
        if not SCAN_LOCK.locked():
            asyncio.create_task(run_full_scan())
            message = "I started a live source refresh. The radar and shortlist will update when it completes."
        else:
            message = "A live source refresh is already running. I will use its results when it completes."
        return {"message": message, "action": "refresh_jobs", "jobs": [], "location_group": location_group, "role": role}
    if "roadmap" in query or "learn" in query or "study plan" in query:
        return {"message": "Opening your Data Analyst roadmap. Completed items are saved on this device.",
                "action": "show_roadmap", "jobs": [], "location_group": location_group, "role": role}
    if "pipeline" in query or "application" in query or "crm" in query:
        return {"message": "Opening the application pipeline and live 20-job transition shortlist.",
                "action": "show_pipeline", "jobs": [], "location_group": location_group, "role": role}
    if "ats" in query or "resume match" in query:
        return {"message": "Opening the ATS matcher. Paste the real job description for an evidence-based comparison.",
                "action": "show_ats", "jobs": [], "location_group": location_group, "role": role}

    items = recommendation_rows(location_group=location_group, role=role, limit=20)
    label = {"preferred": "your preferred locations", "kolkata": "Kolkata", "bengaluru": "Bengaluru",
             "hyderabad": "Hyderabad", "remote": "remote", "other-india": "other Indian locations"}[location_group]
    role_text = f" {role}" if role else " domain-transition"
    message = (f"I found {len(items)} current{role_text} jobs for {label}. "
               "I ranked source-dated roles first and excluded call-centre, voice, chat-support and BPO-process work.")
    return {"message": message, "action": "filter_jobs", "jobs": items,
            "result_count": len(items), "location_group": location_group, "role": role}


@app.post("/api/scraper/scan", status_code=202)
async def trigger_scan():
    if SCAN_LOCK.locked():
        return {"status": "already_running"}
    asyncio.create_task(run_full_scan())
    return {"status": "started", "message": "Public-source refresh started in the background."}


@app.get("/api/scraper/status")
def scanner_status():
    return {"running": SCAN_LOCK.locked(), "last_run": one("SELECT * FROM scanner_runs ORDER BY id DESC LIMIT 1"),
            "schedule": "Hourly; scheduler checks every 5 minutes", "freshness_window": "72 hours",
            "filters": {"call_center_and_bpo_process": "excluded", "salary_cap": "none", "alert_mode": "dashboard only"},
            "coverage": {
                "target_portals": 10,
                "live_target_portals": ["LinkedIn public results", "Naukri public results", "Indeed India public results", "Glassdoor India public results", "Shine public results", "Instahyre public API (age not supplied)"],
                "supplemental_public_feeds": ["Public Google Job Application Tracker (posting age unavailable)", "Direct employer Lever/Greenhouse boards", "Remotive", "Jobicy", "Arbeitnow", "RemoteOK", "Himalayas"],
                "search_only_portals": ["Foundit", "Cutshort", "Wellfound", "SimplyHired India"],
                "why_search_only": "These sites currently block unattended access or provide no unauthenticated public dated-listings API. No login/CAPTCHA bypass is attempted."
            }}


@app.get("/api/projects")
def projects(category: str = ""):
    if category:
        return rows("SELECT * FROM projects WHERE category=? ORDER BY id", (category,))
    return rows("SELECT * FROM projects ORDER BY id")


@app.get("/api/project-trends")
def project_trends():
    return {"items": rows("SELECT * FROM project_trends ORDER BY datetime(updated_at) DESC LIMIT 12"),
            "note": "Recently updated public GitHub repositories are inspiration signals, not evidence that a project is asked in interviews."}


@app.get("/api/skills")
def skills(): return rows("SELECT * FROM skills ORDER BY category,name")


@app.patch("/api/skills/{skill_id}")
def update_skill(skill_id: int, payload: SkillPatch):
    con=connect(); cur=con.execute("UPDATE skills SET mastery=?,updated_at=? WHERE id=?", (payload.mastery,now(),skill_id)); con.commit(); con.close()
    if not cur.rowcount: raise HTTPException(404, "Skill not found")
    return one("SELECT * FROM skills WHERE id=?", (skill_id,))


@app.get("/api/interview")
def interview(category: str = "", difficulty: str = ""):
    where=[]; params=[]
    if category: where.append("category=?"); params.append(category)
    if difficulty: where.append("difficulty=?"); params.append(difficulty)
    clause = " WHERE " + " AND ".join(where) if where else ""
    return rows("SELECT * FROM interview_qna" + clause + " ORDER BY RANDOM()", params)


@app.post("/api/ats_match")
def ats_match(payload: ATSRequest):
    """Return a deterministic, JD-specific and explainable profile comparison."""
    jd = re.sub(r"\s+", " ", payload.job_description.lower()).strip()
    context = f"{payload.job_title.lower()} {jd}"
    # (search terms, importance, candidate evidence level 0..1)
    taxonomy = {
        "SQL": (["sql", "cte", "window function", "query optimization", "stored procedure"], 5, 1.0),
        "Power BI": (["power bi", "powerbi", "dax"], 5, 1.0),
        "Power Query": (["power query", "m language"], 3, 1.0),
        "Advanced Excel": (["advanced excel", "pivot table", "xlookup", "vba", "macros"], 4, 1.0),
        "Python": (["python", "pandas"], 4, .85),
        "Machine Learning": (["machine learning", "scikit-learn", "classification", "regression model"], 3, .65),
        "ETL": (["etl", "data pipeline", "data ingestion", "data transformation"], 4, .8),
        "Data Modeling": (["data model", "dimensional model", "star schema", "data warehouse"], 4, .9),
        "WFM": (["wfm", "workforce management", "erlang", "shrinkage", "occupancy"], 5, 1.0),
        "SLA / AHT": (["service level", "sla", "aht", "average handling time"], 4, 1.0),
        "Forecasting": (["forecasting", "forecast", "capacity planning"], 3, .85),
        "Reporting & KPIs": (["reporting", "dashboard", "kpi", "business insights", "data analysis", "analytics"], 5, 1.0),
        "Operations Analytics": (["operations analytics", "operational analysis", "process excellence", "root cause"], 4, .9),
        "Stakeholder Management": (["stakeholder", "cross-functional", "presentation", "communication"], 3, .8),
        "Statistics": (["statistics", "hypothesis testing", "a/b test", "statistical analysis"], 3, .7),
        "Tableau": (["tableau"], 3, 0.0),
        "Looker": (["looker", "lookml"], 3, 0.0),
        "Cloud": (["aws", "azure", "gcp", "cloud platform"], 4, 0.0),
        "Snowflake": (["snowflake"], 4, 0.0),
        "Databricks / Spark": (["databricks", "pyspark", "apache spark"], 4, 0.0),
        "dbt": (["dbt", "data build tool"], 3, 0.0),
        "Airflow": (["airflow", "orchestration"], 3, 0.0),
        "R": ([" r programming", " r language", "rstudio"], 2, 0.0),
        "SAS": (["sas programming", " sas "], 2, 0.0),
        "Git": (["git", "github", "version control"], 2, 0.0),
        "Agile / Jira": (["agile", "scrum", "jira"], 2, .4),
    }
    detected: list[tuple[str, int, float, list[str]]] = []
    for label, (terms, weight, evidence) in taxonomy.items():
        hits = [term.strip() for term in terms if term in f" {context} "]
        if hits:
            detected.append((label, weight, evidence, hits))

    total_weight = sum(item[1] for item in detected)
    earned_weight = sum(weight * evidence for _, weight, evidence, _ in detected)
    skill_coverage = round(100 * earned_weight / total_weight) if total_weight else 35
    matched = [label for label, _, evidence, _ in detected if evidence >= .65]
    partial = [label for label, _, evidence, _ in detected if 0 < evidence < .65]
    missing = [label for label, _, evidence, _ in detected if evidence == 0]

    preferred_roles = ["data analyst", "business intelligence", "bi analyst", "operations analyst",
                       "reporting analyst", "mis analyst", "customer insights", "revenue analyst",
                       "data operations", "process excellence", "wfm analyst", "workforce management"]
    broader_roles = ["analyst", "analytics", "reporting", "operations", "data"]
    call_center_terms = ["call center", "call centre", "contact center", "contact centre", "voice process",
                         "chat process", "bpo", "bpo process", "telecaller", "telecalling", "customer support executive",
                         "customer service executive", "process associate"]
    excluded_role = next((term for term in call_center_terms if term in context), None)
    if any(term in context[:1200] for term in preferred_roles):
        role_alignment = 95
    elif any(term in context[:1200] for term in broader_roles):
        role_alignment = 70
    else:
        role_alignment = 35
    if excluded_role:
        role_alignment = 0

    number_words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
    experience_text = context
    for word, digit in number_words.items():
        experience_text = re.sub(rf"\b{word}\b", digit, experience_text)
    experience_values = [float(value) for value in re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:\+|to|-)?\s*(?:\d+(?:\.\d+)?)?\s*(?:years|yrs)\b", experience_text
    )]
    required_years = max(experience_values) if experience_values else None
    if required_years is None:
        experience_alignment = 70
    elif required_years <= 2.5:
        experience_alignment = 100
    elif required_years <= 3:
        experience_alignment = 85
    elif required_years <= 4:
        experience_alignment = 60
    elif required_years <= 6:
        experience_alignment = 30
    else:
        experience_alignment = 10

    score = round(skill_coverage * .65 + role_alignment * .25 + experience_alignment * .10)
    if excluded_role:
        score = min(score, 15)
    score = max(1, min(score, 96))

    bullet_library = {
        "SQL": "Used advanced SQL—including CTEs and window functions—to analyze operational data and produce decision-ready reporting; add a verified scale and outcome.",
        "Power BI": "Built Power BI models and DAX measures around clearly defined KPIs; insert a truthful adoption, latency or decision-impact result.",
        "Advanced Excel": "Automated repeatable Excel analysis with Power Query and advanced formulas; add the verified manual-effort reduction.",
        "Python": "Used Python and Pandas for reproducible data preparation, validation and analysis; quantify only an outcome you can evidence.",
        "ETL": "Created controlled ETL steps with reconciliation and quality checks so reporting inputs remained traceable; add a verified refresh or error-rate result.",
        "Data Modeling": "Structured reporting data using dimensional-modeling principles to simplify KPI analysis and filter behavior; add a defensible business result.",
        "WFM": "Analyzed workload, AHT, shrinkage, occupancy and service-level drivers to support workforce decisions; add a verified planning impact.",
        "SLA / AHT": "Tracked SLA and AHT with documented definitions and interval-level root-cause analysis; add a measured improvement only if supported by records.",
        "Forecasting": "Compared forecast demand with actual outcomes and investigated variance drivers; insert a verified accuracy or planning result.",
        "Reporting & KPIs": "Converted operational data into governed KPI reporting and concise stakeholder insights; add the decision and verified outcome.",
        "Operations Analytics": "Investigated operational exceptions and root causes, then translated findings into an actionable process recommendation; add a verified result.",
        "Stakeholder Management": "Presented decision-focused analysis to cross-functional stakeholders, documenting assumptions, limitations and next actions.",
    }
    bullets = [bullet_library[label] for label in matched if label in bullet_library][:4]
    if not bullets:
        bullets = ["Use a profile summary focused on transferable analytics, operations and reporting evidence; do not add tools or results that cannot be verified."]

    fingerprint = hashlib.sha256(f"{payload.job_title}|{jd}".encode()).hexdigest()[:10]
    return {
        "analysis_id": fingerprint, "scoring_version": "profile-jd-v3", "score": score,
        "breakdown": {"skill_coverage": skill_coverage, "role_alignment": role_alignment,
                      "experience_alignment": experience_alignment},
        "formula": "65% detected skill coverage + 25% target-role alignment + 10% experience alignment",
        "candidate_baseline": {"experience_years": 2.5,
                               "skills_source": "Saved profile and skills matrix; no unstated skill receives full credit"},
        "matched": matched, "partial": partial, "missing": missing,
        "required_detected": [label for label, *_ in detected],
        "detected_evidence": {label: hits for label, _, _, hits in detected},
        "tailored_bullets": bullets,
        "learning_priorities": missing[:4],
        "eligibility_warning": f"This description matches your excluded call-centre/BPO category ('{excluded_role}')." if excluded_role else None,
        "required_years": required_years,
        "disclaimer": "This is a JD-specific, explainable profile comparison—not an employer ATS score. It uses only Sam's stated skills; every result or metric must be replaced with verified evidence."
    }


@app.get("/api/export/jobs.csv")
def export_jobs():
    data = rows("SELECT title,company,location,portal,status,url,listing_type,verified,posted_at,updated_at,notes FROM jobs ORDER BY updated_at DESC")
    output=io.StringIO(); writer=csv.DictWriter(output, fieldnames=list(data[0].keys()) if data else ["title"]); writer.writeheader(); writer.writerows(data)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=sam-career-pipeline.csv"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
