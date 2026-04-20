# CPGTriggerEventSearch

Alert system that surfaces **CPG and consumer-products trigger events** so
you can find accounts to reach out to and sell **DOSS**.

Monitors three categories every 4 hours:

| 🚀 | **New CPG / Product Launches** — new brands, retail entries, DTC launches |
| 💰 | **PE / VC Funding** — Series A/B/C, PE acquisitions, M&A in consumer goods |
| 👤 | **Ops / Supply Chain Execs** — new VP/Director/C-Suite hires in supply chain, ops, procurement |

Results land in **Supabase**, email **digests ship every 4 hours**, and a
**Streamlit dashboard** lets you triage leads (mark as Contacted, DOSS
Customer, Out of Alignment, Not Relevant).

## Architecture

```
┌────────────────────────┐                 ┌──────────────────────────────┐
│  GitHub Actions cron   │──┐              │       src.main               │
│  0 */4 * * *           │  │              │   ┌────────────────────┐     │
└────────────────────────┘  │              │   │ GoogleNewsScraper  │──┐  │
                            ├─────────────▶│   │ RSSFeedScraper     │  │  │
┌────────────────────────┐  │              │   │ FinSMEsScraper     │──┼──┼──▶ Supabase
│  Local CLI             │──┘              │   │ JobScraper         │  │  │    ├─ events
│  python -m src.main    │                 │   └────────────────────┘  │  │    └─ source_status
└────────────────────────┘                 │            │              │  │
                                           │   ICP filter + dedupe ◀───┘  │
                                           └────────────┬─────────────────┘
                                                        │
                                       ┌────────────────┴─────────────────┐
                                       ▼                                  ▼
                               ┌──────────────┐                  ┌────────────────┐
                               │ src.alerts   │                  │  dashboard.py  │
                               │ email digest │                  │  (Streamlit)   │
                               └──────────────┘                  └────────────────┘
```

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/mwjacobs3/CPGTriggerEventSearch.git
cd CPGTriggerEventSearch
pip install -r requirements.txt
cp .env.example .env
```

### 2. Set up Supabase

1. Create a project at [app.supabase.com](https://app.supabase.com).
2. SQL Editor → paste [`supabase/migrations/001_init.sql`](supabase/migrations/001_init.sql) → Run.
3. Grab the project URL, the **anon key** (dashboard), and the **service_role key** (scraper).
4. Fill them into `.env`.

### 3. Run locally

```bash
cp config.example.yaml config.yaml   # customize ICP filters / queries if desired
python -m src.main                    # one-shot scrape
python -m src.main --daemon           # runs on the interval in config.yaml
streamlit run dashboard.py            # open the triage UI
```

### 4. Deploy the 4-hour cron to GitHub Actions

In your repo **Settings → Secrets and variables → Actions** add:

| Secret | Required | Description |
|---|---|---|
| `SUPABASE_URL` | ✅ | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Service role key (bypasses RLS) |
| `EMAIL_SENDER` | ✅ | Gmail address |
| `EMAIL_PASSWORD` | ✅ | [Gmail App Password](https://myaccount.google.com/apppasswords) |
| `EMAIL_RECIPIENTS` | ✅ | Comma-separated addresses |
| `SMTP_HOST` | ⬜ | Defaults to `smtp.gmail.com` |
| `SMTP_PORT` | ⬜ | Defaults to `587` |
| `NEWS_API_KEY` | ⬜ | [newsapi.org](https://newsapi.org) — broader coverage |
| `SERP_API_KEY` | ⬜ | [serpapi.com](https://serpapi.com) |
| `ANTHROPIC_API_KEY` | ⬜ | Enables Claude relevance scoring |

The `.github/workflows/scraper.yml` workflow runs on cron `0 */4 * * *`
(every 4 hours) and on-demand via **Actions → CPG Trigger Event Scraper → Run workflow**.

### 5. Deploy the dashboard to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and connect this repo.
2. Main file: `dashboard.py`. Python version is pinned to 3.11 via `runtime.txt`.
3. Under **Advanced settings → Secrets**, paste (use the **anon key**, not service_role):
   ```toml
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "your-anon-key"
   ```
4. Deploy. Theme + server settings are pre-configured in `.streamlit/config.toml`.

## Repository layout

```
CPGTriggerEventSearch/
├── dashboard.py                     # Streamlit triage UI
├── main.py                          # thin shim → src.main
├── config.example.yaml              # scraper config template (ICP, queries, filters)
├── requirements.txt
├── runtime.txt                      # Python 3.11 pin for Streamlit Cloud
├── .env.example
├── .streamlit/config.toml           # dashboard theme + server settings
├── .github/workflows/scraper.yml    # cron: every 4 hours
├── supabase/migrations/001_init.sql # events + source_status + RLS
└── src/
    ├── main.py                      # orchestrator + scheduler + Supabase sync
    ├── models.py                    # TriggerEvent dataclass
    ├── database.py                  # Supabase client + upserts
    ├── alerts.py                    # HTML + plain-text email digest
    └── scrapers/
        ├── base.py                  # shared scraper helpers
        ├── rss_scraper.py           # Google News RSS (no API key)
        ├── news_scraper.py          # NewsAPI
        ├── finsmes_scraper.py       # FinSMEs funding feed
        └── job_scraper.py           # LinkedIn / job board scraping
