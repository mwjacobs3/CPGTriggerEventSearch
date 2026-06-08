# DOSS Trigger Event Search

An automated lead intelligence system built for the DOSS sales team. It continuously monitors the CPG market for companies that are the right size, in the right stage of growth, and showing the exact signals that indicate they need DOSS.

Every 4 hours it scans trade press, funding wires, and Google News, scores each company against the DOSS ICP, and delivers a ranked digest to the team — so reps spend time selling, not researching.

---

## What it finds

| Signal | Why it matters for DOSS |
|---|---|
| 🚀 **Product launches & retail expansions** | A brand going to market or entering new retail channels is building operational complexity fast — exactly when they need DOSS |
| 💰 **Funding rounds (Series A/B/C, PE)** | Fresh capital = budget to fix broken systems. These companies are actively evaluating tools |
| 👤 **New ops & supply chain hires** | A new VP of Ops or COO is the #1 buyer at DOSS. They walk in the door wanting to make changes |

---

## DOSS ICP — who this targets

The system is tuned to surface companies that match the DOSS best-fit profile:

| Dimension | Target |
|---|---|
| **Revenue** | $10M – $200M |
| **Employees** | 10 – 500 |
| **Location** | US & Canada |
| **Products** | Food & bev, beauty, supplements, home goods, pet, apparel, consumer electronics — anything with physical inventory |
| **Manufacturing** | Uses co-manufacturers and/or 3PLs (outsourced) |
| **Current systems** | QuickBooks + spreadsheets, or a broken/failed tool stack |

### Scoring — what gets boosted

Every lead gets a relevance score (0–100). The signals that push a company to the top:

| Signal | Score bonus |
|---|---|
| Ops pain language ("fulfillment challenges", "inventory visibility", "outgrowing systems") | +15 |
| 3PL mention (ShipBob, ShipMonk, Stord, Saddle Creek, Flowspace, DHL Supply Chain, …) | +10 |
| Co-manufacturer / co-packer mention (Refresco, Power Brands, Nellson, Pharmavite, KDC/One, …) | +12 |
| Launch + outsourced ops (the DOSS sweet spot) | +15 stacked bonus |
| Broken/manual stack ("outgrew QuickBooks", "spreadsheet chaos", "manual processes") | +18 |
| DOSS-integrated tools in their stack (Shopify, QuickBooks, SPS Commerce, Faire, …) | +5 per hit |
| US or Canada company | +15 |
| Funding in $5M–$500M range | +15 |
| 10–500 employees | +10 |

### Scoring — what gets penalized or removed

| Signal | Score penalty |
|---|---|
| Full ERP already in place (NetSuite, Intacct, Epicor, Acumatica, SAP) | −30 |
| Disqualifying industry (government, pharma/hospitals, real estate, restaurant chains, VC firms) | −35 |
| Heavy in-house manufacturing with no outsourcing | −20 |
| International company (outside US/Canada) | −25 |
| Funding > $500M | −30 |
| Publicly traded / Fortune 500 | Removed entirely |
| Mega CPG (Nestlé, Unilever, P&G, Coca-Cola, PepsiCo, …) | Removed entirely |

---

## How it works

```
┌────────────────────────┐                 ┌──────────────────────────────┐
│  GitHub Actions cron   │──┐              │         Scrapers             │
│  Every 4 hours         │  │              │   ┌────────────────────┐     │
└────────────────────────┘  ├─────────────▶│   │ Google News (~100  │──┐  │
                            │              │   │   targeted queries)│  │  │
┌────────────────────────┐  │              │   │ Trade Press RSS    │──┼──┼──▶ Supabase
│  Manual trigger        │──┘              │   │   (37 CPG feeds)   │  │  │    ├─ events
│  (Actions → Run)       │                 │   │ Funding Wires      │──┤  │    └─ source_status
└────────────────────────┘                 │   │ Exec Hire Wires    │  │  │
                                           │   └────────────────────┘  │  │
                                           │   ICP score + dedupe ◀────┘  │
                                           └────────────┬─────────────────┘
                                                        │
                                       ┌────────────────┴─────────────────┐
                                       ▼                                  ▼
                               ┌──────────────┐                  ┌────────────────┐
                               │  Email digest│                  │  Dashboard     │
                               │  every 4 hrs │                  │  (Streamlit)   │
                               └──────────────┘                  └────────────────┘
```

