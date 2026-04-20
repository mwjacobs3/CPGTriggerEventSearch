from __future__ import annotations

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from jinja2 import Template

from config import (
    EMAIL_PASSWORD,
    EMAIL_RECIPIENTS,
    EMAIL_SENDER,
    SMTP_HOST,
    SMTP_PORT,
)

if TYPE_CHECKING:
    from searchers.base_searcher import SearchResult

DIGEST_HTML = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; color: #222; max-width: 700px; margin: 0 auto; }
    h1 { color: #1a4f8a; border-bottom: 2px solid #1a4f8a; padding-bottom: 8px; }
    h2 { color: #1a4f8a; margin-top: 32px; font-size: 16px; text-transform: uppercase;
         letter-spacing: 1px; }
    .result { border-left: 4px solid #1a4f8a; padding: 8px 12px; margin-bottom: 14px;
              background: #f7f9fc; }
    .result a { color: #1a4f8a; font-weight: bold; text-decoration: none; font-size: 15px; }
    .result a:hover { text-decoration: underline; }
    .meta { font-size: 12px; color: #666; margin-top: 4px; }
    .summary { font-size: 13px; margin-top: 6px; color: #444; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
             font-size: 11px; font-weight: bold; color: #fff; margin-right: 6px; }
    .badge-launch  { background: #27ae60; }
    .badge-funding { background: #e67e22; }
    .badge-exec    { background: #8e44ad; }
    .footer { font-size: 11px; color: #999; margin-top: 32px; border-top: 1px solid #eee;
              padding-top: 12px; }
    .no-results { color: #888; font-style: italic; }
  </style>
</head>
<body>
  <h1>CPG Trigger Event Digest</h1>
  <p>{{ date }} &nbsp;|&nbsp; <strong>{{ total }}</strong> new signals found</p>

  {% for category, items in grouped.items() %}
  <h2>{{ category }} ({{ items|length }})</h2>
  {% if items %}
    {% for r in items %}
    <div class="result">
      <a href="{{ r.url }}" target="_blank">{{ r.title }}</a>
      <div class="meta">{{ r.source }} &nbsp;·&nbsp; {{ r.published }}</div>
      {% if r.summary %}
      <div class="summary">{{ r.summary[:250] }}{% if r.summary|length > 250 %}…{% endif %}</div>
      {% endif %}
    </div>
    {% endfor %}
  {% else %}
    <p class="no-results">No new results this run.</p>
  {% endif %}
  {% endfor %}

  <div class="footer">
    Sent by CPGTriggerEventSearch &nbsp;·&nbsp; Selling DOSS to the CPG world
  </div>
</body>
</html>
"""

DIGEST_TEXT = """
CPG TRIGGER EVENT DIGEST — {{ date }}
{{ total }} new signals found
{% for category, items in grouped.items() %}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{ category }} ({{ items|length }})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{% if items %}{% for r in items %}
• {{ r.title }}
  {{ r.url }}
  {{ r.source }} | {{ r.published }}
  {{ r.summary[:200] }}
{% endfor %}{% else %}No new results this run.
{% endif %}{% endfor %}
"""


class EmailSender:
    def __init__(self):
        self.sender = EMAIL_SENDER
        self.password = EMAIL_PASSWORD
        self.recipients = EMAIL_RECIPIENTS
        self.smtp_host = SMTP_HOST
        self.smtp_port = SMTP_PORT

    def send_digest(self, results: list[SearchResult]) -> bool:
        if not self.recipients or not self.sender:
            print("[Email] No sender or recipients configured — skipping email.")
            return False

        grouped = self._group_by_category(results)
        date_str = datetime.now().strftime("%B %d, %Y")
        ctx = {"date": date_str, "total": len(results), "grouped": grouped}

        html_body = Template(DIGEST_HTML).render(**ctx)
        text_body = Template(DIGEST_TEXT).render(**ctx)

        subject = f"CPG Alert Digest — {date_str} ({len(results)} signals)"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.recipients, msg.as_string())
            print(f"[Email] Digest sent to {self.recipients} ({len(results)} results)")
            return True
        except Exception as exc:
            print(f"[Email] Failed to send digest: {exc}")
            return False

    @staticmethod
    def _group_by_category(
        results: list[SearchResult],
    ) -> dict[str, list[SearchResult]]:
        order = ["New CPG / Product Launch", "PE / VC Funding", "New Ops / Supply Chain Exec"]
        grouped: dict[str, list[SearchResult]] = {cat: [] for cat in order}
        for r in results:
            if r.category in grouped:
                grouped[r.category].append(r)
            else:
                grouped.setdefault(r.category, []).append(r)
        return grouped