```

## Customizing the search

All queries, ICP filters, excluded companies/locations, and scheduling live in
[`config.example.yaml`](config.example.yaml) — copy it to `config.yaml` and edit:

```yaml
queries:
  product_launch: [...]
  funding:        [...]
  exec_hire:      [...]
```

Edit, commit, push — the next cron run picks them up. Every query is expanded
to a Google News RSS feed (zero API keys needed) and, if configured, NewsAPI.

## Sources monitored

Every 4-hour run pulls from **four** scrapers. All sources are filtered by the
DOSS ICP rules in `config.yaml` (US-only, mid-market, excludes public mega-caps).

### 1. Trade-press RSS (`RSSFeedScraper`, 37 feeds from `config.yaml`)

| Category | Feeds |
|---|---|
| **Food & Beverage** | Food Dive · Food Business News · FoodNavigator USA · Prepared Foods · Beverage Daily · BevNET · Candy Industry · Snack Food & Wholesale Bakery · Pet Food Industry |
| **Retail / Grocery** | Grocery Dive · Progressive Grocer · Supermarket News · Retail Dive · Winsight Grocery Business · Convenience Store News · Chain Store Age |
| **Health, Beauty & Wellness** | Beauty Independent · Drug Store News · CosmeticsDesign USA · Happi · Glossy · WWD Beauty · Natural Products Insider · Nutraceuticals World · Nutritional Outlook |
| **DTC / Omnichannel** | Modern Retail · Retail Brew · Digiday Retail |
| **Press Releases (broad)** | BusinessWire (Consumer Products / Food & Bev / Health & Wellness / Retail) · PR Newswire · GlobeNewswire Consumer · EIN Presswire Consumer Goods · AccessWire |

### 2. Google News (`GoogleNewsScraper`, ~100 queries from `config.yaml`)

Every query is expanded to a Google News RSS feed. Grouped by event type:

- **Product Launch** — 25+ queries across Food & Beverage, Health & Beauty, Home & Household, DTC / General CPG
- **Retail Expansion** — 20+ queries for DTC → retail (Whole Foods, Target, Walmart, Costco, Kroger, Sprouts, Publix, Ulta, Sephora, CVS, Walgreens, PetSmart, Petco) + distribution deals
- **Funding** — 20+ queries for Series A/B, PE minority investments, seed rounds across F&B, Health & Beauty, Home, DTC
- **Exec Hire** — 25+ queries for DOSS ICP roles: VP/SVP/Director/Head of Supply Chain, Operations, Procurement, Logistics, Fulfillment, COO, CSCO, **plus Founder / Co-Founder / Founder & CEO** at founder-led CPG brands (where the founder is the operational decision-maker)

### 3. Funding-specific RSS (`FinSMEsScraper`, 9 feeds, hard-coded)

FinSMEs · TechCrunch Startups · Crunchbase News · VentureBeat · Fortune Entrepreneurship · Inc. Startups & Funding · Axios Business · BevNET Funding · Beauty Independent Funding

### 4. Exec-hire press wires (`JobScraper`, BusinessWire + PR Newswire)

Monitors press-release wires for exec appointment announcements, then filters
for the DOSS ICP:

- **Ops / supply-chain leaders** — VP / SVP / EVP / Director / Head of
  Supply Chain, Operations, Procurement, Logistics, Fulfillment
- **C-suite** — COO, CSCO, Chief Operations / Supply Chain Officer
- **Founder-led brands** — Founder, Co-Founder, Founder & CEO, President & CEO
  (at sub-$50M CPG, the founder IS the ops buyer)

Press-release wires are more reliable than scraping job boards (which block bots).

## Lead triage workflow

The dashboard shows `NEW` signals first. Mark each as:

- 📞 **Contacted** — you've reached out
- 💼 **DOSS Customer** — already a customer
- ❌ **Out of Alignment** — not a DOSS fit
- 🚫 **Not Relevant** — noise; deletes from DB

Bulk actions are in the sidebar.

## Background

Repurposed from [TriggerEventSearch](https://github.com/mwjacobs3/TriggerEventSearch)
(which targeted CFOs, finance hires, and PE funding). Same scaffolding —
searchers, Supabase sync, Streamlit dashboard, 4-hour GitHub Actions cron —
but every search query and event type is retargeted at CPG ops buyers.
