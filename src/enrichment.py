"""
Website-stack enrichment for CPG trigger events.

Press text rarely names a brand's 3PL, co-manufacturer, or e-commerce stack.
But the brand's own website almost always exposes its tech stack — Shopify
ships a `Shopify.theme` global, BigCommerce sets `<meta name="generator"
content="BigCommerce">`, Klaviyo / Yotpo / Recharge / Gorgias inject obvious
script tags. This module fetches the company website homepage once and
fingerprints it for those tells.

Detected products are merged into `event.tech_stack` and re-evaluated for
DOSS-integration overlap, which updates `event.integration_match`. The
whole pass is wrapped in try/except — enrichment is strictly best-effort
and never blocks event ingestion.
"""

from __future__ import annotations

import re
from typing import Optional

import requests

from .models import TriggerEvent
from .scrapers.base import DOSS_INTEGRATION_KEYWORDS

# ── Homepage HTML fingerprints ──────────────────────────────────────────────
# Each entry is (regex, canonical-product-key). Keys overlap with the
# DOSS_INTEGRATION_KEYWORDS map so the integration_match list stays consistent.
_HOMEPAGE_FINGERPRINTS: list[tuple[re.Pattern, str]] = [
    # Shopify
    (re.compile(r"cdn\.shopify\.com|Shopify\.theme|/cdn/shop/", re.I), "shopify"),
    (re.compile(r'meta name="shopify-checkout-api-token"', re.I), "shopify"),
    # Shopify Plus (subset of Shopify, but worth tagging)
    (re.compile(r"shopify-plus|Shopify Plus", re.I), "shopify plus"),
    # BigCommerce
    (re.compile(r'meta\s+name="generator"\s+content="BigCommerce"', re.I), "bigcommerce"),
    (re.compile(r"cdn\d+\.bigcommerce\.com", re.I), "bigcommerce"),
    # WooCommerce / Magento
    (re.compile(r"woocommerce", re.I), "woocommerce"),
    (re.compile(r"Magento|mage/cookies", re.I), "magento"),
    # Klaviyo, Yotpo, Gorgias — adjacent CPG stack signals
    (re.compile(r"klaviyo\.com", re.I), "klaviyo"),
    (re.compile(r"yotpo\.com", re.I), "yotpo"),
    (re.compile(r"gorgias\.com", re.I), "gorgias"),
    # Recharge / subscriptions
    (re.compile(r"rechargepayments\.com|rechargeapps\.com", re.I), "recharge"),
    # Faire
    (re.compile(r"faire\.com", re.I), "faire"),
    # ShipStation tracking
    (re.compile(r"shipstation\.com", re.I), "shipstation"),
    # Amazon storefront / vendor central links
    (re.compile(r"amazon\.com/(?:stores|shops|sp)/", re.I), "amazon seller"),
]


def enrich_event(
    event: TriggerEvent,
    timeout: float = 6.0,
    user_agent: str = "Mozilla/5.0 (compatible; CPGTriggerEventSearch/2.0)",
) -> TriggerEvent:
    """Fetch the brand's homepage and merge tech-stack fingerprint hits.

    Idempotent and side-effect-free outside `event` mutation. Any failure is
    swallowed — this is a *best-effort* enrichment pass.
    """
    site = event.company_website
    if not site:
        return event

    html = _fetch_homepage(site, timeout=timeout, user_agent=user_agent)
    if not html:
        return event

    new_stack = list(event.tech_stack or [])
    new_integrations = list(event.integration_match or [])

    for rx, key in _HOMEPAGE_FINGERPRINTS:
        if rx.search(html) and key not in new_stack:
            new_stack.append(key)

    # Promote new tech-stack hits into integration_match.
    combined_lc = " ".join(new_stack).lower()
    for needle, label in DOSS_INTEGRATION_KEYWORDS.items():
        if needle in combined_lc and label not in new_integrations:
            new_integrations.append(label)

    event.tech_stack = new_stack
    event.integration_match = new_integrations
    return event


def _fetch_homepage(
    domain: str, timeout: float, user_agent: str
) -> Optional[str]:
    if not domain:
        return None
    url = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": user_agent},
            allow_redirects=True,
        )
        if resp.status_code == 200 and resp.text:
            return resp.text[:200_000]  # cap at ~200KB
    except requests.RequestException:
        return None
    return None
