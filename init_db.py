"""Initialize Sam Career Studio's SQLite database.

Safe to run repeatedly: schema migrations and seed inserts are idempotent.
All seeded pipeline records are explicitly marked as search leads, not as live vacancies.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "career_engine.db"
NOW = datetime.now(timezone.utc).isoformat()

PROFILE = {
    "full_name": "Soumyadip Sarkar (Sam)",
    "professional_title": "Data & WFM Analytics Lead | BI Specialist",
    "phone": "6363793581",
    "email": "soumyadipsarkar2106@gmail.com",
    "experience": "2.5+ Years in Contact Center Operations & BPO Analytics (Startek, Alorica, Teleperformance)",
    "target_ctc": "INR 8.5 LPA - 12.0 LPA",
    "locations": ["Bangalore", "Kolkata", "Hyderabad", "Remote"],
    "core_stack": ["Advanced SQL", "Power BI", "WFM", "Python", "Advanced Excel"],
}

# Domain-transition roles grounded in Sam's analytics/reporting skills and transferable
# operations experience. Voice, support-process, call-centre and generic BPO roles are
# deliberately not target roles.
ROLES = [
    "Data Analyst", "Junior Data Analyst", "Business Data Analyst", "Operations Analyst",
    "Business Analyst", "MIS Analyst / MIS Executive", "Reporting Analyst",
    "Business Intelligence Analyst", "Power BI Analyst", "Data Operations Analyst",
    "Workforce Analytics Analyst", "Process Excellence Analyst", "Customer Insights Analyst",
    "Revenue Analyst", "Supply Chain Data Analyst", "CX Analytics Analyst",
]

PORTALS = [
    ("LinkedIn", "https://www.linkedin.com/jobs/search/?keywords={role}&location={location}", "linkedin", 1),
    ("Naukri", "https://www.naukri.com/{role_slug}-jobs-in-{location_slug}", "jobspy", 1),
    ("Indeed India", "https://in.indeed.com/jobs?q={role}&l={location}", "jobspy", 1),
    ("Instahyre", "https://www.instahyre.com/search-jobs/?skills={role}", "instahyre", 1),
    ("Foundit", "https://www.foundit.in/srp/results?query={role}&locations={location}", "search", 0),
    ("Glassdoor India", "https://www.glassdoor.co.in/Job/india-{role_slug}-jobs-SRCH_IL.0,5_IN115_KO6.htm", "jobspy", 1),
    ("Cutshort", "https://cutshort.io/jobs/{role_slug}-jobs", "search", 0),
    ("Wellfound", "https://wellfound.com/jobs?q={role}", "search", 0),
    ("Shine", "https://www.shine.com/job-search/{role_slug}-jobs-in-{location_slug}", "shine", 1),
    ("SimplyHired India", "https://www.simplyhired.co.in/search?q={role}&l={location}", "search", 0),
]

PROJECTS = [
    ("Automated Multi-Portal Job Scraper", "Automation", "https://www.kaggle.com/datasets/arshkon/linkedin-job-postings", "Build an ethical, source-aware ingestion pipeline with deduplication, freshness checks and observability."),
    ("Enterprise Pharma Commercial Sales", "Sales BI", "https://www.kaggle.com/datasets/milanzdravkovic/pharma-sales-data", "Model regional product performance, forecast variance and rep-level commercial effectiveness."),
    ("Global Streaming Media Catalog EDA", "Product Analytics", "https://www.kaggle.com/datasets/shivamb/netflix-shows", "Analyze catalog mix, release lag, country coverage and genre portfolio trends."),
    ("Telecom Predictive Churn & LTV", "Machine Learning", "https://www.kaggle.com/datasets/blastchar/telco-customer-churn", "Prioritize retention with calibrated churn propensity and customer lifetime value segments."),
    ("High-Volume BPO SLA, AHT & Concurrency", "WFM", "https://www.kaggle.com/datasets/komalkomal7/call-center-workforce-dataset-wfo-aht-kpi", "Create interval-level capacity, SLA, AHT and Erlang-C decision intelligence."),
    ("Multi-Channel E-Commerce Cohort Retention", "Customer Analytics", "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce", "Build acquisition cohorts, repeat-rate curves and contribution-margin retention views."),
    ("Autonomous AI Gmail Job Classifier", "NLP Automation", "https://www.kaggle.com/datasets/isuranga/spammalicious-detection", "Classify recruiting email intent with human review, confidence thresholds and audit logs."),
    ("Corporate HR Attrition & Equity", "People Analytics", "https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset", "Explain attrition patterns while monitoring fairness and avoiding causal overclaims."),
    ("Real-Time Equities Volatility & VaR", "Risk Analytics", "https://www.kaggle.com/datasets/camnugent/sandp500", "Calculate rolling volatility, historical VaR and breach monitoring for a market-risk dashboard."),
    ("Supply Chain Fulfillment SLA & Delay Root-Cause", "Operations", "https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis", "Quantify late-delivery drivers and build lane, carrier and product exception workflows."),
    ("Contact Center FCR & CSAT Driver Engine", "CX Analytics", "https://www.kaggle.com/datasets/gayatriwagadre/pwc-call-centre-analysis", "Find operational drivers of resolution and CSAT with statistically responsible segmentation."),
    ("B2B Enterprise SaaS Sales Velocity", "Revenue Operations", "https://www.kaggle.com/datasets/kyanyoga/sample-sales-data", "Track funnel conversion, aging, sales cycle and weighted pipeline velocity."),
    ("ML Propensity Lead Scoring Engine", "Machine Learning", "https://www.kaggle.com/datasets/amritachatterjee09/lead-scoring-dataset", "Deploy an explainable lead score with lift, calibration and drift monitoring."),
    ("PDF Invoice Extraction & Reconciliation", "Document AI", "https://www.kaggle.com/datasets/devp1866/high-quality-ocr-ready-invoice-pdfs", "Extract invoice fields, validate totals and reconcile records with exception queues."),
    ("SQL Query Optimization & Profiler", "Data Engineering", "https://www.kaggle.com/datasets/stackoverflow/stacksample", "Diagnose query plans, indexing trade-offs and latency regressions with reproducible benchmarks."),
    ("Multi-Exchange FX Arbitrage & Slippage", "Quant Analytics", "https://www.kaggle.com/datasets/dhruvildave/currency-exchange-rates", "Separate theoretical spreads from executable opportunities after fees, latency and slippage."),
]

SKILLS = [
    ("Advanced SQL", "Data", 86, "Window functions, CTEs, indexing, query plans"),
    ("Power BI & DAX", "BI", 84, "Star schema, measures, RLS, performance analyzer"),
    ("WFM Analytics", "Operations", 88, "Erlang-C, AHT, shrinkage, occupancy, SLA"),
    ("Python / Pandas", "Data", 76, "ETL, validation, APIs, scikit-learn"),
    ("Advanced Excel", "BI", 90, "Power Query, pivots, dynamic arrays, VBA"),
    ("Statistics", "Analytics", 70, "Experiments, uncertainty, regression diagnostics"),
    ("Data Storytelling", "Leadership", 80, "Executive narratives, decision-first dashboards"),
    ("Data Engineering", "Data", 66, "Orchestration, data quality, dimensional modeling"),
]

QNA = [
    ("SQL", "Intermediate", "How would you return the latest status for every application?", "Use ROW_NUMBER() over PARTITION BY application_id ORDER BY status_timestamp DESC, then filter rn = 1. Resolve timestamp ties with a deterministic event_id and index the partition/order keys."),
    ("SQL", "Advanced", "A dashboard query regressed from 4 seconds to 90 seconds. How do you investigate?", "Capture the actual execution plan, compare row estimates with actuals, check blocking and parameter sensitivity, inspect scans/sorts/spills, validate statistics, and benchmark a targeted index or query rewrite before deployment."),
    ("Power BI", "Intermediate", "Why prefer a star schema over one wide table?", "A star schema gives predictable filter propagation, reusable dimensions, smaller dictionaries, clearer grain, and simpler DAX. Define fact grain first and keep relationships single-direction unless a tested exception requires otherwise."),
    ("Power BI", "Advanced", "Explain row context versus filter context in DAX.", "Row context identifies a current row in iterators or calculated columns. Filter context constrains the model before evaluation. CALCULATE modifies filter context and performs context transition when row context exists."),
    ("WFM", "Intermediate", "How do AHT and shrinkage affect staffing?", "Higher AHT raises workload and required staffed hours. Shrinkage converts net requirement into scheduled headcount: scheduled = net / (1 - shrinkage). Reforecast both by interval rather than applying only daily averages."),
    ("WFM", "Advanced", "Why can two intervals with equal workload have different SLA?", "Arrival shape, staffing discreteness, occupancy, queue carryover and service-time distribution matter. Erlang-C also assumes Poisson arrivals, exponential handling and no abandonment, so compare it with actual interval behavior."),
    ("Python", "Intermediate", "How would you make an ETL pipeline idempotent?", "Use stable business keys, deterministic transforms, upserts or partition replacement, source checkpoints, schema and quality assertions, and a run ledger. Re-running the same input should produce the same state."),
    ("Analytics", "Advanced", "A model shows churn correlation with support calls. Can you recommend reducing calls?", "No. Calls may be a symptom of product issues or reverse causality. Control for tenure and product, inspect call reasons and timing, use a causal design where possible, and test an intervention before claiming impact."),
    ("Architecture", "Advanced", "Design a daily multi-source job radar.", "Use source adapters with policy-aware access, normalized canonical fields, URL and content-hash deduplication, UTC timestamps, exponential backoff, run-level observability, freshness expiry and provenance visible to users. Keep search launchers separate from verified listings."),
    ("Behavioral", "Intermediate", "Tell me about a dashboard that changed an operation.", "Structure the answer as situation, decision, action, measurable result and learning. State the baseline, the metric definition, your specific contribution, stakeholder adoption, and any limitation rather than inventing precision."),
]


def project_guides(title: str, category: str) -> dict[str, str]:
    blueprints = {
        "Automated Multi-Portal Job Scraper": ("source + external_job_id + scraped_at", "scraped_at", "source", "match_score", "fresh active listings, dedupe rate and source success"),
        "Enterprise Pharma Commercial Sales": ("sale date + product/category", "sale_date", "product_category", "quantity", "unit volume, rolling demand and forecast variance"),
        "Global Streaming Media Catalog EDA": ("one title / show_id", "date_added", "genre", "release_year", "catalog additions, release lag and country coverage"),
        "Telecom Predictive Churn & LTV": ("one customer at snapshot", "snapshot_date", "contract_type", "monthly_charges", "churn rate, calibrated risk and expected LTV"),
        "High-Volume BPO SLA, AHT & Concurrency": ("date + interval + queue", "interval_start", "queue", "offered_contacts", "service level, AHT, occupancy and required FTE"),
        "Multi-Channel E-Commerce Cohort Retention": ("one order / order_id", "purchase_timestamp", "customer_cohort", "payment_value", "repeat rate, cohort retention and contribution value"),
        "Autonomous AI Gmail Job Classifier": ("one message / message_id", "ingested_at", "predicted_intent", "model_confidence", "precision, recall, review rate and classification latency"),
        "Corporate HR Attrition & Equity": ("one employee at snapshot", "snapshot_date", "department", "monthly_income", "attrition rate, pay distribution and fairness diagnostics"),
        "Real-Time Equities Volatility & VaR": ("symbol + trading date", "trade_date", "symbol", "adjusted_close", "returns, rolling volatility, historical VaR and breaches"),
        "Supply Chain Fulfillment SLA & Delay Root-Cause": ("order + line item", "order_date", "shipping_mode", "sales", "late-delivery rate, cycle time and exception value"),
        "Contact Center FCR & CSAT Driver Engine": ("one contact / call_id", "contact_date", "agent_or_topic", "csat_score", "resolution rate, CSAT and repeat-contact proxy when supported"),
        "B2B Enterprise SaaS Sales Velocity": ("one opportunity / opportunity_id", "close_date", "stage", "deal_amount", "conversion, stage aging, win rate and pipeline velocity"),
        "ML Propensity Lead Scoring Engine": ("one lead at scoring time", "scored_at", "lead_source", "propensity_score", "lift, calibration, precision at capacity and drift"),
        "PDF Invoice Extraction & Reconciliation": ("document hash + invoice number", "invoice_date", "vendor", "invoice_total", "field accuracy, reconciliation variance and straight-through rate"),
        "SQL Query Optimization & Profiler": ("query hash + execution id", "executed_at", "query_family", "duration_ms", "p50/p95 latency, scan volume, spills and regression rate"),
        "Multi-Exchange FX Arbitrage & Slippage": ("timestamp + pair + venue", "quote_timestamp", "currency_pair", "mid_price", "gross spread, fees, net spread and executable slippage"),
    }
    grain, date_col, segment, metric, kpis = blueprints[title]
    excel = f"""GOAL
