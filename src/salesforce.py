"""
Salesforce cross-reference for the lead dashboard.

Flags dashboard leads that already exist as Accounts in SFDC so sales can see
ownership, account type, and funnel status at a glance — and avoid working a
company that's already owned or closed-lost.

Read-only. Credentials come from Streamlit secrets or environment variables:

    SFDC_USERNAME         Salesforce login (e.g. max@doss.com)
    SFDC_PASSWORD         password
    SFDC_SECURITY_TOKEN   security token (appended to password by the API)
    SFDC_DOMAIN           "login" (production, default) or "test" (sandbox)

The integration degrades gracefully: if `simple-salesforce` isn't installed or
the credentials are missing/invalid, every lookup returns an empty result and
the dashboard simply omits the SFDC badge — nothing errors.
"""

from __future__ import annotations

import os
import re
from typing import Iterable

# Strip scheme + leading www and keep just the registrable host, e.g.
# "https://www.drinkpoppi.com/about" -> "drinkpoppi.com".
_DOMAIN_RE = re.compile(r"^(?:https?://)?(?:www\.)?([^/\s]+)", re.IGNORECASE)


def _secret(key: str) -> str | None:
    """Read a secret from Streamlit secrets, falling back to env — mirrors the
    SUPABASE_* pattern in dashboard.py so configuration is consistent."""
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets.get(key)
    except Exception:
        pass
    return os.environ.get(key)


def normalize_domain(website: str | None) -> str:
    """Bare lowercase host for matching, '' when there's nothing usable."""
    if not website:
        return ""
    match = _DOMAIN_RE.match(str(website).strip().lower())
    return match.group(1) if match else ""


def normalize_name(name: str | None) -> str:
    """Aggressively normalize a company name for fuzzy equality: lowercased,
    alphanumerics only. 'OLIPOP' == 'Olipop', 'Magic Spoon' == 'magic-spoon'."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def get_client():
    """Return an authenticated read-only Salesforce client, or None if the
    library or credentials are unavailable (caller treats None as 'no SFDC')."""
    try:
        from simple_salesforce import Salesforce
    except ImportError:
        return None

    username = _secret("SFDC_USERNAME")
    password = _secret("SFDC_PASSWORD")
    token = _secret("SFDC_SECURITY_TOKEN") or ""
    domain = _secret("SFDC_DOMAIN") or "login"

    if not username or not password:
        return None

    try:
        return Salesforce(
            username=username,
            password=password,
            security_token=token,
            domain=domain,
        )
    except Exception:
        return None


def _soql_escape(value: str) -> str:
    """Escape a string literal for embedding in SOQL."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


# Fields surfaced on the lead card / table. Type + Account_Status__c tell sales
# whether this is a customer, an open prospect, or a dead/closed-lost account.
_ACCOUNT_FIELDS = (
    "Id, Name, Website, Type, Account_Status__c, Industry, "
    "Owner.Name, Last_Activity_Date__c"
)


def lookup_accounts(companies: Iterable[tuple[str | None, str | None]]) -> dict:
    """Cross-reference (company_name, website) pairs against SFDC Accounts.

    Returns a dict keyed by BOTH normalized domain and normalized name, each
    mapping to a small account-info dict. Domain keys are preferred by callers
    because they're far less ambiguous than names (avoids "Poppi" matching
    "Poppin Cobs"). Returns {} when SFDC is unconfigured.
    """
    sf = get_client()
    if sf is None:
        return {}

    names: set[str] = set()
    domains: set[str] = set()
    for name, website in companies:
        if name and str(name).strip():
            names.add(str(name).strip())
        dom = normalize_domain(website)
        if dom:
            domains.add(dom)

    if not names and not domains:
        return {}

    records: list[dict] = []
    try:
        # Query in chunks so neither the SOQL length limit nor the IN-list size
        # is exceeded on dashboards with hundreds of distinct companies.
        name_list = sorted(names)
        domain_list = sorted(domains)
        chunk = 200
        # Pad so zip pairs up cleanly; each loop emits at most `chunk` of each.
        rounds = max(
            (len(name_list) + chunk - 1) // chunk,
            (len(domain_list) + chunk - 1) // chunk,
            1,
        )
        for r in range(rounds):
            n_chunk = name_list[r * chunk : (r + 1) * chunk]
            d_chunk = domain_list[r * chunk : (r + 1) * chunk]
            clauses: list[str] = []
            if n_chunk:
                joined = ", ".join(f"'{_soql_escape(n)}'" for n in n_chunk)
                clauses.append(f"Name IN ({joined})")
            for dom in d_chunk:
                clauses.append(f"Website LIKE '%{_soql_escape(dom)}%'")
            if not clauses:
                continue
            soql = (
                f"SELECT {_ACCOUNT_FIELDS} FROM Account "
                f"WHERE {' OR '.join(clauses)} LIMIT 2000"
            )
            result = sf.query_all(soql)
            records.extend(result.get("records", []))
    except Exception:
        return {}

    matches: dict = {}
    for rec in records:
        owner = rec.get("Owner") or {}
        info = {
            "id": rec.get("Id"),
            "name": rec.get("Name"),
            "website": rec.get("Website"),
            "type": rec.get("Type"),
            "status": rec.get("Account_Status__c"),
            "industry": rec.get("Industry"),
            "owner": owner.get("Name") if isinstance(owner, dict) else None,
            "last_activity": rec.get("Last_Activity_Date__c"),
        }
        dom = normalize_domain(rec.get("Website"))
        if dom:
            matches.setdefault(f"domain:{dom}", info)
        nm = normalize_name(rec.get("Name"))
        if nm:
            matches.setdefault(f"name:{nm}", info)
    return matches


def match_for(matches: dict, company_name: str | None, website: str | None) -> dict | None:
    """Look up one lead in the map produced by lookup_accounts. Domain first
    (high confidence), then normalized name (fallback)."""
    if not matches:
        return None
    dom = normalize_domain(website)
    if dom and f"domain:{dom}" in matches:
        return matches[f"domain:{dom}"]
    nm = normalize_name(company_name)
    if nm and f"name:{nm}" in matches:
        return matches[f"name:{nm}"]
    return None
