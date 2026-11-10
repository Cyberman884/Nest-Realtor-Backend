"""Nest Realtor V2 - Serper-powered multi-source public property discovery.

Drop-in replacement for the previous OpenAI discovery_engine.py. Keeps the same
public function contract: generate_discovery_leads(location, property_type,
max_results_per_source, sources) -> dict with leads/source diagnostics.

Requires SERPER_API_KEY in Render. No OpenAI API key or OpenAI credits required. OwnersOnly is paused unless written permission is confirmed via OWNERSONLY_PERMISSION_CONFIRMED=true.
Serper's standard API: POST https://google.serper.dev/search with X-API-KEY.

Important: the configured entries are search targets, not confirmed data partnerships
or APIs. Serper searches public Google-indexed results. It cannot see private,
login-only, blocked, or unindexed listings. It does not guarantee exclusivity.
"""
from __future__ import annotations

import concurrent.futures
import logging
import os
import re
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)
SERPER_URL = "https://google.serper.dev/search"
# Never accept mainstream agent portals/aggregators or agency/auction domains,
# including when a generic discovery query finds them.
EXCLUDED_HOST_FRAGMENTS = (
    # Mainstream portals and aggregators where agents commonly advertise.
    "property24.com", "privateproperty.co.za", "iolproperty.co.za", "propertycentral.co.za",
    "property.co.za", "homehunt.co.za", "myroof.co.za", "immoafrica.net", "myproperty.co.za",
    "trovit.", "mitula.", "nestoria.", "properstar.", "propertyfox.",
    # Estate agency brands and franchise/branch sites.
    "rawson.co.za", "pamgolding.co.za", "seeff.com", "remax.co.za", "justproperty.co.za",
    "chas-everitt.co.za", "jawitz.co.za", "tysonprop.co.za", "dpgprop.co.za", "huizemark.com",
    "leapfrog.co.za", "century21.co.za", "kwsa.co.za", "harcourts.co.za", "expsouthafrica.com",
    # Auction platforms and auctioneers are deliberately excluded.
    "aucor.com", "aldes.co.za", "aldesauctions.co.za", "auctionnation.co.za", "openauctions.co.za",
    "auctioncentral.co.za", "goauctions.co.za", "gemfinder.co.za", "sheriffauctions.co.za",
)

SERPER_GL = (os.getenv("SERPER_GL") or "za").strip().lower()
SERPER_HL = (os.getenv("SERPER_HL") or "en").strip().lower()
DISCOVERY_TIMEOUT = int(os.getenv("DISCOVERY_TIMEOUT", "35"))
DISCOVERY_MAX_WORKERS = max(1, min(5, int(os.getenv("DISCOVERY_MAX_WORKERS", "3"))))
DEFAULT_MAX_RESULTS_PER_SOURCE = max(1, min(10, int(os.getenv("DISCOVERY_MAX_RESULTS_PER_SOURCE", "5"))))

# Deliberately excludes mainstream agent-heavy portals, agency websites, auction
# sources, and aggregators that commonly syndicate agent listings. Keep only
# owner-direct marketplaces/classifieds and public community/bank-sale discovery.
DISCOVERY_SOURCES: List[Dict[str, str]] = [
    {"key": "junk_mail", "name": "Junk Mail Classifieds - Owner Direct", "kind": "classifieds", "aliases": "junk mail|junkmail", "domain": "junkmail.co.za", "owner_direct_only": "true"},
    {"key": "noagent", "name": "NoAgent Owner-Direct Listings", "kind": "owner-direct marketplace", "aliases": "noagent|no agent", "domain": "noagent.co.za", "owner_direct_only": "true"},
    {"key": "ownerselling", "name": "OwnerSelling", "kind": "owner-direct marketplace", "aliases": "ownerselling|owner selling", "domain": "ownerselling.co.za", "owner_direct_only": "true"},
    {"key": "privately", "name": "Privately - Private Seller Listings", "kind": "private-owner marketplace", "aliases": "privately|privately.co.za", "domain": "privately.co.za", "owner_direct_only": "true"},
    {"key": "ownersonly", "name": "OwnersOnly", "kind": "private-owner marketplace", "aliases": "ownersonly|owners only", "domain": "ownersonly.co.za", "requires_permission": "true", "owner_direct_only": "true"},
    {"key": "classads", "name": "ClassAds Classifieds - Owner Direct", "kind": "classifieds", "aliases": "classads", "domain": "classads.co.za", "owner_direct_only": "true"},
    {"key": "bob_shop", "name": "Bob Shop Classifieds - Owner Direct", "kind": "classifieds", "aliases": "bob shop|bobshop", "domain": "bobshop.co.za", "owner_direct_only": "true"},
    {"key": "locanto", "name": "Locanto Classifieds - Owner Direct", "kind": "classifieds", "aliases": "locanto", "domain": "locanto.co.za", "owner_direct_only": "true"},
    {"key": "facebook_property_groups", "name": "Public Facebook Property Groups - Owner Direct", "kind": "public social listings", "aliases": "facebook|property for sale|house for sale", "domain": "facebook.com", "owner_direct_only": "true"},
    {"key": "facebook_private_sellers", "name": "Facebook Private-Seller Property Pages", "kind": "public social listings", "aliases": "facebook|private seller|owner selling", "domain": "facebook.com", "owner_direct_only": "true"},
    {"key": "neighbourhood_classifieds", "name": "Public Neighbourhood Classifieds - Owner Direct", "kind": "public community classifieds", "aliases": "classifieds|community|for sale", "allow_any_domain": "true", "owner_direct_only": "true"},
    {"key": "property_for_sale_forums", "name": "Public Property-for-Sale Forums - Owner Direct", "kind": "public property forums", "aliases": "property forum|property for sale|house for sale", "allow_any_domain": "true", "owner_direct_only": "true"},
    {"key": "bank_assisted_sales", "name": "Direct Bank-Assisted Sales", "kind": "bank-direct property sales", "aliases": "bank assisted|bank property sale|property for sale", "allow_any_domain": "true", "owner_direct_only": "true"},
    {"key": "bank_repossessions", "name": "Direct Bank Repossessions", "kind": "bank repossession listings", "aliases": "bank repossession|repossessed property|bank property", "allow_any_domain": "true", "owner_direct_only": "true"},
    {"key": "owner_direct_web", "name": "Other Public Owner-Direct Property Adverts", "kind": "owner-direct public pages", "aliases": "owner selling|private seller|owner direct", "allow_any_domain": "true", "owner_direct_only": "true"},
]