Build a decision-ready {title} workbook.

BUSINESS GRAIN
{grain}

CORE KPI LAYER
{kpis}

1. Load raw files with Power Query and preserve an immutable raw query.
2. Profile nulls, duplicates, type failures and the coverage of {date_col}.
3. Confirm the grain before removing duplicates; document every rule.
4. Build a Date table and a controlled {segment} dimension.
5. Reconcile the curated {metric} total to the source before charting.
6. Add exception views, refresh timestamp and metric definitions.
7. Progression: pivots -> Power Pivot measures -> automated refresh.

INTERVIEW DEFENCE
Explain the grain, one quality defect, one trade-off, the decision enabled,
and why the analysis is associative unless a causal design supports more."""
    dax = f"""-- {title}
-- Canonical model after mapping raw columns:
-- DimDate / DimSegment -> FactEvents at grain: {grain}
Records = COUNTROWS(FactEvents)
Total Value = SUM(FactEvents[MetricValue])  -- map from: {metric}
Average Value = DIVIDE([Total Value], [Records])
Valid Records = CALCULATE([Records], FactEvents[IsValid] = TRUE())
Quality Rate = DIVIDE([Valid Records], [Records])
Prior Month Value = CALCULATE([Total Value], DATEADD(DimDate[Date], -1, MONTH))
MoM Change % = DIVIDE([Total Value] - [Prior Month Value], [Prior Month Value])
Rolling 30D Value = CALCULATE(
    [Total Value], DATESINPERIOD(DimDate[Date], MAX(DimDate[Date]), -30, DAY)
)
Segment Share % = DIVIDE(
    [Total Value], CALCULATE([Total Value], REMOVEFILTERS(DimSegment))
)