**Four scrapers run every cycle:**
1. **37 trade-press RSS feeds** — Food Dive, BevNET, Beauty Independent, Grocery Dive, Modern Retail, Progressive Grocer, BusinessWire, PR Newswire, GlobeNewswire, and more
2. **~100 Google News queries** — parameterized by event type (launch, funding, retail expansion, exec hire) and vertical (food & bev, beauty, supplements, home goods, pet, apparel, consumer electronics)
3. **Funding wires** — FinSMEs, TechCrunch, Crunchbase News, Axios, VentureBeat, Inc., BevNET Funding
4. **Exec appointment press wires** — BusinessWire and PR Newswire filtered for VP/Director/C-Suite ops and supply chain titles

Each article is parsed for company name, founder, location, funding, employee count, tech stack, retail doors, and DOSS fit signals (3PL, co-man, ops pain). A best-effort homepage fetch fingerprints the brand's actual tech stack (Shopify CDN, BigCommerce tags, Klaviyo/Yotpo/Recharge scripts) to fill gaps that press copy misses.

---

## The dashboard

The Streamlit dashboard is where reps triage leads. Leads are sorted by priority: NEW first, then US/Canada above international, then by relevance score.

Each lead card shows:
- Company name, location, founder name
- Funding round and amount, employee count, founding year
- DOSS fit badges: ops pain, 3PL, co-man, channel mix (DTC / Retail / DTC+Retail)
- Retail doors (Whole Foods, Target, Costco, etc.)
- Company website, LinkedIn, source article

**Mark each lead as:**
- 📞 **Contacted** — outreach sent
- 💼 **DOSS Customer** — already closed
- ❌ **Out of Alignment** — not a fit
- 🚫 **Not Relevant** — noise

Sidebar filters let you slice by event type, industry, lead status, and supply-chain signals (ops pain only, 3PL only, co-man only, DOSS-integrated stack, channel mix).

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/mwjacobs3/CPGTriggerEventSearch.git
cd CPGTriggerEventSearch
pip install -r requirements.txt
cp .env.example .env
```

### 2. Set up Supabase

1. Create a project at [app.supabase.com](https://app.supabase.com).
2. SQL Editor → paste [`supabase/schema.sql`](supabase/schema.sql) → Run.
3. Grab the project URL, **anon key** (for the dashboard), and **service_role key** (for the scraper).
4. Fill them into `.env`.

### 3. Run locally

```bash
cp config.example.yaml config.yaml
python -m src.main          # one-shot scrape
python -m src.main --daemon # runs on the configured interval
streamlit run dashboard.py  # open the triage dashboard
```

### 4. GitHub Actions (4-hour cron)

In **Settings → Secrets and variables → Actions**, add:

| Secret | Required | Description |
|---|---|---|
| `SUPABASE_URL` | ✅ | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Service role key (bypasses RLS) |
| `EMAIL_SENDER` | ✅ | Gmail address |
| `EMAIL_PASSWORD` | ✅ | [Gmail App Password](https://myaccount.google.com/apppasswords) |
| `EMAIL_RECIPIENTS` | ✅ | Comma-separated addresses |
| `SMTP_HOST` | ⬜ | Defaults to `smtp.gmail.com` |
| `SMTP_PORT` | ⬜ | Defaults to `587` |

The workflow runs automatically every 4 hours and can be triggered manually via **Actions → CPG Trigger Event Scraper → Run workflow**.

### 5. Streamlit Cloud (dashboard)

1. Go to [share.streamlit.io](https://share.streamlit.io) and connect this repo.
2. Main file: `dashboard.py`. Python version is pinned to 3.11 via `runtime.txt`.
3. Under **Advanced settings → Secrets**:
   ```toml
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "your-anon-key"
   ```

---

## Repository layout

```
CPGTriggerEventSearch/
├── dashboard.py                     # Streamlit triage UI
├── main.py                          # entry point → src.main
├── config.example.yaml              # ICP filters, queries, scheduling
├── requirements.txt
├── runtime.txt                      # Python 3.11 (Streamlit Cloud)
├── .streamlit/config.toml           # dashboard theme
├── .github/workflows/scraper.yml    # cron: every 4 hours
├── supabase/
│   ├── schema.sql                   # complete idempotent schema — run this
│   └── migrations/                  # individual migration history
└── src/
    ├── main.py                      # orchestrator + Supabase sync
    ├── models.py                    # TriggerEvent dataclass
    ├── database.py                  # Supabase client
    ├── alerts.py                    # email digest
    ├── enrichment.py                # tech-stack fingerprinting
    └── scrapers/
        ├── base.py                  # ICP filters, scoring, extraction logic
        ├── rss_scraper.py           # Google News + trade press RSS
        ├── finsmes_scraper.py       # funding wires
        └── job_scraper.py           # exec hire press wires
```
