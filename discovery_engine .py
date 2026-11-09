"""Nest Realtor V2 - OpenAI-powered multi-source property discovery.

This module is an ADD-ON. It does not replace main.py, lead_engine.py, Gumtree,
Facebook Marketplace, or the existing filter_leads pipeline.

What it does
------------
* Runs one OpenAI Responses API web-search job for each configured marketplace.
* Asks the model to find property-sale advertisements in the requested location and
  extract only information supported by the source page/search result.
* Normalises results into a common Nest Realtor lead shape.
* Deduplicates repeated URLs and likely duplicate property advertisements.
* Keeps exclusivity unverified unless the source contains explicit evidence.
* Reports each source's status so a failed/unsupported source is never shown as
  successfully searched.

Important limitations
---------------------
OpenAI web search is not a guaranteed scraper, marketplace API, or exhaustive
inventory feed. It may find indexed/public pages, but it cannot access private
WhatsApp groups, login-only pages, blocked content, or every listing. Some
configured marketplaces may return no results. Respect each site's terms,
robots/access rules, POPIA, and any applicable direct-marketing requirements.

Environment variables
---------------------
OPENAI_API_KEY       Required. Keep this secret in Render environment variables.
OPENAI_MODEL         Optional. Defaults to gpt-6-astra; change to a model enabled
                     for your API project if needed.
DISCOVERY_TIMEOUT    Optional. Defaults to 90 seconds per source.
DISCOVERY_MAX_WORKERS Optional. Defaults to 3 concurrent source searches.
DISCOVERY_MAX_RESULTS_PER_SOURCE Optional. Defaults to 8.

Example use from Python:
    from discovery_engine import generate_discovery_leads
    result = generate_discovery_leads(
        location="Johannesburg, Gauteng, South Africa",
        property_type="houses",
        max_results_per_source=5,
    )
    print(result["leads"])

Optional integration into lead_engine.py (do this only after testing this file):
    from discovery_engine import generate_discovery_leads
    discovery = generate_discovery_leads(location=location)
    raw_leads.extend(discovery.get("leads", []))

No API keys are stored in this file.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-6-astra").strip()
DISCOVERY_TIMEOUT = int(os.getenv("DISCOVERY_TIMEOUT", "90"))
DISCOVERY_MAX_WORKERS = max(1, min(5, int(os.getenv("DISCOVERY_MAX_WORKERS", "3"))))
DEFAULT_MAX_RESULTS_PER_SOURCE = max(
    1, min(20, int(os.getenv("DISCOVERY_MAX_RESULTS_PER_SOURCE", "8")))
)

# These are the 11 named marketplaces/platforms discussed in the planning.
# They are search targets, NOT confirmed API integrations. The web-search tool
# attempts to find publicly indexed pages for each named platform.
DISCOVERY_SOURCES: List[Dict[str, str]] = [
    {"key": "ownersonly", "name": "OwnersOnly", "kind": "private-owner marketplace"},
    {"key": "privately", "name": "Privately", "kind": "private-owner marketplace"},
    {"key": "nextpropconnect", "name": "NextPropConnect", "kind": "property marketplace"},
    {"key": "sa_hometraders", "name": "SA HomeTraders", "kind": "property marketplace"},
    {"key": "myroof", "name": "MyRoof", "kind": "property portal"},
    {"key": "immoafrica", "name": "ImmoAfrica", "kind": "property portal"},
    {"key": "asset_scout", "name": "Asset Scout South Africa", "kind": "auction and distressed-property aggregator"},
    {"key": "open_auctions", "name": "Open Auctions South Africa", "kind": "property auction platform"},
    {"key": "aldes_auctions", "name": "Aldes Auctions", "kind": "auction platform"},
    {"key": "aucor_property", "name": "Aucor Property", "kind": "property auction platform"},
    {"key": "auction_central", "name": "Auction Central South Africa", "kind": "auction platform"},
]

LEAD_FIELDS = [
    "title",
    "property_type",
    "price",
    "address",
    "suburb",
    "city",
    "province",
    "bedrooms",
    "bathrooms",
    "seller_type",
    "seller_name",
    "phone",
    "email",
    "listing_url",
    "source_evidence",
    "seller_intent_signals",
    "exclusivity_status",
    "exclusivity_evidence",
    "opportunity_type",
    "confidence",
]


def _clean_text(value: Any, limit: int = 1200) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


def _response_text(data: Dict[str, Any]) -> str:
    """Read output text from a Responses API response without SDK dependency."""
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: List[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if isinstance(content, dict) and content.get("type") in ("output_text", "text"):
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "\n".join(parts).strip()


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except (ValueError, TypeError):
        pass
    # Fallback: locate the first JSON object in a response with surrounding text.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except (ValueError, TypeError):
            return None
    return None


def _openai_web_search(source: Dict[str, str], location: str, property_type: str,
                       max_results: int) -> Tuple[Dict[str, Any], List[str]]:
    """Search one source using OpenAI's hosted Responses API web_search tool."""
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured on the backend")

    prompt = f"""
You are researching public property-sale advertisements for Nest Realtor in South Africa.
Search specifically for the platform named {source['name']} ({source['kind']}).
Target location: {location}.
Property type requested: {property_type or 'all residential property types'}.
Find up to {max_results} CURRENT, publicly accessible property-for-sale advertisements
that are actually listed on this platform. Prefer private-owner/direct-seller listings,
but include relevant auction opportunities and ordinary listings when they are on this
specific source. Do not substitute listings from another portal.

Return ONLY a JSON object with this exact shape:
{{
  "source_name": "{source['name']}",
  "search_status": "searched|no_results|source_unavailable|uncertain",
  "notes": "short explanation",
  "leads": [
    {{
      "title": "listing headline",
      "property_type": "house/apartment/townhouse/land/commercial/unknown",
      "price": "price as displayed, or empty",
      "address": "full address if explicitly shown, otherwise empty",
      "suburb": "suburb if explicitly shown, otherwise empty",
      "city": "city if explicitly shown, otherwise empty",
      "province": "province if explicitly shown, otherwise empty",
      "bedrooms": "number or empty",
      "bathrooms": "number or empty",
      "seller_type": "private_owner|agent|auctioneer|developer|unknown",
      "seller_name": "name only if explicitly published",
      "phone": "phone only if explicitly published",
      "email": "email only if explicitly published",
      "listing_url": "direct listing URL, not just homepage or search page",
      "source_evidence": "brief factual evidence visible in result/page",
      "seller_intent_signals": ["only explicit signals, e.g. urgent sale, price reduced"],
      "exclusivity_status": "verified_exclusive|claimed_exclusive|not_verified",
      "exclusivity_evidence": "exact reason for classification; empty if none",
      "opportunity_type": "private_owner|auction|portal_listing|other",
      "confidence": "high|medium|low"
    }}
  ]
}}

Rules:
- Never invent a property, address, price, seller identity, phone number, email, or URL.
- Only include results with a direct listing URL and credible evidence that they are on
  {source['name']}. If you cannot confirm the source, do not include the listing.
- Only include listings in or clearly relevant to {location}; do not silently widen
  to another city or province.
- Treat exclusivity as verified ONLY if the source explicitly documents an exclusive
  mandate/agreement. A private-owner advert is NOT an exclusive agent lead.
- "claimed_exclusive" is allowed only when the advertisement itself explicitly claims it.
- If evidence is missing, use unknown/not_verified and empty strings.
- Do not infer motivation from price alone. Record only explicit seller signals.
- Do not include rentals, wanted ads, sold properties, duplicate ads, or non-property goods.
- Search the named source even if it is obscure. If it has no searchable listings, report
  no_results or source_unavailable rather than filling the response with other websites.
""".strip()

    body = {
        "model": OPENAI_MODEL,
        "tools": [{
            "type": "web_search",
            "search_context_size": "medium",
            "external_web_access": True,
            "user_location": {
                "type": "approximate",
                "country": "ZA",
                "timezone": "Africa/Johannesburg",
            },
        }],
        "tool_choice": "required",
        "include": ["web_search_call.action.sources"],
        "max_output_tokens": 5000,
        "input": prompt,
    }
    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=DISCOVERY_TIMEOUT,
    )
    if not response.ok:
        # Avoid logging the API key or request headers.
        try:
            error_body = response.json()
            message = error_body.get("error", {}).get("message") or response.text[:500]
        except ValueError:
            message = response.text[:500]
        raise RuntimeError(f"OpenAI API error ({response.status_code}): {message}")

    data = response.json()
    output_text = _response_text(data)
    parsed = _extract_json(output_text)
    if parsed is None:
        raise RuntimeError("OpenAI returned a response that could not be parsed as the required JSON")

    consulted_sources: List[str] = []
    for item in data.get("output", []) or []:
        if isinstance(item, dict) and item.get("type") == "web_search_call":
            action = item.get("action") or {}
            for src in action.get("sources", []) or []:
                if isinstance(src, dict) and src.get("url"):
                    consulted_sources.append(str(src["url"]))

    return parsed, consulted_sources