-- KPI target: {kpis}.
-- Keep relationships single-direction and mark a proper Date table."""
    sql = f"""-- Production SQL blueprint: {title}
-- Map event_ts <- {date_col}; category <- {segment}; metric_value <- {metric}.
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY business_key ORDER BY updated_at DESC, ingest_id DESC
  ) AS version_rank
  FROM staging_events
), validated AS (
  SELECT *, CASE
    WHEN business_key IS NULL OR event_ts IS NULL OR metric_value IS NULL THEN 0
    ELSE 1 END AS is_valid
  FROM ranked WHERE version_rank = 1
), daily AS (
  SELECT CAST(event_ts AS DATE) AS event_date, category,
         COUNT(*) AS records,
         SUM(metric_value) AS total_value,
         SUM(is_valid) AS valid_records
  FROM validated
  GROUP BY CAST(event_ts AS DATE), category
)
SELECT event_date, category, records, total_value,
       1.0 * valid_records / NULLIF(records, 0) AS quality_rate,
       AVG(total_value) OVER (
         PARTITION BY category ORDER BY event_date
         ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
       ) AS value_7d_avg
FROM daily;

-- Benchmark first. Index proven filter/join paths; verify with the actual plan."""
    python = f'''"""Reproducible starter: {title}
Expected analytical grain: {grain}
"""
from pathlib import Path
import json
import pandas as pd

INPUT = Path("data/raw.csv")
OUTPUT = Path("data/curated.parquet")
REPORT = Path("data/quality_report.json")

df = pd.read_csv(INPUT)
assert not df.empty, "Source is empty"
df.columns = (df.columns.str.strip().str.lower()
              .str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_"))

expected = ["{date_col}", "{segment}", "{metric}"]
missing = [column for column in expected if column not in df.columns]
if missing:
    raise ValueError(f"Map dataset columns to canonical fields before modeling: {{missing}}")

df["{date_col}"] = pd.to_datetime(df["{date_col}"], errors="coerce", utc=True)
df["{metric}"] = pd.to_numeric(df["{metric}"], errors="coerce")
# Replace only after proving the business key from the dataset documentation.
business_key = [df.columns[0]]
df = df.sort_values("{date_col}").drop_duplicates(business_key, keep="last")

quality = {{
    "rows": len(df),
    "date_min": str(df["{date_col}"].min()),
    "date_max": str(df["{date_col}"].max()),
    "duplicate_keys": int(df.duplicated(business_key).sum()),
    "null_rate_top10": df.isna().mean().nlargest(10).to_dict(),
}}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(OUTPUT, index=False)
REPORT.write_text(json.dumps(quality, indent=2, default=str))
print(quality)
'''
    return {"excel_guide": excel, "powerbi_dax": dax, "production_sql": sql, "python_script": python}


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db() -> None:
    con = connect()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS profile (
      id INTEGER PRIMARY KEY CHECK (id=1), data_json TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS portals (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, url_template TEXT NOT NULL,
      adapter TEXT NOT NULL DEFAULT 'search', live_ingestion INTEGER NOT NULL DEFAULT 0,
      enabled INTEGER NOT NULL DEFAULT 1, last_status TEXT DEFAULT 'not_checked', last_checked_at TEXT
    );
    CREATE TABLE IF NOT EXISTS target_roles (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS jobs (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, company TEXT NOT NULL, location TEXT,
      portal TEXT, url TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Interested', salary_text TEXT,
      posted_at TEXT, notes TEXT DEFAULT '', listing_type TEXT NOT NULL DEFAULT 'search_lead',
      verified INTEGER NOT NULL DEFAULT 0, source_job_id INTEGER, created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS live_scraped_jobs (
      id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, external_id TEXT, title TEXT NOT NULL,
      company TEXT, location TEXT, role_query TEXT, description TEXT, url TEXT NOT NULL UNIQUE,
      posted_at TEXT, source_observed_at TEXT, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, scraped_at TEXT NOT NULL,
      match_score INTEGER DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, provenance TEXT,
      salary_text TEXT, employment_type TEXT, freshness_verified INTEGER NOT NULL DEFAULT 0,
      fit_tier TEXT DEFAULT 'Explore', excluded_reason TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_live_role ON live_scraped_jobs(role_query, match_score DESC);
    CREATE INDEX IF NOT EXISTS idx_live_seen ON live_scraped_jobs(last_seen_at DESC);
    CREATE TABLE IF NOT EXISTS projects (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT UNIQUE NOT NULL, category TEXT NOT NULL,
      dataset_url TEXT NOT NULL, objective TEXT NOT NULL, excel_guide TEXT NOT NULL,
      powerbi_dax TEXT NOT NULL, production_sql TEXT NOT NULL, python_script TEXT NOT NULL,
      difficulty TEXT DEFAULT 'Intermediate', source_status TEXT DEFAULT 'not_checked',
      source_checked_at TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS project_trends (
      id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, external_id TEXT NOT NULL,
      title TEXT NOT NULL, description TEXT, url TEXT NOT NULL, stars INTEGER DEFAULT 0,
      language TEXT, updated_at TEXT, fetched_at TEXT NOT NULL, UNIQUE(source, external_id)
    );
    CREATE TABLE IF NOT EXISTS skills (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, category TEXT NOT NULL,
      mastery INTEGER NOT NULL CHECK(mastery BETWEEN 0 AND 100), evidence TEXT, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS interview_qna (
      id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, difficulty TEXT NOT NULL,
      question TEXT UNIQUE NOT NULL, answer TEXT NOT NULL, source TEXT DEFAULT 'curated',
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS scanner_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, completed_at TEXT,
      status TEXT NOT NULL, sources_attempted INTEGER DEFAULT 0, sources_succeeded INTEGER DEFAULT 0,
      jobs_seen INTEGER DEFAULT 0, jobs_new INTEGER DEFAULT 0, error_log TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    """)
    # Lightweight forward-only migrations for databases created by earlier builds.
    live_columns = {row[1] for row in con.execute("PRAGMA table_info(live_scraped_jobs)")}
    for name, definition in {
        "freshness_verified": "INTEGER NOT NULL DEFAULT 0",
        "fit_tier": "TEXT DEFAULT 'Explore'",
        "excluded_reason": "TEXT",
        "source_observed_at": "TEXT",
    }.items():
        if name not in live_columns:
            con.execute(f"ALTER TABLE live_scraped_jobs ADD COLUMN {name} {definition}")

    con.execute("INSERT OR REPLACE INTO profile(id,data_json,updated_at) VALUES(1,?,?)", (json.dumps(PROFILE), NOW))
    for name, template, adapter, live in PORTALS:
        con.execute("""INSERT INTO portals(name,url_template,adapter,live_ingestion) VALUES(?,?,?,?)
                       ON CONFLICT(name) DO UPDATE SET url_template=excluded.url_template,
                       adapter=excluded.adapter,live_ingestion=excluded.live_ingestion""", (name, template, adapter, live))
    # Replace the discovery controls with the current domain-transition role set while
    # retaining old rows for database compatibility/history.
    con.execute("UPDATE target_roles SET active=0")
    for role in ROLES:
        con.execute("""INSERT INTO target_roles(name,active) VALUES(?,1)
                       ON CONFLICT(name) DO UPDATE SET active=1""", (role,))
    for title, category, url, objective in PROJECTS:
        guides = project_guides(title, category)
        con.execute("""INSERT INTO projects(title,category,dataset_url,objective,excel_guide,powerbi_dax,
                       production_sql,python_script,created_at) VALUES(?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(title) DO UPDATE SET category=excluded.category,dataset_url=excluded.dataset_url,
                       objective=excluded.objective,excel_guide=excluded.excel_guide,powerbi_dax=excluded.powerbi_dax,
                       production_sql=excluded.production_sql,python_script=excluded.python_script""",
                    (title, category, url, objective, guides["excel_guide"], guides["powerbi_dax"],
                     guides["production_sql"], guides["python_script"], NOW))
    for name, category, mastery, evidence in SKILLS:
        con.execute("""INSERT INTO skills(name,category,mastery,evidence,updated_at) VALUES(?,?,?,?,?)
                       ON CONFLICT(name) DO NOTHING""", (name, category, mastery, evidence, NOW))
    for category, difficulty, question, answer in QNA:
        con.execute("""INSERT INTO interview_qna(category,difficulty,question,answer,updated_at)
                       VALUES(?,?,?,?,?) ON CONFLICT(question) DO UPDATE SET answer=excluded.answer,
                       difficulty=excluded.difficulty,category=excluded.category,updated_at=excluded.updated_at""",
                    (category, difficulty, question, answer, NOW))

    # Remove only the obsolete demo/search cards from earlier builds. Real manual and
    # source-imported pipeline records are preserved. Live recommendations now come from
    # the hourly source database instead of permanent fake/stale starter cards.
    con.execute("""DELETE FROM jobs
                   WHERE (listing_type='search_lead'
                          AND notes='Starter search lead; verify a specific vacancy before applying.')
                      OR (company='Amazon' AND title='Operations Intelligence & WFM Analyst')
                      OR (company='Concentrix' AND title='MIS & Reporting Team Lead')
                      OR (company='Startek' AND title='WFM Reporting Lead & Data Specialist')
                      OR (company='Alorica' AND title='Senior Business Analytics Specialist')
                      OR (company='Teleperformance' AND title='Lead BI Developer & Operations Analyst')
                      OR (company='Genpact' AND title='Power BI & DAX Specialist (Analytics Core)')""")

    defaults = {
        "scan_interval_hours": "1", "max_job_age_hours": "72", "last_scan_at": "",
        "scanner_mode": "public_sources", "exclude_call_center": "true",
        "alert_email": "soumyadipsarkar2106@gmail.com", "alert_mode": "dashboard_only",
        "data_integrity_note": "Default radar includes only source-dated jobs posted in the past 72 hours. Source-active listings without a published date are separated and labeled.",
    }
    for key, value in defaults.items():
        if key == "last_scan_at":
            con.execute("INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES(?,?,?)", (key, value, NOW))
        else:
            con.execute("""INSERT INTO settings(key,value,updated_at) VALUES(?,?,?)
                           ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
                        (key, value, NOW))
    con.commit()
    con.close()
    print(f"Initialized {DB_PATH}")
    print("Seeded: 10 portals, 16 active domain-transition roles, 16 projects, 8 skills and 10 interview questions; obsolete demo job cards removed.")


if __name__ == "__main__":
    init_db()
