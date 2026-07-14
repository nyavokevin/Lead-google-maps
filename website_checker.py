"""
website_checker.py
-------------------
Pings each lead's website and classifies it as:
    - "missing"  : no website field at all
    - "broken"   : timeout, connection error, or HTTP 4xx/5xx (incl. 404)
    - "ok"       : responded with a 2xx/3xx status

For "missing"/"broken" leads, attaches a ready-to-use French outreach note
tailored to restaurants (pitches booking/delivery/ERP — the exact pitch a
site-less or broken-site restaurant most plausibly needs).

Usage:
    from website_checker import check_leads_websites
    leads = check_leads_websites(leads, max_workers=10)
    # each lead now has: lead["website_status"], lead["website_note"]
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

TIMEOUT_SECONDS = 8
USER_AGENT = "Mozilla/5.0 (compatible; LeadFinderBot/1.0; +https://example.com/bot)"


def _broken_note() -> str:
    return (
        "j'ai vu que votre site web ne marche pas actuellement (page inaccessible). "
        "Ca peut faire perdre des reservations et des commandes a emporter. "
        "On propose justement des solutions simples de reservation en ligne, "
        "gestion des commandes/livraison et un petit systeme de gestion (ERP) "
        "pensees pour les restaurants — je peux vous montrer ca en 2 minutes ?"
    )


def _missing_note() -> str:
    return (
        "j'ai vu que vous n'avez pas encore de site web. C'est souvent ce qui manque "
        "pour capter les reservations et les commandes en ligne. On propose un site "
        "avec reservation, commande a emporter/livraison et gestion (ERP) cle en main "
        "pour les restaurants — ca vous interesserait d'en discuter ?"
    )


def check_website(url: str | None, timeout: int = TIMEOUT_SECONDS) -> dict[str, Any]:
    """Checks a single URL. Returns status/http_status/note/error."""
    if not url or not url.strip():
        return {"status": "missing", "http_status": None, "note": _missing_note(), "error": None}

    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True, headers=headers)
        # Some servers don't implement HEAD properly (405/403) -> fall back to GET.
        if resp.status_code in (403, 405) or resp.status_code >= 500:
            resp = requests.get(url, timeout=timeout, allow_redirects=True, headers=headers)

        if resp.status_code >= 400:
            return {
                "status": "broken",
                "http_status": resp.status_code,
                "note": _broken_note(),
                "error": None,
            }
        return {"status": "ok", "http_status": resp.status_code, "note": None, "error": None}

    except requests.exceptions.RequestException as e:
        return {
            "status": "broken",
            "http_status": None,
            "note": _broken_note(),
            "error": str(e),
        }


def check_leads_websites(leads: list[dict[str, Any]], max_workers: int = 10) -> list[dict[str, Any]]:
    """
    Mutates and returns `leads`, adding to each:
        website_status : "ok" | "broken" | "missing"
        website_note   : French outreach note, or None if the site is fine
        website_http_status : int | None
    Runs checks concurrently since this can be dozens/hundreds of leads.
    """
    def _run(idx_lead):
        idx, lead = idx_lead
        result = check_website(lead.get("website"))
        return idx, result

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_run, (i, lead)) for i, lead in enumerate(leads)]
        for future in as_completed(futures):
            idx, result = future.result()
            leads[idx]["website_status"] = result["status"]
            leads[idx]["website_note"] = result["note"]
            leads[idx]["website_http_status"] = result["http_status"]

    ok = sum(1 for l in leads if l["website_status"] == "ok")
    broken = sum(1 for l in leads if l["website_status"] == "broken")
    missing = sum(1 for l in leads if l["website_status"] == "missing")
    print(f"  🌐 Website check: {ok} ok, {broken} broken, {missing} missing")

    return leads
