import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
SERP_API_KEY = os.getenv("SERP_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
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
RUN_SCHEDULE = os.getenv("RUN_SCHEDULE", "every_4_hours")
RUN_TIME = os.getenv("RUN_TIME", "07:00")

# ── Local Fallback Storage ────────────────────────────────────────────────────
SEEN_RESULTS_FILE = os.getenv("SEEN_RESULTS_FILE", "data/seen_results.json")
RESULTS_OUTPUT_FILE = os.getenv("RESULTS_OUTPUT_FILE", "data/results.csv")

# ── Event Type Identifiers ────────────────────────────────────────────────────
EVENT_TYPE_PRODUCT_LAUNCH    = "product_launch"
EVENT_TYPE_FUNDING           = "funding"
EVENT_TYPE_EXEC_HIRE         = "exec_hire"
EVENT_TYPE_RETAIL_EXPANSION  = "retail_expansion"

# =============================================================================
# DOSS ICP TARGET PROFILE
# =============================================================================
# DOSS sells an Adaptive Resource Platform (ERP evolved) to:
#   • Mid-market ($5M–$100M) CPG, Food & Beverage, Health & Beauty, Supplements
#   • Companies with supply chain complexity (multi-channel, wholesale + DTC)
#   • Brands that are growing and outgrowing spreadsheets/QuickBooks/legacy ERP
#
# Highest-value trigger events:
#   1. Funding (Series A/B) — they have budget; need to scale ops
#   2. DTC brand entering retail (Whole Foods, Target, Walmart, Costco) — ops complexity spike
#   3. New VP/Director of Ops or Supply Chain — new exec, mandate to modernize, quick wins
#   4. New brand launch in F&B, Health, Beauty — building ops stack from scratch
# =============================================================================

# ── 1. New Product & Brand Launches ──────────────────────────────────────────
# Target: Emerging/challenger brands in DOSS verticals going to market.
PRODUCT_LAUNCH_QUERIES = [
    # Food & Beverage
    '"new food brand" launch US 2025',
    '"new beverage brand" launch US',
    "emerging food startup launches US market",
    "natural food brand launch US grocery",
    "functional beverage brand launch",
    "plant-based food brand launch US",
    "challenger food brand launch retail",
    # Health, Beauty & Wellness
    '"new supplement brand" launch US',
    "health and wellness brand launch US",
    "clean beauty brand launch US",
    "personal care brand launch direct to consumer",
    "new skincare brand launch US",
    # General CPG mid-market
    "emerging CPG brand launch mid-market",
    "challenger consumer brand launch US",
    "DTC brand launch consumer goods",
]

# ── 2. PE / VC Funding ───────────────────────────────────────────────────────
# Target: Series A/B in CPG verticals — they have budget + scaling pressure.
FUNDING_QUERIES = [
    # Sweet spot: Series A/B ($2M–$50M)
    "food beverage brand Series A funding",
    "health beauty startup Series A funding",
    "CPG brand Series B funding round",
    "supplement brand raises venture capital",
    "natural food brand funding round",
    "consumer goods startup raises million Series A",
    "DTC brand Series A funding",
    "personal care brand raises funding",
    "wellness brand venture capital investment",
    # PE / minority investment
    "CPG company private equity minority investment",
    "emerging consumer brand PE investment",
    "food brand private equity growth investment",
    # Broader
    "consumer packaged goods startup funding 2025",
    "health beauty brand raises million",
]

# ── 3. DTC-to-Retail Expansion ───────────────────────────────────────────────
# Target: DTC brands entering wholesale / retail — biggest ops complexity spike.
RETAIL_EXPANSION_QUERIES = [
    # Landing key retail doors
    "DTC brand enters Whole Foods",
    "direct to consumer brand launches Target",
    "DTC brand Walmart retail launch",
    "consumer brand Costco launch",
    "DTC brand enters grocery retail US",
    "emerging brand retail distribution deal",
    # Wholesale / distribution
    "DTC brand wholesale expansion US",
    "consumer brand national distribution deal",
    "food brand enters retail from direct to consumer",
    "online brand brick and mortar expansion",
    "digital native brand retail launch US",
    "DTC food brand retail partnership",
    # Amazon / omnichannel
    "consumer brand Amazon FBA launch",
    "health brand omnichannel expansion",
    "CPG brand multichannel retail launch",
]

# ── 4. New Ops / Supply Chain Executives ─────────────────────────────────────
# Target: Newly hired VPs and Directors who arrive with a modernization mandate.
EXEC_HIRE_QUERIES = [
    # VP / Director level — supply chain
    '"VP supply chain" food beverage hired',
    '"VP supply chain" health beauty appointed',
    '"Director supply chain" consumer goods named',
    '"Director of operations" CPG brand appointed',
    '"Head of supply chain" consumer brand',
    # COO / Chief ops level
    '"Chief Operations Officer" food beverage brand',
    '"COO" consumer goods startup appointed',
    '"Chief Supply Chain Officer" CPG',
    # Procurement / logistics / fulfillment
    '"VP procurement" food beverage company',
    '"VP logistics" consumer goods brand hired',
    '"Director of fulfillment" DTC brand',
    '"VP operations" health beauty company',
    # General
    "new operations leader CPG brand hired",
    "supply chain executive joins food beverage company",
    "operations director consumer goods company appointed",
]

# ── Relevance Filter Keywords ─────────────────────────────────────────────────
# Any one match keeps the result. Tuned to DOSS verticals + ops signals.
CPG_RELEVANCE_KEYWORDS = [
    # Core verticals
    "cpg", "consumer packaged goods", "consumer goods", "fmcg",
    "food", "beverage", "grocery",
    "health", "beauty", "wellness", "supplement", "vitamins",
    "personal care", "skincare", "haircare", "cosmetics",
    "natural", "organic", "clean label", "plant-based", "functional",
    # Go-to-market & channel
    "retail", "brand", "product launch", "dtc", "direct to consumer",
    "d2c", "wholesale", "omnichannel", "multichannel", "distribution",
    "whole foods", "target", "walmart", "costco", "amazon",
    # Operations & supply chain
    "supply chain", "operations", "logistics", "procurement",
    "fulfillment", "inventory", "warehouse", "3pl", "erp",
    "sku", "demand planning", "order management",
    # Finance / investment signals
    "private equity", "venture capital", "series a", "series b",
    "funding", "acquisition", "merger", "raises",
]

# ── AI Relevance Filter ───────────────────────────────────────────────────────
USE_AI_FILTER = os.getenv("USE_AI_FILTER", "false").lower() == "true"
AI_RELEVANCE_THRESHOLD = float(os.getenv("AI_RELEVANCE_THRESHOLD", "0.65"))

# DOSS ICP context injected into the AI filter prompt
DOSS_ICP_CONTEXT = """
DOSS sells an Adaptive Resource Platform (ERP evolved) to mid-market companies
($5M–$100M revenue) in these verticals: Food & Beverage, Health & Beauty,
Supplements/Vitamins, Personal Care, and Consumer Goods / CPG.

Ideal prospects are:
- Growing brands with supply chain complexity (multi-channel, wholesale + DTC)
- Companies that just raised Series A or B funding
- DTC brands expanding into retail (Whole Foods, Target, Walmart, Costco)
- Companies with a new VP/Director/COO of Operations or Supply Chain
- Brands outgrowing spreadsheets, QuickBooks, or rigid legacy ERP

NOT ideal:
- Fortune 500 enterprises (too large, long sales cycles)
- Very early pre-revenue startups
- Non-CPG industries (tech, SaaS, real estate)
- Retail chains or pure service businesses
"""
