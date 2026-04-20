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
┌───────────────────┐       ┌──────────────────┐       ┌────────────────┐
│  GitHub Actions   │──┐    │                  │       │                │
│  cron: 0 */4 * *  │  ├──▶ │  main.py         │──────▶│   Supabase     │
└───────────────────┘  │    │  (searchers +    │       │   (events +    │
                       │    │   Supabase sync) │       │   source_status)│
┌───────────────────┐  │    │                  │       └───────┬────────┘
│  Local CLI /      │──┘    └────────┬─────────┘               │
│  python main.py   │                │                         │
└───────────────────┘                ▼                         ▼
                             ┌──────────────┐         ┌────────────────┐
                             │  Email       │         │  dashboard.py  │
                             │  digest      │         │  (Streamlit)   │
                             └──────────────┘         └────────────────┘
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
python main.py                    # one-shot
python main.py --schedule         # runs every 4 hours in-process
streamlit run dashboard.py        # open the triage UI
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
2. Main file: `dashboard.py`.
3. Add secrets (use the **anon key**, not service_role):
   ```toml
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "your-anon-key"
   ```
4. Deploy.

## Repository layout

```
CPGTriggerEventSearch/
├── main.py                          # orchestrator + scheduler + Supabase sync
├── dashboard.py                     # Streamlit triage UI
├── config.py                        # queries, schedule, API keys
├── requirements.txt
├── .env.example
├── .github/workflows/scraper.yml    # cron: every 4 hours
├── supabase/migrations/001_init.sql # events + source_status + RLS
├── searchers/
│   ├── base_searcher.py             # Google News RSS + NewsAPI + relevance
│   ├── product_launch_searcher.py
│   ├── funding_searcher.py
│   └── exec_hire_searcher.py
├── alerts/
│   └── email_sender.py              # HTML + plain-text digest
└── utils/
    ├── supabase_client.py           # upserts + source_status updates
    ├── deduplicator.py              # JSON fallback when Supabase off
    └── formatter.py                 # console + CSV export
```

## Customizing the search

All search queries live in [`config.py`](config.py):

```python
PRODUCT_LAUNCH_QUERIES = [...]
FUNDING_QUERIES = [...]
EXEC_HIRE_QUERIES = [...]
```

Edit, commit, push — the next cron run picks them up. Every query is expanded
to a Google News RSS feed (zero API keys needed) and, if configured, NewsAPI.

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