LEAD_FIELDS = [
    "title", "property_type", "price", "address", "suburb", "city", "province",
    "bedrooms", "bathrooms", "seller_type", "seller_name", "phone", "email",
    "listing_url", "source_evidence", "seller_intent_signals", "exclusivity_status",
    "exclusivity_evidence", "opportunity_type", "confidence",
]


def _clean_text(value: Any, limit: int = 1200) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = str(value)
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


def _valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _normalise_words(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _source_match(result: Dict[str, Any], source: Dict[str, str]) -> bool:
    """Confirm source identity, or allow carefully constrained generic public searches."""
    raw_host = urlparse(str(result.get("link") or "")).netloc.lower().replace("www.", "")
    if any(fragment in raw_host for fragment in EXCLUDED_HOST_FRAGMENTS):
        return False
    host = _normalise_words(raw_host)
    text = _normalise_words(" ".join(str(result.get(k) or "") for k in ("title", "snippet", "link")))
    domains = [d.strip() for d in source.get("domain", "").split("|") if d.strip()]
    if any(_normalise_words(domain) in host for domain in domains):
        return True
    aliases = [a.strip() for a in source.get("aliases", "").split("|") if a.strip()]
    name_phrase = _normalise_words(source["name"])
    if any((phrase := _normalise_words(candidate)) and (phrase in host or phrase in text)
           for candidate in aliases + [name_phrase]):
        return True
    return source.get("allow_any_domain") == "true"


def _extract_price(text: str) -> str:
    patterns = [r"R\s?\d[\d\s,]*(?:\.\d{2})?", r"ZAR\s?\d[\d\s,]*(?:\.\d{2})?"]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(0)).strip()
    return ""


def _extract_number(text: str, labels: str) -> str:
    m = re.search(r"(\d{1,2})\s*(?:" + labels + r")\b", text, re.I)
    return m.group(1) if m else ""


