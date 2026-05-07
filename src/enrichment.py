"""
Website + BuiltWith enrichment for CPG trigger events.

Press text rarely names a brand's 3PL, co-manufacturer, or e-commerce stack.
But the brand's own website almost always exposes its tech stack — Shopify
ships a `Shopify.theme` global, BigCommerce sets `<meta name="generator"
content="BigCommerce">`, etc. This module fetches the company website
homepage and inspects it for those tells.

If a `BUILTWITH_API_KEY` is configured, we additionally call BuiltWith's
free-tier domain endpoint for a deeper read (paid integrations, payment
processors, EDI providers). The API call is wrapped in a try/except —
enrichment is strictly best-effort and never blocks event ingestion.

Detected products are merged into `event.tech_stack` and re-evaluated for
DOSS-integration overlap, which updates `event.integration_match`.
"""

from __future__ import annotations

import os
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

# Press-style boilerplate sometimes credits a 3PL or co-man explicitly on the
# About / Press / Sustainability page. Cheap to search for these on homepage HTML.
_HOMEPAGE_3PL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(?:fulfilled by|powered by|partnered with)\s+([A-Z][\w&\.\- ]{2,40})", re.I),
]


def enrich_event(
    event: TriggerEvent,
    timeout: float = 6.0,
    user_agent: str = "Mozilla/5.0 (compatible; CPGTriggerEventSearch/2.0)",
) -> TriggerEvent:
    """Fetch the brand's website + (optional) BuiltWith and merge tech-stack hits.

    Idempotent and side-effect-free outside `event` mutation. Any failure is
    swallowed — this is a *best-effort* enrichment pass.
    """
    site = event.company_website
    if not site:
        return event

    new_stack = list(event.tech_stack or [])
    new_integrations = list(event.integration_match or [])

    # ── Homepage fingerprint pass ────────────────────────────────────────────
    html = _fetch_homepage(site, timeout=timeout, user_agent=user_agent)
    if html:
        for rx, key in _HOMEPAGE_FINGERPRINTS:
            if rx.search(html) and key not in new_stack:
                new_stack.append(key)

    # ── BuiltWith API (optional) ─────────────────────────────────────────────
    builtwith_key = os.getenv("BUILTWITH_API_KEY")
    if builtwith_key:
        bw_techs = _query_builtwith(site, builtwith_key, timeout=timeout)
        for tech in bw_techs:
            tech_lc = tech.lower()
            if tech_lc not in new_stack:
                new_stack.append(tech_lc)

    # ── Promote new tech-stack hits into integration_match ───────────────────
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


def _query_builtwith(domain: str, api_key: str, timeout: float) -> list[str]:
    """Call BuiltWith's domain API and return the flat list of detected tech names.

    Free-tier endpoint: https://api.builtwith.com/free1/api.json?KEY=...&LOOKUP=...
    """
    apex = domain.replace("https://", "").replace("http://", "").split("/", 1)[0]
    try:
        resp = requests.get(
            "https://api.builtwith.com/free1/api.json",
            params={"KEY": api_key, "LOOKUP": apex},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    techs: list[str] = []
    for group in data.get("groups", []):
        for cat in group.get("categories", []):
            for tech in cat.get("technologies", []):
                name = tech.get("name")
                if name:
                    techs.append(name)
    return techs
