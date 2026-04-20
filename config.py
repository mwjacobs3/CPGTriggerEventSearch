import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")           # newsapi.org (optional)
SERP_API_KEY = os.getenv("SERP_API_KEY", "")           # serpapi.com (optional)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "") # Claude relevance filter

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# Service-role key: used by the sync/scraper job (bypasses RLS)
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
# Anon key: used by the Streamlit dashboard (read-only via RLS)
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ── Email Settings ────────────────────────────────────────────────────────────
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENTS = [
    r.strip()
    for r in os.getenv("EMAIL_RECIPIENTS", "").split(",")
    if r.strip()
]
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# ── Schedule ──────────────────────────────────────────────────────────────────
# "every_4_hours" | "hourly" | "daily" | "weekly"
RUN_SCHEDULE = os.getenv("RUN_SCHEDULE", "every_4_hours")
RUN_TIME = os.getenv("RUN_TIME", "07:00")  # 24h HH:MM for daily/weekly

# ── Local Fallback Storage (used when Supabase is not configured) ─────────────
SEEN_RESULTS_FILE = os.getenv("SEEN_RESULTS_FILE", "data/seen_results.json")
RESULTS_OUTPUT_FILE = os.getenv("RESULTS_OUTPUT_FILE", "data/results.csv")

# ── Search Queries ────────────────────────────────────────────────────────────

PRODUCT_LAUNCH_QUERIES = [
    "new CPG brand launch",
    "consumer packaged goods product launch",
    "new food beverage brand launch",
    "new DTC consumer brand launch",
    "CPG startup launch",
    "new product retail launch grocery",
    "new consumer goods brand announced",
    "food and beverage startup launch funding",
]

FUNDING_QUERIES = [
    "CPG company funding round",
    "consumer packaged goods investment",
    "food beverage startup series A funding",
    "consumer brand private equity acquisition",
    "CPG venture capital investment",
    "consumer goods company PE funding",
    "FMCG startup funding announced",
    "consumer products brand acquired",
    "CPG company raises million",
]

EXEC_HIRE_QUERIES = [
    "VP supply chain CPG hired appointed",
    "Chief Supply Chain Officer consumer goods",
    "VP operations consumer packaged goods",
    "Director supply chain CPG appointed",
    "Head of operations food beverage company",
    "Chief Operations Officer CPG brand",
    "VP procurement consumer goods appointed",
    "Director of logistics CPG hired",
    "VP distribution consumer packaged goods",
    "new supply chain executive consumer brand",
]

# ── Event Type Identifiers (match dashboard + DB) ─────────────────────────────
EVENT_TYPE_PRODUCT_LAUNCH = "product_launch"
EVENT_TYPE_FUNDING = "funding"
EVENT_TYPE_EXEC_HIRE = "exec_hire"

# ── Relevance Filter Keywords ─────────────────────────────────────────────────
CPG_RELEVANCE_KEYWORDS = [
    "cpg", "consumer packaged goods", "consumer goods", "fmcg",
    "food", "beverage", "grocery", "retail", "brand", "product launch",
    "supply chain", "operations", "logistics", "procurement", "distribution",
    "dtc", "direct to consumer", "e-commerce", "omnichannel",
    "private equity", "venture capital", "series a", "series b", "funding",
    "acquisition", "merger",
]

# ── AI Relevance Filter ───────────────────────────────────────────────────────
USE_AI_FILTER = os.getenv("USE_AI_FILTER", "false").lower() == "true"
AI_RELEVANCE_THRESHOLD = float(os.getenv("AI_RELEVANCE_THRESHOLD", "0.7"))