def _query_for(source: Dict[str, str], location: str, property_type: str) -> str:
    kind = property_type if property_type and property_type.lower() not in ("all", "all property types") else "property"
    if "for sale" not in kind.lower():
        kind = kind + " for sale"
    domain = source.get("domain", "").strip()
    if domain:
        domain_clause = " OR ".join(f"site:{d.strip()}" for d in domain.split("|") if d.strip())
        if source["key"] in ("facebook_property_groups", "facebook_private_sellers"):
            extra = "public group owner private seller" if source["key"] == "facebook_property_groups" else "private seller owner direct"
            return f'({domain_clause}) {kind} {location} South Africa {extra}'
        return f'({domain_clause}) {kind} {location} South Africa ("owner selling" OR "private seller" OR "for sale by owner" OR "no agent")'
    exclusions = " ".join(
        f"-site:{d}" for d in (
            "property24.com", "privateproperty.co.za", "iolproperty.co.za",
            "propertycentral.co.za", "property.co.za", "homehunt.co.za", "propertyfox.co.za",
            "myroof.co.za", "immoafrica.net", "myproperty.co.za", "trovit.co.za",
            "mitula.co.za", "nestoria.co.za", "properstar.com",
            "rawson.co.za", "pamgolding.co.za", "seeff.com", "remax.co.za",
            "justproperty.co.za", "chas-everitt.co.za", "jawitz.co.za", "tysonprop.co.za",
            "dpgprop.co.za", "huizemark.com", "leapfrog.co.za", "century21.co.za",
            "kwsa.co.za", "harcourts.co.za", "expsouthafrica.com", "aucor.com",
            "aldes.co.za", "auctionnation.co.za", "openauctions.co.za", "auctioncentral.co.za",
            "goauctions.co.za", "gemfinder.co.za",
        )
    )
    extra_queries = {
        "neighbourhood_classifieds": f'({kind} OR "owner selling" OR "private seller") {location} South Africa neighbourhood classifieds {exclusions}',
        "property_for_sale_forums": f'("{kind}" OR "owner selling") {location} South Africa property forum classifieds {exclusions}',
        "bank_assisted_sales": f'("bank assisted sale" OR "assisted sale" OR "bank property") {kind} {location} South Africa {exclusions}',
        "bank_repossessions": f'("bank repossessed" OR "repossessed property" OR "bank property") {kind} {location} South Africa {exclusions}',
        "owner_direct_web": f'("owner selling" OR "private seller" OR "owner direct") {kind} {location} South Africa {exclusions}',
    }
    return extra_queries.get(source["key"], f'"{source["name"]}" {kind} {location} South Africa')


def _serper_search(source: Dict[str, str], location: str, property_type: str,
                   max_results: int) -> Tuple[List[Dict[str, Any]], str]:
    api_key = (os.getenv("SERPER_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("SERPER_API_KEY is not configured on the backend")
    query = _query_for(source, location, property_type)
    response = requests.post(
        SERPER_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "gl": SERPER_GL, "hl": SERPER_HL, "num": max(10, min(10, max_results * 2))},
        timeout=DISCOVERY_TIMEOUT,
    )
    if not response.ok:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:400]
        raise RuntimeError(f"Serper API error ({response.status_code}): {detail}")
    data = response.json()
    organic = data.get("organic", [])
    if not isinstance(organic, list):
        organic = []
    return organic, query


def _location_evidence(text: str, location: str) -> bool:
    haystack = _normalise_words(text)
    parts = [p for p in re.split(r"[,/]", location) if len(p.strip()) >= 3]
    # Require the specific requested place phrase or at least its first meaningful token.
    target = _normalise_words(parts[0] if parts else location)
    return bool(target and target in haystack)


def _normalise_lead(item: Dict[str, Any], source: Dict[str, str], location: str) -> Optional[Dict[str, Any]]:
    title = _clean_text(item.get("title"), 300)
    url = _clean_text(item.get("link"), 2000)
    snippet = _clean_text(item.get("snippet"), 1500)
    if not title or not _valid_http_url(url):
        return None
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    generic_paths = {"listings", "properties", "property", "search", "for-sale", "property-for-sale"}
    if len(path_parts) < 2 or (len(path_parts) == 1 and path_parts[0].lower() in generic_paths):
        return None
    evidence = " ".join(x for x in (title, snippet) if x)
    if not re.search(r"\b(for sale|sale|auction|selling|property|house|home|flat|apartment|townhouse|land)\b", evidence, re.I):
        return None
    if not _source_match(item, source):
        return None
    if source.get("owner_direct_only") == "true":
        owner_pattern = r"\b(owner[ -]?sell(?:ing)?|owner[ -]?direct|private[ -]?seller|for sale by owner|sold by owner|no agent|direct from owner|privately owned|bank[ -]owned|bank[ -]assisted|bank[ -]repossessed|repossessed by bank)\b"
        if not re.search(owner_pattern, evidence, re.I):
            return None
    location_verified = _location_evidence(evidence, location)
    price = _extract_price(evidence)
    return {
        "title": title,
        "name": title,
        "property_type": "unknown",
        "price": price,
        "address": "",
        "suburb": "",
        "city": "",
        "province": "",
        "bedrooms": _extract_number(evidence, r"bed(?:room)?s?"),
        "bathrooms": _extract_number(evidence, r"bath(?:room)?s?"),
        "seller_type": "unknown",
        "seller_name": "",
        "phone": "",
        "email": "",
        "listing_url": url,
        "url": url,
        "website": url,
        "source_evidence": snippet or title,
        "seller_intent_signals": [],
        "exclusivity_status": "not_verified",
        "exclusivity_evidence": "",
        "exclusivity_verified": False,
        "opportunity_type": "portal_listing",
        "confidence": "medium" if location_verified else "low",
        "source": source["key"],
        "source_name": source["name"],
        "location": location if location_verified else "",
        "location_verified": location_verified,
        "supplemental": False,
        "discovery_method": "serper_google_search",
        "serper_position": item.get("position"),
    }