def _valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _normalise_lead(raw: Dict[str, Any], source: Dict[str, str], location: str) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    url = _clean_text(raw.get("listing_url"), 2000)
    title = _clean_text(raw.get("title"), 300)
    if not title or not _valid_http_url(url):
        return None

    lead: Dict[str, Any] = {field: raw.get(field, "") for field in LEAD_FIELDS}
    for key in LEAD_FIELDS:
        if key == "seller_intent_signals":
            value = lead.get(key)
            lead[key] = value if isinstance(value, list) else ([str(value)] if value else [])
        else:
            lead[key] = _clean_text(lead.get(key), 1500)

    lead.update({
        "title": title,
        "listing_url": url,
        "source": source["key"],
        "source_name": source["name"],
        # Do not fill a missing property location with the search target.
        # That would make an unlocated listing look location-verified downstream.
        "location": _clean_text(lead.get("address") or lead.get("suburb") or lead.get("city")),
        "location_verified": bool(lead.get("address") or lead.get("suburb") or lead.get("city")),
        "supplemental": False,
        "discovery_method": "openai_web_search",
        "exclusivity_verified": lead.get("exclusivity_status") == "verified_exclusive" and bool(lead.get("exclusivity_evidence")),
    })

    # Never silently upgrade an unsubstantiated exclusivity claim.
    if lead.get("exclusivity_status") not in ("verified_exclusive", "claimed_exclusive"):
        lead["exclusivity_status"] = "not_verified"
        lead["exclusivity_evidence"] = ""
        lead["exclusivity_verified"] = False
    elif lead.get("exclusivity_status") == "verified_exclusive" and not lead.get("exclusivity_evidence"):
        lead["exclusivity_status"] = "not_verified"
        lead["exclusivity_verified"] = False

    return lead


