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

st.set_page_config(
    page_title="CPG Trigger Events",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .stApp { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    .main-header {
        background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(14, 165, 233, 0.3);
    }
    .main-header h1 {
        color: white; font-size: 2rem; font-weight: 700; margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p { color: rgba(255,255,255,0.85); font-size: 1rem; margin-top: 0.5rem; }

    .metric-card {
        background: white; border-radius: 16px; padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 1px solid rgba(0,0,0,0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.12); }
    .metric-icon {
        width: 48px; height: 48px; border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.5rem; margin-bottom: 1rem;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: #1a1a2e; line-height: 1; }
    .metric-label { font-size: 0.875rem; color: #6b7280; margin-top: 0.5rem; font-weight: 500; }

    .event-card-inner { padding: 0.25rem 0; }
    .event-card-header { display: flex; align-items: flex-start; gap: 1rem; }

    .event-type-badge {
        padding: 0.35rem 0.75rem; border-radius: 50px;
        font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.5px; white-space: nowrap;
    }
    .badge-launch  { background: #dcfce7; color: #166534; }
    .badge-funding { background: #fef3c7; color: #92400e; }
    .badge-exec    { background: #ede9fe; color: #5b21b6; }
    .badge-other   { background: #f3f4f6; color: #374151; }

    .status-badge {
        padding: 0.25rem 0.6rem; border-radius: 50px;
        font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
    }
    .status-new          { background: #dbeafe; color: #1e40af; }
    .status-contacted    { background: #fef3c7; color: #92400e; }
    .status-customer     { background: #d1fae5; color: #065f46; }
    .status-out          { background: #fee2e2; color: #991b1b; }
    .status-not-relevant { background: #f3f4f6; color: #6b7280; }

    .event-title {
        font-size: 1rem; font-weight: 600; color: #1a1a2e;
        margin: 0.5rem 0; line-height: 1.4;
    }
    .event-company { display: flex; align-items: center; gap: 0.5rem;
                     color: #6b7280; font-size: 0.875rem; }
    .event-meta    { display: flex; gap: 1rem; margin-top: 0.75rem;
                     font-size: 0.8rem; color: #9ca3af; }

    .search-container {
        background: white; border-radius: 12px; padding: 0.5rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06); margin-bottom: 1.5rem;
    }

    .section-header {
        display: flex; align-items: center; gap: 0.75rem;
        margin: 1.5rem 0 1rem; padding-bottom: 0.75rem;
        border-bottom: 2px solid #f1f5f9;
    }
    .section-header h2 { font-size: 1.25rem; font-weight: 600; color: #1a1a2e; margin: 0; }
    .section-count {
        background: #f1f5f9; padding: 0.25rem 0.75rem; border-radius: 50px;
        font-size: 0.8rem; font-weight: 600; color: #64748b;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #fafbfc 0%, #f1f5f9 100%);
    }

    .stButton > button { border-radius: 8px; font-weight: 500; transition: all 0.2s ease; }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

    hr { border: none; height: 1px; background: #e5e7eb; margin: 1.5rem 0; }
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

# ── Lead workflow (adapted for DOSS sales) ────────────────────────────────────
LEAD_STATUSES = [
    "NEW",
    "REVIEWED - Contacted",
    "REVIEWED - DOSS Customer",
    "REVIEWED - Out of Alignment",
    "NOT RELEVANT",
]

STATUS_CONFIG = {
    "NEW":                         {"icon": "🆕", "class": "status-new",          "label": "New"},
    "REVIEWED - Contacted":        {"icon": "📞", "class": "status-contacted",    "label": "Contacted"},
    "REVIEWED - DOSS Customer":    {"icon": "💼", "class": "status-customer",     "label": "DOSS Customer"},
    "REVIEWED - Out of Alignment": {"icon": "❌", "class": "status-out",          "label": "Out"},
    "NOT RELEVANT":                {"icon": "🚫", "class": "status-not-relevant", "label": "Not Relevant"},
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


def load_events(days: int = 30, search: str | None = None) -> pd.DataFrame:
    client = get_supabase_client()
    if not client:
        return pd.DataFrame()

    try:
        query = client.table("events").select("*")
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        query = query.gte("discovered_at", cutoff_date)
        response = query.order("discovered_at", desc=True).limit(2000).execute()

        if not response.data:
            return pd.DataFrame()

        df = pd.DataFrame(response.data)

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
        return df

    except Exception as exc:
        st.error(f"Error loading events: {exc}")
        return pd.DataFrame()


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
        return True
    except Exception as exc:
        st.error(f"Error updating status: {exc}")
        return False


def render_metric_card(icon: str, value: int, label: str, color: str) -> None:
    bg_gradient = f"linear-gradient(135deg, {color}20 0%, {color}10 100%)"
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-icon" style="background: {bg_gradient};">{icon}</div>
            <div class="metric-value">{value:,}</div>
            <div class="metric-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_event_card(row, event_config) -> None:
    status = row.get("lead_status", "NEW") or "NEW"
    title = str(row.get("title", ""))[:140]
    company = row.get("company_name") or "Unknown Company"
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

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="event-card-inner">
                <div class="event-card-header">
                    <span class="event-type-badge {badge_class}">{event_config['icon']} {event_config['label']}</span>
                    <span class="status-badge {status_cfg['class']}">{status_cfg['label']}</span>
                </div>
                <div class="event-title">{title}</div>
                <div class="event-company"><span>🏢</span><span>{company}</span></div>
                <div class="event-meta"><span>📅 {date_display}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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
    full_label = event_config.get("full_label", event_config["label"])

    st.markdown(
        f"""
        <div class="section-header">
            <span style="font-size: 1.5rem;">{event_config['icon']}</span>
            <h2>{full_label}</h2>
            <span class="section-count">{len(type_df)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
    st.markdown(
        """
        <div class="main-header">
            <h1>🛒 CPG Trigger Events</h1>
            <p>Find CPG &amp; consumer products accounts to sell DOSS — track launches, funding, and ops hires</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
    st.sidebar.markdown("### 🎛️ Filters")
    days = st.sidebar.slider("Time Range (days)", 1, 90, 30)

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

    # Metrics
    type_counts = df["event_type"].value_counts().to_dict()
    new_count = len(df[df["lead_status"] == "NEW"])
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("📊", len(df), "Total Signals", "#0ea5e9")
    with col2:
        render_metric_card("🆕", new_count, "New Leads", "#10b981")
    with col3:
        render_metric_card("💰", type_counts.get("funding", 0), "PE/VC Funding", "#f59e0b")
    with col4:
        render_metric_card("👤", type_counts.get("exec_hire", 0), "Ops Hires", "#8b5cf6")

    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("📡 Source Health", expanded=False):
        render_source_status_table(load_source_statuses())

    st.markdown("<br>", unsafe_allow_html=True)

    new_df = df[df["lead_status"] == "NEW"]
    classified_df = df[df["lead_status"] != "NEW"]

    # New Leads
    st.markdown(
        f"""
        <div class="section-header">
            <span style="font-size: 1.5rem;">🆕</span>
            <h2>New Leads</h2>
            <span class="section-count">{len(new_df)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if new_df.empty:
        st.info("No new leads to review. Nice work!")
    else:
        n_launch  = len(new_df[new_df["event_type"] == "product_launch"])
        n_funding = len(new_df[new_df["event_type"] == "funding"])
        n_exec    = len(new_df[new_df["event_type"] == "exec_hire"])

        tab_launch, tab_funding, tab_exec = st.tabs([
            f"🚀 Launches ({n_launch})",
            f"💰 Funding ({n_funding})",
            f"👤 Ops Execs ({n_exec})",
        ])

        with tab_launch:
            render_event_section(new_df, "product_launch", EVENT_TYPES["product_launch"])
        with tab_funding:
            render_event_section(new_df, "funding", EVENT_TYPES["funding"])
        with tab_exec:
            render_event_section(new_df, "exec_hire", EVENT_TYPES["exec_hire"])

    st.markdown("<br>", unsafe_allow_html=True)

    # Classified Leads
    st.markdown(
        f"""
        <div class="section-header">
            <span style="font-size: 1.5rem;">📋</span>
            <h2>Classified Leads</h2>
            <span class="section-count">{len(classified_df)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
                    for _, row in status_df.iterrows():
                        cfg = EVENT_TYPES.get(row.get("event_type", "other"), EVENT_TYPES["other"])
                        render_event_card(row, cfg)

    st.markdown("<br>", unsafe_allow_html=True)

    # All Events Table + Export
    with st.expander("📊 All Events Table", expanded=False):
        cols = ["event_type", "company_name", "title", "published_date", "lead_status"]
        available = [c for c in cols if c in df.columns]
        display = df[available].copy()
        display.columns = ["Type", "Company", "Title", "Published", "Status"]
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

    bulk_status = st.sidebar.selectbox(
        "Mark all new as:",
        ["Select status…"] + LEAD_STATUSES,
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