def _dedupe_key(lead: Dict[str, Any]) -> str:
    url = _clean_text(lead.get("listing_url")).lower().rstrip("/").split("?")[0]
    return "url:" + url if url else "title:" + _normalise_words(lead.get("title", ""))


def _are_probable_duplicates(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    ta = _normalise_words(a.get("title", ""))
    tb = _normalise_words(b.get("title", ""))
    return bool(ta and tb and SequenceMatcher(None, ta, tb).ratio() >= 0.94)


def _search_one_source(source: Dict[str, str], location: str, property_type: str,
                       max_results: int) -> Dict[str, Any]:
    started = time.time()
    status: Dict[str, Any] = {"source": source["key"], "source_name": source["name"],
        "status": "error", "raw_count": 0, "error": "", "query": "", "duration_seconds": 0}
    try:
        if source.get("requires_permission") == "true" and os.getenv("OWNERSONLY_PERMISSION_CONFIRMED", "false").strip().lower() not in ("1", "true", "yes", "on"):
            status["status"] = "skipped_permission"
            status["error"] = "Search disabled pending written permission: OwnersOnly terms prohibit copying, scraping or harvesting listings/contact details."
            status["leads"] = []
            return status
        results, query = _serper_search(source, location, property_type, max_results)
        status["query"] = query
        leads = []
        for item in results:
            if not isinstance(item, dict):
                continue
            lead = _normalise_lead(item, source, location)
            if lead:
                leads.append(lead)
            if len(leads) >= max_results:
                break
        status["status"] = "searched" if leads else "no_results"
        status["raw_count"] = len(leads)
        status["leads"] = leads
        status["notes"] = "Google organic results checked; public/indexed pages only. Results are not proof of seller identity, contact permission, exclusivity or mandate."
    except Exception as exc:
        status["status"] = "error"
        status["error"] = str(exc)[:800]
        status["leads"] = []
        logger.warning("Serper discovery failed for %s: %s", source["name"], exc)
    status["duration_seconds"] = round(time.time() - started, 2)
    return status


def generate_discovery_leads(location: str, property_type: str = "",
                             max_results_per_source: Optional[int] = None,
                             sources: Optional[List[str]] = None) -> Dict[str, Any]:
    location = _clean_text(location, 250)
    property_type = _clean_text(property_type or "property", 100)
    if not location:
        return {"success": False, "engine": "serper_multi_source_discovery", "count": 0, "leads": [], "error": "Location is required"}
    if not (os.getenv("SERPER_API_KEY") or "").strip():
        return {"success": False, "engine": "serper_multi_source_discovery", "count": 0, "leads": [], "error": "SERPER_API_KEY is not configured on the backend"}
    max_results = max(1, min(10, int(max_results_per_source or DEFAULT_MAX_RESULTS_PER_SOURCE)))
    selected_keys = set(sources or [])
    selected = [s for s in DISCOVERY_SOURCES if not selected_keys or s["key"] in selected_keys]
    if not selected:
        return {"success": False, "engine": "serper_multi_source_discovery", "count": 0, "leads": [], "error": "No requested source keys matched", "available_sources": [s["key"] for s in DISCOVERY_SOURCES]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(DISCOVERY_MAX_WORKERS, len(selected))) as pool:
        results = list(pool.map(lambda s: _search_one_source(s, location, property_type, max_results), selected))
    combined, seen = [], set()
    duplicate_count = 0
    for result in results:
        for lead in result.get("leads", []):
            key = _dedupe_key(lead)
            if key in seen or any(_are_probable_duplicates(lead, old) for old in combined):
                duplicate_count += 1
                continue
            seen.add(key)
            combined.append(lead)
    source_counts = {r["source"]: r.get("raw_count", 0) for r in results}
    successful = [r["source"] for r in results if r.get("status") in ("searched", "no_results")]
    errors = [{"source": r["source"], "source_name": r["source_name"], "error": r.get("error")} for r in results if r.get("status") == "error"]
    return {
        "success": bool(successful), "engine": "serper_multi_source_discovery",
        "requested_location": location, "property_type": property_type,
        "count": len(combined), "sources": [s["key"] for s in selected],
        "successful_sources": successful, "source_counts": source_counts,
        "duplicate_count": duplicate_count, "leads": combined,
        "source_diagnostics": results, "errors": errors,
        "exclusivity_note": "A private-owner listing is not automatically an exclusive agent mandate. Exclusivity is not verified by Google search snippets.",
        "search_provider": "Serper Google Search API",
    }
