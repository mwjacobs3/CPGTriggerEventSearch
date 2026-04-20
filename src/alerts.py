"""Email alert manager — sends HTML digests grouped by CPG event type."""

from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from jinja2 import Template

from .models import EventType, TriggerEvent

_CATEGORY_META = {
    EventType.PRODUCT_LAUNCH:   {"icon": "🚀", "label": "New CPG / Product Launches"},
    EventType.RETAIL_EXPANSION: {"icon": "🏪", "label": "DTC → Retail Expansions"},
    EventType.FUNDING:          {"icon": "💰", "label": "PE / VC Funding"},
    EventType.EXEC_HIRE:        {"icon": "👤", "label": "Ops / Supply Chain Execs"},
    EventType.OTHER:            {"icon": "📋", "label": "Other"},
}

_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
           color: #222; max-width: 680px; margin: 0 auto; }
    .header { background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%);
              padding: 1.75rem 2rem; border-radius: 14px; margin-bottom: 1.5rem; }
    .header h1 { color: #fff; margin: 0; font-size: 1.6rem; font-weight: 700; }
    .header p  { color: rgba(255,255,255,.85); margin: .4rem 0 0; font-size: .9rem; }
    h2 { font-size: 1rem; text-transform: uppercase; letter-spacing: .8px;
         color: #1a1a2e; margin: 1.75rem 0 .75rem; border-bottom: 2px solid #f1f5f9;
         padding-bottom: .5rem; }
    .card { border-left: 4px solid #0ea5e9; padding: .7rem 1rem;
            margin-bottom: .9rem; background: #f7f9fc; border-radius: 0 8px 8px 0; }
    .card a { color: #0ea5e9; font-weight: 600; font-size: .95rem;
               text-decoration: none; }
    .meta { font-size: .75rem; color: #6b7280; margin-top: .3rem; }
    .company { font-size: .8rem; color: #374151; margin-top: .25rem; }
    .summary { font-size: .8rem; color: #555; margin-top: .4rem; }
    .badge { display: inline-block; padding: .2rem .55rem; border-radius: 50px;
             font-size: .65rem; font-weight: 700; text-transform: uppercase;
             letter-spacing: .4px; margin-right: .4rem; }
    .badge-launch  { background: #dcfce7; color: #166534; }
    .badge-retail  { background: #dbeafe; color: #1e40af; }
    .badge-funding { background: #fef3c7; color: #92400e; }
    .badge-exec    { background: #ede9fe; color: #5b21b6; }
    .footer { font-size: .7rem; color: #9ca3af; margin-top: 2rem;
              border-top: 1px solid #e5e7eb; padding-top: .75rem; }
  </style>
</head>
<body>
  <div class="header">
    <h1>🛒 CPG Trigger Events — DOSS ICP</h1>
    <p>{{ date }} &nbsp;·&nbsp; <strong>{{ total }}</strong> new signals</p>
  </div>

  {% for etype, meta in categories.items() %}
  {% set items = grouped[etype] %}
  {% if items %}
  <h2>{{ meta.icon }} {{ meta.label }} ({{ items|length }})</h2>
  {% for e in items %}
  <div class="card">
    <a href="{{ e.url }}" target="_blank">{{ e.title[:120] }}</a>
    {% if e.company_name %}<div class="company">🏢 {{ e.company_name }}{% if e.funding_round %} &nbsp;·&nbsp; {{ e.funding_round }}{% endif %}{% if e.funding_amount %} &nbsp;·&nbsp; {{ e.funding_amount }}{% endif %}</div>{% endif %}
    {% if e.person_name %}<div class="company">👤 {{ e.person_name }}{% if e.person_title %} — {{ e.person_title }}{% endif %}</div>{% endif %}
    <div class="meta">{{ e.source_name }} &nbsp;·&nbsp; {{ e.published_date.strftime('%b %d, %Y') if e.published_date else '' }}</div>
    {% if e.description %}<div class="summary">{{ e.description[:200] }}{% if e.description|length > 200 %}…{% endif %}</div>{% endif %}
  </div>
  {% endfor %}
  {% endif %}
  {% endfor %}

  <div class="footer">CPGTriggerEventSearch &nbsp;·&nbsp; Selling DOSS to the CPG world</div>
</body>
</html>
"""

_TEXT_TEMPLATE = """CPG TRIGGER EVENTS — DOSS ICP
{{ date }} | {{ total }} new signals
{% for etype, meta in categories.items() %}{% set items = grouped[etype] %}{% if items %}
{{ meta.icon }} {{ meta.label|upper }} ({{ items|length }})
{% for e in items %}• {{ e.title }}
  {{ e.url }}
  {{ e.source_name }} | {{ e.published_date.strftime('%b %d, %Y') if e.published_date else '' }}
{% if e.company_name %}  Company: {{ e.company_name }}{% endif %}
{% endfor %}{% endif %}{% endfor %}"""


class AlertManager:

    def __init__(self, config: dict[str, Any]):
        email_cfg = config.get("alerts", {}).get("email", {})
        self.enabled    = email_cfg.get("enabled", False)
        self.sender     = email_cfg.get("sender_email") or os.environ.get("EMAIL_SENDER", "")
        self.password   = email_cfg.get("sender_password") or os.environ.get("EMAIL_PASSWORD", "")
        raw_recipients  = email_cfg.get("recipient_emails") or []
        env_recips      = [r.strip() for r in os.environ.get("EMAIL_RECIPIENTS", "").split(",") if r.strip()]
        self.recipients = raw_recipients if raw_recipients else env_recips
        self.smtp_host  = email_cfg.get("smtp_host") or os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port  = int(email_cfg.get("smtp_port") or os.environ.get("SMTP_PORT", "587"))

    def send_alerts(self, events: list[TriggerEvent]) -> int:
        if not events:
            return 0
        handlers = 0
        if self.enabled and self.sender and self.recipients:
            if self._send_email(events):
                handlers += 1
        return handlers

    def _send_email(self, events: list[TriggerEvent]) -> bool:
        grouped: dict[EventType, list[TriggerEvent]] = {et: [] for et in EventType}
        for e in events:
            grouped[e.event_type].append(e)

        date_str   = datetime.now().strftime("%B %d, %Y %H:%M")
        categories = _CATEGORY_META

        ctx = {"date": date_str, "total": len(events),
               "grouped": grouped, "categories": categories}

        html = Template(_HTML_TEMPLATE).render(**ctx)
        text = Template(_TEXT_TEMPLATE).render(**ctx)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"CPG Alert — {datetime.now().strftime('%b %d')} ({len(events)} signals)"
        msg["From"]    = self.sender
        msg["To"]      = ", ".join(self.recipients)
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.recipients, msg.as_string())
            print(f"  [Email] Digest sent → {self.recipients} ({len(events)} events)")
            return True
        except Exception as exc:
            print(f"  [Email] Failed: {exc}")
            return False
