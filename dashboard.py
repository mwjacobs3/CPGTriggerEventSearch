#!/usr/bin/env python3
"""
CPG Trigger Events Dashboard

Interactive Streamlit dashboard for managing CPG trigger event alerts.
Reads from Supabase for online access.

Usage:
    streamlit run dashboard.py
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

try:
    from src.scrapers.base import INDUSTRY_LABELS
except Exception:
    INDUSTRY_LABELS = {
        "food_beverage":        "Food & Beverage",
        "health_beauty":        "Health & Beauty",
        "wellness_supplements": "Supplements & Wellness",
        "household_home":       "Household & Home",
        "pet":                  "Pet & Specialty",
        "other_cpg":            "Consumer Goods (Other)",
    }

st.set_page_config(
    page_title="CPG Trigger Events",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    /* ── DOSS-aligned palette: ink hero, warm accent, clean minimal cards ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --doss-ink:        #0B0B0C;  /* near-black hero */
        --doss-ink-2:      #1A1A1F;  /* card dark text */
        --doss-accent:     #FF6B35;  /* warm orange accent */
        --doss-accent-2:   #F59E0B;  /* amber secondary */
        --doss-surface:    #FAFAF7;  /* warm off-white app bg */
        --doss-border:     #E5E4DF;
        --doss-muted:      #6B6B6B;
        --doss-muted-2:    #9A9A94;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background: var(--doss-surface);
        color: var(--doss-ink-2);
    }

    .main-header {
        background: var(--doss-ink);
        padding: 2.5rem 2.75rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        border: 1px solid #000;
        position: relative;
        overflow: hidden;
    }
    .main-header::after {
        content: "";
        position: absolute; inset: auto -40px -40px auto;
        width: 220px; height: 220px; border-radius: 50%;
        background: radial-gradient(circle, rgba(255,107,53,0.25) 0%, rgba(255,107,53,0) 70%);
        pointer-events: none;
    }
    .main-header h1 {
        color: #FFFFFF; font-size: 2.1rem; font-weight: 800; margin: 0;
        letter-spacing: -0.8px;
    }
    .main-header .eyebrow {
        color: var(--doss-accent); font-size: 0.75rem; font-weight: 700;
        letter-spacing: 2px; text-transform: uppercase; margin-bottom: 0.5rem;
    }
    .main-header p { color: rgba(255,255,255,0.72); font-size: 0.98rem; margin-top: 0.65rem; max-width: 720px; }

    .metric-card {
        background: #FFFFFF; border-radius: 14px; padding: 1.4rem;
        border: 1px solid var(--doss-border);
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .metric-card:hover { transform: translateY(-1px); border-color: var(--doss-ink); }
    .metric-icon {
        width: 40px; height: 40px; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.25rem; margin-bottom: 0.9rem;
    }
    .metric-value { font-size: 1.9rem; font-weight: 700; color: var(--doss-ink); line-height: 1; letter-spacing: -0.5px; }
    .metric-label { font-size: 0.78rem; color: var(--doss-muted); margin-top: 0.5rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }

    .event-card-inner { padding: 0.25rem 0; }
    .event-card-header { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }

    .event-type-badge {
        padding: 0.3rem 0.7rem; border-radius: 6px;
        font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.6px; white-space: nowrap;
    }
    .badge-launch  { background: #E8F5EC; color: #0F5132; }
    .badge-funding { background: #FFF3D9; color: #7A4900; }
    .badge-exec    { background: #EBE5FA; color: #4C1D95; }
    .badge-retail  { background: #E0EAFB; color: #1E3A8A; }
    .badge-other   { background: #EEEEEA; color: #3F3F3F; }

    .status-badge {
        padding: 0.22rem 0.55rem; border-radius: 6px;
        font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.4px;
    }
    .status-new          { background: var(--doss-ink); color: #FFFFFF; }
    .status-added        { background: #FFE4D6; color: #B0440D; }
    .status-customer     { background: #D6F0E0; color: #0F5132; }
    .status-not-relevant { background: #EEEEEA; color: #6B6B6B; }

    .industry-badge {
        padding: 0.22rem 0.55rem; border-radius: 6px;
        font-size: 0.68rem; font-weight: 600;
        background: #F3F1EC; color: var(--doss-ink-2);
        border: 1px solid var(--doss-border);
    }

    .score-badge {
        padding: 0.22rem 0.55rem; border-radius: 6px;
        font-size: 0.68rem; font-weight: 700;
        font-variant-numeric: tabular-nums;
    }
    .score-hot  { background: var(--doss-accent); color: #FFFFFF; }
    .score-warm { background: #FFE4D6; color: #B0440D; }
    .score-cool { background: #EEEEEA; color: #4A4A4A; }

    .event-title {
        font-size: 1.02rem; font-weight: 600; color: var(--doss-ink);
        margin: 0.65rem 0 0.4rem; line-height: 1.4; letter-spacing: -0.1px;
    }
    .event-company { display: flex; align-items: center; gap: 0.5rem;
                     color: var(--doss-muted); font-size: 0.875rem; }
    .event-meta    { display: flex; gap: 1rem; margin-top: 0.75rem;
                     font-size: 0.78rem; color: var(--doss-muted-2); }

    .search-container {
        background: #FFFFFF; border-radius: 10px; padding: 0.4rem;
        border: 1px solid var(--doss-border);
        margin-bottom: 1.5rem;
    }

    .section-header {
        display: flex; align-items: center; gap: 0.75rem;
        margin: 1.5rem 0 1rem; padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--doss-border);
    }
    .section-header h2 { font-size: 1.2rem; font-weight: 700; color: var(--doss-ink); margin: 0; letter-spacing: -0.3px; }
    .section-count {
        background: var(--doss-ink); padding: 0.2rem 0.65rem; border-radius: 6px;
        font-size: 0.72rem; font-weight: 700; color: #FFFFFF;
    }

    section[data-testid="stSidebar"] {
        background: #FFFFFF; border-right: 1px solid var(--doss-border);
    }
    section[data-testid="stSidebar"] h3 { color: var(--doss-ink); font-weight: 700; }

    .stButton > button {
        border-radius: 8px; font-weight: 600; transition: all 0.15s ease;
        border: 1px solid var(--doss-ink); background: var(--doss-ink); color: #FFFFFF;
    }
    .stButton > button:hover {
        background: var(--doss-accent); border-color: var(--doss-accent);
        color: #FFFFFF; transform: translateY(-1px);
    }

    hr { border: none; height: 1px; background: var(--doss-border); margin: 1.5rem 0; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Event type configurations (CPG-specific) ──────────────────────────────────
EVENT_TYPES = {
    "product_launch": {
        "label": "Launch",
        "full_label": "New CPG / Product Launches",
        "color": "#10b981",
        "gradient": "linear-gradient(135deg, #10b981 0%, #059669 100%)",
        "icon": "🚀",
        "badge_class": "badge-launch",
        "bg_color": "#dcfce7",
    },
    "funding": {
        "label": "Funding",
        "full_label": "PE / VC Funding",
        "color": "#f59e0b",
        "gradient": "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
        "icon": "💰",
        "badge_class": "badge-funding",
        "bg_color": "#fef3c7",
    },
    "exec_hire": {
        "label": "Exec",
        "full_label": "Ops / Supply Chain Execs",
        "color": "#8b5cf6",
        "gradient": "linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)",
        "icon": "👤",
        "badge_class": "badge-exec",
        "bg_color": "#ede9fe",
    },
    "retail_expansion": {
        "label": "Retail",
        "full_label": "DTC → Retail Expansion",
        "color": "#3b82f6",
        "gradient": "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
        "icon": "🏪",
        "badge_class": "badge-retail",
        "bg_color": "#dbeafe",
    },
    "other": {
        "label": "Other",
        "full_label": "Other Events",
        "color": "#6b7280",
        "gradient": "linear-gradient(135deg, #6b7280 0%, #4b5563 100%)",
        "icon": "📋",
        "badge_class": "badge-other",
        "bg_color": "#f3f4f6",
    },
}

# ── Lead workflow — simplified to 3 actionable outcomes for DOSS sales ────────
LEAD_STATUSES = [
    "NEW",
    "ADDED TO LEAD LIST",
    "DOSS CUSTOMER / PROSPECT",
    "NOT RELEVANT",
]

STATUS_CONFIG = {
    "NEW":                       {"icon": "🆕", "class": "status-new",          "label": "New"},
    "ADDED TO LEAD LIST":        {"icon": "✅", "class": "status-added",        "label": "Added to Lead List"},
    "DOSS CUSTOMER / PROSPECT":  {"icon": "💼", "class": "status-customer",     "label": "DOSS Customer / Prospect"},
    "NOT RELEVANT":              {"icon": "🚫", "class": "status-not-relevant", "label": "Not Relevant"},
}


@st.cache_resource
def get_supabase_client():
    try:
        from supabase import create_client
    except ImportError:
        st.error("Supabase not installed. Run: pip install supabase")
        return None

    url = (
        st.secrets.get("SUPABASE_URL")
        if hasattr(st, "secrets") and "SUPABASE_URL" in st.secrets
        else os.environ.get("SUPABASE_URL")
    )
    key = (
        st.secrets.get("SUPABASE_KEY")
        if hasattr(st, "secrets") and "SUPABASE_KEY" in st.secrets
        else os.environ.get("SUPABASE_KEY")
    )

    if not url or not key:
        return None

    return create_client(url, key)


@st.cache_data(ttl=300, show_spinner="Loading leads from Supabase…")
def _fetch_events(days: int) -> pd.DataFrame:
    """Fetch raw events from Supabase. Cached for 5 minutes to avoid
    refetching on every filter/selectbox interaction."""
    client = get_supabase_client()
    if not client:
        return pd.DataFrame()

    try:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        response = (
            client.table("events")
            .select("*")
            .gte("discovered_at", cutoff_date)
            .order("discovered_at", desc=True)
            .limit(2000)
            .execute()
        )
        if not response.data:
            return pd.DataFrame()
        return pd.DataFrame(response.data)
    except Exception as exc:
        st.error(f"Error loading events: {exc}")
        return pd.DataFrame()


def load_events(days: int = 30, search: str | None = None) -> pd.DataFrame:
    df = _fetch_events(days).copy()
    if df.empty:
        return df

    if search:
        search_lower = search.lower()
        mask = (
            df["title"].fillna("").str.lower().str.contains(search_lower, na=False)
            | df["company_name"].fillna("").str.lower().str.contains(search_lower, na=False)
            | df["description"].fillna("").str.lower().str.contains(search_lower, na=False)
        )
        df = df[mask]

    df = df.rename(columns={"source_url": "url", "discovered_at": "discovered_date"})
    df["lead_status"] = df["lead_status"].fillna("NEW")
    if "relevance_score" in df.columns:
        df["relevance_score"] = pd.to_numeric(df["relevance_score"], errors="coerce").fillna(0)
    else:
        df["relevance_score"] = 0
    return df


def load_source_statuses() -> pd.DataFrame:
    client = get_supabase_client()
    if not client:
        return pd.DataFrame()
    try:
        resp = (
            client.table("source_status")
            .select("*")
            .order("source_type")
            .order("source_name")
            .execute()
        )
        if not resp.data:
            return pd.DataFrame()
        return pd.DataFrame(resp.data)
    except Exception:
        return pd.DataFrame()


def update_lead_status(event_id: str, status: str, notes: str = "") -> bool:
    client = get_supabase_client()
    if not client:
        return False
    try:
        if status == "NOT RELEVANT":
            client.table("events").delete().eq("id", event_id).execute()
        else:
            data = {"lead_status": status}
            if notes is not None:
                data["notes"] = notes
            client.table("events").update(data).eq("id", event_id).execute()
        _fetch_events.clear()  # bust cache so the card disappears on rerun
        return True
    except Exception as exc:
        st.error(f"Error updating status: {exc}")
        return False


def _score_badge(score: float) -> str:
    """Return HTML for a DOSS priority badge. ≥75 = hot, 50-74 = warm, <50 = cool."""
    try:
        s = float(score or 0)
    except (TypeError, ValueError):
        s = 0
    cls = "score-hot" if s >= 75 else "score-warm" if s >= 50 else "score-cool"
    return f'<span class="score-badge {cls}">🎯 {int(s)}</span>'


def render_metric_card(icon: str, value: int, label: str, color: str) -> None:
    bg_gradient = f"linear-gradient(135deg, {color}28 0%, {color}10 100%)"
    html = (
        '<div class="metric-card">'
        f'<div class="metric-icon" style="background: {bg_gradient};">{icon}</div>'
        f'<div class="metric-value">{value:,}</div>'
        f'<div class="metric-label">{label}</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_event_card(row, event_config) -> None:
    status = row.get("lead_status", "NEW") or "NEW"
    title = str(row.get("title", ""))[:140]
    company = row.get("company_name") or "Unknown Company"
    location = row.get("company_location", "") or ""
    person_name = row.get("person_name", "") or ""
    person_title = row.get("person_title", "") or ""
    funding_round = row.get("funding_round", "") or ""
    funding_amount = row.get("funding_amount", "") or ""
    industry_key = row.get("industry", "") or ""
    published = row.get("published_date", "")

    date_display = ""
    if published:
        try:
            dt = (
                datetime.fromisoformat(published.replace("Z", "+00:00"))
                if isinstance(published, str)
                else published
            )
            date_display = dt.strftime("%b %d, %Y")
        except Exception:
            date_display = str(published)[:10]

    status_cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["NEW"])
    badge_class = event_config.get("badge_class", "badge-other")
    score_badge_html = _score_badge(row.get("relevance_score", 0))
    industry_label = INDUSTRY_LABELS.get(industry_key, "") if industry_key else ""
    industry_html = (
        f'<span class="industry-badge">🏷 {industry_label}</span>' if industry_label else ""
    )

    # Build supplemental line: person name, funding round, or location
    extra_html = ""
    if person_name:
        extra_html = f'<div class="event-company"><span>👤</span><span>{person_name}{" — " + person_title if person_title else ""}</span></div>'
    elif funding_round or funding_amount:
        label = " · ".join(filter(None, [funding_round, funding_amount]))
        extra_html = f'<div class="event-company"><span>💰</span><span>{label}</span></div>'
    elif location:
        extra_html = f'<div class="event-company"><span>📍</span><span>{location}</span></div>'

    # Keep this markdown flush left — Streamlit uses CommonMark, which treats
    # content indented 4+ spaces as a code block and prints raw HTML to the UI.
    card_html = (
        '<div class="event-card-inner">'
        '<div class="event-card-header">'
        f'<span class="event-type-badge {badge_class}">{event_config["icon"]} {event_config["label"]}</span>'
        f'<span class="status-badge {status_cfg["class"]}">{status_cfg["label"]}</span>'
        f'{industry_html}'
        f'{score_badge_html}'
        '</div>'
        f'<div class="event-title">{title}</div>'
        f'<div class="event-company"><span>🏢</span><span>{company}</span></div>'
        f'{extra_html}'
        f'<div class="event-meta"><span>📅 {date_display}</span></div>'
        '</div>'
    )

    with st.container(border=True):
        st.markdown(card_html, unsafe_allow_html=True)

        with st.expander("📝 Details & Actions"):
            col1, col2 = st.columns([2, 1])

            with col1:
                desc = row.get("description", "")
                if desc:
                    st.markdown("**Description**")
                    text = str(desc)
                    st.caption(text[:500] + ("…" if len(text) > 500 else ""))

                url = row.get("url", "")
                if url:
                    st.link_button("🔗 View Source", url, use_container_width=False)

            with col2:
                current_status = status
                new_status = st.selectbox(
                    "Status",
                    LEAD_STATUSES,
                    index=LEAD_STATUSES.index(current_status) if current_status in LEAD_STATUSES else 0,
                    key=f"status_{row['id']}",
                    label_visibility="collapsed",
                )
                notes = st.text_area(
                    "Notes",
                    value=row.get("notes") or "",
                    key=f"notes_{row['id']}",
                    height=80,
                    placeholder="Add notes…",
                )
                if st.button("💾 Save", key=f"save_{row['id']}", use_container_width=True):
                    if update_lead_status(row["id"], new_status, notes):
                        if new_status == "NOT RELEVANT":
                            st.success("✓ Event removed!")
                        else:
                            st.success("✓ Saved!")
                        st.rerun()


def render_event_section(df, event_type, event_config) -> None:
    type_df = df[df["event_type"] == event_type]
    # DOSS priority: hottest signals first, recency as tiebreaker.
    if not type_df.empty and "relevance_score" in type_df.columns:
        type_df = type_df.sort_values(
            by=["relevance_score", "discovered_date"],
            ascending=[False, False],
        )
    full_label = event_config.get("full_label", event_config["label"])

    header_html = (
        '<div class="section-header">'
        f'<span style="font-size: 1.5rem;">{event_config["icon"]}</span>'
        f'<h2>{full_label}</h2>'
        f'<span class="section-count">{len(type_df)}</span>'
        '</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    if type_df.empty:
        st.info(f"No {full_label.lower()} found matching your filters.")
        return

    for _, row in type_df.iterrows():
        render_event_card(row, event_config)


def render_source_status_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No source status data available. Run the scraper to populate.")
        return

    total = len(df)
    success = len(df[df["status"] == "success"])
    errors = len(df[df["status"] == "error"])
    partial = len(df[df["status"] == "partial"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sources", total)
    col2.metric("Working", success)
    col3.metric("Partial", partial)
    col4.metric("Failed", errors)

    def icon(status: str) -> str:
        return {"success": "🟢", "partial": "🟡"}.get(status, "🔴")

    display = []
    for _, row in df.iterrows():
        last = row.get("last_check", "")
        if last:
            try:
                dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
                last = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        display.append(
            {
                "Status": icon(row["status"]),
                "Source": row["source_name"],
                "Events": row.get("events_found", 0),
                "Last Check": last,
                "Error": row.get("error_message") or "",
            }
        )
    st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)


def main() -> None:
    hero_html = (
        '<div class="main-header">'
        '<div class="eyebrow">DOSS · Sales Intelligence</div>'
        '<h1>CPG Trigger Events</h1>'
        '<p>Mid-market Food &amp; Bev, Health &amp; Beauty, and Consumer Goods signals — '
        'product launches, retail expansion, Series A/B funding, and ops exec hires '
        'mapped to DOSS’s ideal customer profile.</p>'
        '</div>'
    )
    st.markdown(hero_html, unsafe_allow_html=True)

    client = get_supabase_client()
    if not client:
        st.warning("⚠️ Supabase not configured")
        st.info(
            """
        **To connect to Supabase:**

        Add to Streamlit secrets:
        ```
        SUPABASE_URL = "https://your-project.supabase.co"
        SUPABASE_KEY = "your-anon-key"
        ```

        And run `supabase/migrations/001_init.sql` in the Supabase SQL editor.
            """
        )
        return

    # Sidebar filters
    st.sidebar.markdown("### Filters")
    days = st.sidebar.slider("Time Range (days)", 1, 90, 30)
    if st.sidebar.button("🔄 Refresh data", use_container_width=True, help="Bypass the 5-min cache"):
        _fetch_events.clear()
        st.rerun()

    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    search = st.text_input(
        "Search",
        placeholder="🔍 Search by company, product, or keyword…",
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    df = load_events(days=days, search=search or None)

    if df.empty:
        st.info("📭 No events found. Run the scraper to populate data.")
        return

    # Industry filter — slice DOSS's ICP by vertical
    industry_options = [
        (key, INDUSTRY_LABELS.get(key, key))
        for key in INDUSTRY_LABELS
        if "industry" in df.columns and (df["industry"] == key).any()
    ]
    selected_industries: list[str] = []
    if industry_options:
        st.sidebar.markdown("### Industry")
        selected_labels = st.sidebar.multiselect(
            "Filter by industry",
            options=[label for _, label in industry_options],
            default=[],
            label_visibility="collapsed",
            placeholder="All industries",
        )
        label_to_key = {label: key for key, label in industry_options}
        selected_industries = [label_to_key[l] for l in selected_labels]
        if selected_industries:
            df = df[df["industry"].isin(selected_industries)]

    if df.empty:
        st.info("📭 No events match the selected industry filter.")
        return

    # Metrics — DOSS palette (ink + accent)
    type_counts = df["event_type"].value_counts().to_dict()
    new_count = len(df[df["lead_status"] == "NEW"])
    top_industry_label = "—"
    if "industry" in df.columns and not df["industry"].dropna().empty:
        top_key = df["industry"].replace("", pd.NA).dropna().value_counts().idxmax()
        top_industry_label = INDUSTRY_LABELS.get(top_key, top_key)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        render_metric_card("📊", len(df), "Total Signals", "#0B0B0C")
    with col2:
        render_metric_card("🆕", new_count, "New Leads", "#FF6B35")
    with col3:
        render_metric_card("🏪", type_counts.get("retail_expansion", 0), "Retail Expansions", "#1E3A8A")
    with col4:
        render_metric_card("💰", type_counts.get("funding", 0), "PE/VC Funding", "#F59E0B")
    with col5:
        render_metric_card("👤", type_counts.get("exec_hire", 0), "Ops Hires", "#4C1D95")

    st.sidebar.markdown("---")
    st.sidebar.caption(f"🏷 Top vertical: **{top_industry_label}**")

    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("📡 Source Health", expanded=False):
        render_source_status_table(load_source_statuses())

    st.markdown("<br>", unsafe_allow_html=True)

    new_df = df[df["lead_status"] == "NEW"]
    classified_df = df[df["lead_status"] != "NEW"]

    # New Leads
    new_header_html = (
        '<div class="section-header">'
        '<span style="font-size: 1.5rem;">🆕</span>'
        '<h2>New Leads</h2>'
        f'<span class="section-count">{len(new_df)}</span>'
        '</div>'
    )
    st.markdown(new_header_html, unsafe_allow_html=True)

    if new_df.empty:
        st.info("No new leads to review. Nice work!")
    else:
        n_launch  = len(new_df[new_df["event_type"] == "product_launch"])
        n_retail  = len(new_df[new_df["event_type"] == "retail_expansion"])
        n_funding = len(new_df[new_df["event_type"] == "funding"])
        n_exec    = len(new_df[new_df["event_type"] == "exec_hire"])

        tab_launch, tab_retail, tab_funding, tab_exec = st.tabs([
            f"🚀 Launches ({n_launch})",
            f"🏪 Retail Expansion ({n_retail})",
            f"💰 Funding ({n_funding})",
            f"👤 Ops Execs ({n_exec})",
        ])

        with tab_launch:
            render_event_section(new_df, "product_launch", EVENT_TYPES["product_launch"])
        with tab_retail:
            render_event_section(new_df, "retail_expansion", EVENT_TYPES["retail_expansion"])
        with tab_funding:
            render_event_section(new_df, "funding", EVENT_TYPES["funding"])
        with tab_exec:
            render_event_section(new_df, "exec_hire", EVENT_TYPES["exec_hire"])

    st.markdown("<br>", unsafe_allow_html=True)

    # Classified Leads
    classified_header_html = (
        '<div class="section-header">'
        '<span style="font-size: 1.5rem;">📋</span>'
        '<h2>Classified Leads</h2>'
        f'<span class="section-count">{len(classified_df)}</span>'
        '</div>'
    )
    st.markdown(classified_header_html, unsafe_allow_html=True)

    if classified_df.empty:
        st.info("No classified leads yet. Review new leads above to classify them.")
    else:
        classified_statuses = [s for s in LEAD_STATUSES if s not in ("NEW", "NOT RELEVANT")]
        tab_labels, tab_keys = [], []
        for s in classified_statuses:
            count = len(classified_df[classified_df["lead_status"] == s])
            if count > 0:
                cfg = STATUS_CONFIG.get(s, {"icon": "📋", "label": s})
                tab_labels.append(f"{cfg['icon']} {cfg['label']} ({count})")
                tab_keys.append(s)

        if tab_labels:
            tabs = st.tabs(tab_labels)
            for tab, status_key in zip(tabs, tab_keys):
                with tab:
                    status_df = classified_df[classified_df["lead_status"] == status_key]
                    if "relevance_score" in status_df.columns:
                        status_df = status_df.sort_values(
                            by=["relevance_score", "discovered_date"],
                            ascending=[False, False],
                        )
                    for _, row in status_df.iterrows():
                        cfg = EVENT_TYPES.get(row.get("event_type", "other"), EVENT_TYPES["other"])
                        render_event_card(row, cfg)

    st.markdown("<br>", unsafe_allow_html=True)

    # All Events Table + Export
    with st.expander("📊 All Events Table", expanded=False):
        cols = ["event_type", "industry", "company_name", "title", "published_date", "lead_status"]
        available = [c for c in cols if c in df.columns]
        display = df[available].copy()
        rename_map = {
            "event_type": "Type",
            "industry": "Industry",
            "company_name": "Company",
            "title": "Title",
            "published_date": "Published",
            "lead_status": "Status",
        }
        display.columns = [rename_map[c] for c in available]
        if "Industry" in display.columns:
            display["Industry"] = display["Industry"].map(
                lambda k: INDUSTRY_LABELS.get(k, "") if k else ""
            )
        st.dataframe(display, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Export CSV",
            csv,
            file_name=f"cpg_trigger_events_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    # Sidebar bulk actions
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚡ Bulk Actions")
    st.sidebar.caption("Apply to all NEW leads:")

    bulk_options = [s for s in LEAD_STATUSES if s != "NEW"]
    bulk_status = st.sidebar.selectbox(
        "Mark all new as:",
        ["Select status…"] + bulk_options,
        label_visibility="collapsed",
    )
    if (
        bulk_status
        and bulk_status != "Select status…"
        and st.sidebar.button("✓ Apply to All New", use_container_width=True)
    ):
        updated = 0
        for event_id in new_df["id"].tolist():
            try:
                if bulk_status == "NOT RELEVANT":
                    client.table("events").delete().eq("id", event_id).execute()
                else:
                    client.table("events").update({"lead_status": bulk_status}).eq(
                        "id", event_id
                    ).execute()
                updated += 1
            except Exception:
                pass
        st.sidebar.success(f"✓ Updated {updated} events!")
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption("🛒 CPGTriggerEventSearch — DOSS Sales Intel")


if __name__ == "__main__":
    main()