def _dedupe_key(lead: Dict[str, Any]) -> str:
    url = _clean_text(lead.get("listing_url")).lower().rstrip("/")
    if url:
        return "url:" + url.split("?")[0]
    address = _clean_text(lead.get("address") or lead.get("suburb")).lower()
    title = _clean_text(lead.get("title")).lower()
    return "property:" + re.sub(r"[^a-z0-9]", "", address + title)


def _are_probable_duplicates(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    address_a = re.sub(r"[^a-z0-9]", "", _clean_text(a.get("address") or a.get("suburb")).lower())
    address_b = re.sub(r"[^a-z0-9]", "", _clean_text(b.get("address") or b.get("suburb")).lower())
    if address_a and address_b and address_a == address_b:
        return True
    title_a = re.sub(r"[^a-z0-9]", "", _clean_text(a.get("title")).lower())
    title_b = re.sub(r"[^a-z0-9]", "", _clean_text(b.get("title")).lower())
    area_a = _clean_text(a.get("suburb") or a.get("city")).lower()
    area_b = _clean_text(b.get("suburb") or b.get("city")).lower()
    return bool(title_a and title_b and area_a and area_b and area_a == area_b and SequenceMatcher(None, title_a, title_b).ratio() >= 0.92)


def _search_one_source(source: Dict[str, str], location: str, property_type: str,
                       max_results: int) -> Dict[str, Any]:
    started = time.time()
    status: Dict[str, Any] = {
        "source": source["key"],
        "source_name": source["name"],
        "status": "error",
        "raw_count": 0,
        "error": "",
        "search_urls": [],
        "duration_seconds": 0,
    }
    try:
        parsed, urls = _openai_web_search(source, location, property_type, max_results)
        raw_leads = parsed.get("leads", [])
        if not isinstance(raw_leads, list):
            raw_leads = []
        status["status"] = _clean_text(parsed.get("search_status") or "uncertain", 50)
        if status["status"] not in ("searched", "no_results", "source_unavailable", "uncertain"):
            status["status"] = "uncertain"
        status["notes"] = _clean_text(parsed.get("notes"), 1000)
        status["search_urls"] = urls[:30]
        leads = []
        for item in raw_leads[:max_results]:
            lead = _normalise_lead(item, source, location)
            if lead:
                leads.append(lead)
        status["raw_count"] = len(leads)
        status["leads"] = leads
    except Exception as exc:
        status["status"] = "error"
        status["error"] = str(exc)[:1000]
        status["leads"] = []
        logger.warning("Discovery search failed for %s: %s", source["name"], exc)
    status["duration_seconds"] = round(time.time() - started, 2)
    return status


def generate_discovery_leads(
    location: str,
    property_type: str = "",
    max_results_per_source: Optional[int] = None,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Search all configured marketplaces and return unified seller opportunities.

    Args:
        location: Required target location, e.g. "Johannesburg, Gauteng, South Africa".
        property_type: Optional property type such as houses, apartments, land.
        max_results_per_source: Maximum candidate listings requested per source.
        sources: Optional list of source keys to run. Defaults to all 11.

    Returns:
        Dict with success, engine, location, sources, source_counts, leads and errors.
    """
    location = _clean_text(location, 250)
    property_type = _clean_text(property_type or "all property types", 100)
    if not location:
        return {
            "success": False,
            "engine": "openai_multi_source_discovery",
            "count": 0,
            "leads": [],
            "error": "Location is required",
        }
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        return {
            "success": False,
            "engine": "openai_multi_source_discovery",
            "count": 0,
            "leads": [],
            "error": "OPENAI_API_KEY is not configured on the backend",
        }

    max_results = max_results_per_source or DEFAULT_MAX_RESULTS_PER_SOURCE
    max_results = max(1, min(20, int(max_results)))
    selected_keys = set(sources or [])
    selected_sources = [
        source for source in DISCOVERY_SOURCES
        if not selected_keys or source["key"] in selected_keys
    ]
    if selected_keys and not selected_sources:
        return {
            "success": False,
            "engine": "openai_multi_source_discovery",
            "count": 0,
            "leads": [],
            "error": "None of the requested source keys matched DISCOVERY_SOURCES",
            "available_sources": [s["key"] for s in DISCOVERY_SOURCES],
        }

    source_results: List[Dict[str, Any]] = []
    # Keep concurrency modest: this is an expensive web-search workflow.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(DISCOVERY_MAX_WORKERS, len(selected_sources))) as pool:
        futures = {
            pool.submit(_search_one_source, source, location, property_type, max_results): source
            for source in selected_sources
        }
        for future in concurrent.futures.as_completed(futures):
            source_results.append(future.result())

    source_results.sort(key=lambda item: next(
        (i for i, src in enumerate(selected_sources) if src["key"] == item["source"]), 999
    ))

    combined: List[Dict[str, Any]] = []
    seen_keys = set()
    duplicate_count = 0
    for result in source_results:
        for lead in result.get("leads", []):
            key = _dedupe_key(lead)
            if key in seen_keys or any(_are_probable_duplicates(lead, existing) for existing in combined):
                duplicate_count += 1
                continue
            seen_keys.add(key)
            combined.append(lead)

    source_counts = {result["source"]: result.get("raw_count", 0) for result in source_results}
    successful_sources = [
        result["source"] for result in source_results
        if result.get("status") in ("searched", "no_results", "source_unavailable", "uncertain")
    ]
    errors = [
        {"source": r["source"], "source_name": r["source_name"], "error": r.get("error")}
        for r in source_results if r.get("status") == "error"
    ]

    # A run is successful only if at least one source completed an API search.
    # A successful API call can legitimately return zero listings.
    run_success = any(result.get("status") != "error" for result in source_results)

    return {
        "success": run_success,
        "engine": "openai_multi_source_discovery",
        "requested_location": location,
        "property_type": property_type,
        "count": len(combined),
        "sources": [source["key"] for source in selected_sources],
        "successful_sources": successful_sources,
        "source_counts": source_counts,
        "duplicate_count": duplicate_count,
        "leads": combined,
        "source_diagnostics": source_results,
        "errors": errors,
        "model": OPENAI_MODEL,
        "exclusivity_note": (
            "A private-owner advertisement is not an exclusive mandate. "
            "Only explicit documentary evidence is classified as verified_exclusive."
        ),
    }


def get_discovery_leads(location: str, query: str = "houses for sale") -> List[Dict[str, Any]]:
    """Small adapter if you later want to append results to lead_engine.py."""
    result = generate_discovery_leads(location=location, property_type=query)
    if not result.get("success"):
        logger.warning("OpenAI discovery engine did not run: %s", result.get("error"))
        return []
    return result.get("leads", [])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Nest Realtor OpenAI property discovery")
    parser.add_argument("--location", default="Johannesburg, Gauteng, South Africa")
    parser.add_argument("--property-type", default="houses")
    parser.add_argument("--max-per-source", type=int, default=3)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    output = generate_discovery_leads(
        location=args.location,
        property_type=args.property_type,
        max_results_per_source=args.max_per_source,
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))
