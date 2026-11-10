import os
import requests
from typing import Dict, List, Any

from filter_leads import filter_leads
from gumtree import search_gumtree
from facebook_marketplace import get_facebook_marketplace

# Discovery is an optional add-on. If its module or API configuration is
# unavailable, the existing Gumtree/Facebook/Google pipeline still runs.
try:
    from discovery_engine import generate_discovery_leads
    DISCOVERY_IMPORT_ERROR = None
except Exception as import_error:
    generate_discovery_leads = None
    DISCOVERY_IMPORT_ERROR = str(import_error)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Keep the existing source settings intact.
FACEBOOK_ENABLED = os.getenv("FACEBOOK_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
GUMTREE_MAX_ITEMS = int(os.getenv("GUMTREE_MAX_ITEMS", "4"))
FACEBOOK_MAX_ITEMS = int(os.getenv("FACEBOOK_MAX_ITEMS", "20"))

# Discovery runs when enabled and SERPER_API_KEY is configured.
DISCOVERY_ENABLED = os.getenv("DISCOVERY_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
DISCOVERY_MAX_RESULTS_PER_SOURCE = int(os.getenv("DISCOVERY_MAX_RESULTS_PER_SOURCE", "5"))

# Explicit startup diagnostics: never print the API key itself.
print(
    "DISCOVERY CONFIG | enabled:", DISCOVERY_ENABLED,
    "| module_imported:", bool(generate_discovery_leads),
    "| serper_key_present:", bool((os.getenv("SERPER_API_KEY") or "").strip()),
    "| import_error:", DISCOVERY_IMPORT_ERROR or "none",
    flush=True,
)


def get_place_details(place_id):
    try:
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "name,formatted_phone_number,website",
            "key": GOOGLE_API_KEY,
        }
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "OK":
            result = data.get("result", {})
            return {
                "phone": result.get("formatted_phone_number"),
                "website": result.get("website"),
            }
        return {}
    except Exception as exc:
        print("Place Details Error:", str(exc))
        return {}


def get_google_supplemental(location, query="houses for sale"):
    """Google Places remains supplemental, not a primary listing source."""
    if not GOOGLE_API_KEY:
        print("GOOGLE_API_KEY not configured")
        return []
    try:
        print("Starting Google Places (supplemental)")
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        response = requests.get(
            url,
            params={"query": f"{query} in {location}", "key": GOOGLE_API_KEY},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK":
            print("Google Places unavailable:", data.get("status"))
            return []

        leads = []
        for place in data.get("results", [])[:10]:
            place_id = place.get("place_id")
            details = get_place_details(place_id) if place_id else {}
            address = place.get("formatted_address")
            leads.append({
                "name": place.get("name"),
                "title": place.get("name"),
                "address": address,
                "location": address,
                "rating": place.get("rating"),
                "user_ratings_total": place.get("user_ratings_total"),
                "phone": details.get("phone"),
                "website": details.get("website"),
                "source": "google_places",
                "location_verified": bool(address),
                "supplemental": True,
            })
        print("Google supplemental results:", len(leads))
        return leads
    except Exception as exc:
        print("Google Places Exception:", str(exc))
        return []


def _normalise_discovery_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Add legacy filter/dashboard aliases without discarding discovery evidence."""
    lead = dict(record)
    title = lead.get("title") or lead.get("name") or ""
    address = (
        lead.get("address") or lead.get("suburb") or
        lead.get("city") or lead.get("location") or ""
    )
    source = lead.get("source") or "serper_discovery"

    lead["title"] = title
    lead["name"] = lead.get("name") or title
    lead["address"] = address
    lead["location"] = address or lead.get("location") or ""
    lead["url"] = lead.get("url") or lead.get("listing_url") or ""
    lead["website"] = lead.get("website") or lead.get("listing_url") or ""
    lead["price"] = lead.get("price") or lead.get("current_price") or ""
    lead["seller_type"] = lead.get("seller_type") or lead.get("sellerType") or ""
    lead["source"] = source
    lead["discovery_source"] = source
    lead["discovery_method"] = lead.get("discovery_method") or "serper_google_search"
    lead["supplemental"] = False
    # A private-owner advert is not automatically an exclusive mandate.
    lead["exclusivity_verified"] = bool(
        lead.get("exclusivity_status") == "verified_exclusive"
        and lead.get("exclusivity_evidence")
    )
    return lead


def _record_key(lead: Dict[str, Any]) -> str:
    source = str(lead.get("source") or "").strip().lower()
    url = str(lead.get("listing_url") or lead.get("url") or "").strip().lower().split("?")[0].rstrip("/")
    if url:
        return source + "|url|" + url
    title = str(lead.get("title") or lead.get("name") or "").strip().lower()
    address = str(lead.get("address") or lead.get("location") or "").strip().lower()
    return source + "|property|" + " ".join((title, address))


def _attach_discovery_fields(filtered: List[Dict[str, Any]], raw_discovery: List[Dict[str, Any]]) -> None:
    """The existing filter returns a dashboard-safe subset; restore source evidence."""
    lookup = {}
    for raw in raw_discovery:
        lookup[_record_key(raw)] = raw

    # Match on source + title/address because filter_leads normalises name/title.
    for item in filtered:
        source = str(item.get("source") or "").strip().lower()
        name = str(item.get("name") or item.get("title") or "").strip().lower()
        address = str(item.get("address") or item.get("location") or "").strip().lower()
        match = None
        for raw in raw_discovery:
            if str(raw.get("source") or "").strip().lower() != source:
                continue
            raw_name = str(raw.get("title") or raw.get("name") or "").strip().lower()
            raw_address = str(raw.get("address") or raw.get("location") or raw.get("suburb") or "").strip().lower()
            if name == raw_name and (not address or not raw_address or address == raw_address):
                match = raw
                break
        if match:
            # Preserve discovery-only evidence and useful original fields.
            for key in (
                "listing_url", "source_name", "source_evidence", "seller_intent_signals",
                "exclusivity_status", "exclusivity_evidence", "exclusivity_verified",
                "opportunity_type", "confidence", "property_type", "bedrooms",
                "bathrooms", "seller_name", "email", "description", "discovery_method",
            ):
                if key in match:
                    item[key] = match[key]
            if not item.get("url"):
                item["url"] = match.get("listing_url", "")
            if not item.get("website"):
                item["website"] = match.get("listing_url", "")


def generate_leads(query: str, location: str) -> Dict:
    location = str(location or "").strip()
    query = str(query or "houses for sale").strip()

    if not location:
        return {
            "success": False,
            "engine": "multi_source",
            "count": 0,
            "sources": [],
            "source_counts": {},
            "filtered_source_counts": {},
            "leads": [],
            "error": "Location is required",
        }

    raw_leads: List[Dict[str, Any]] = []
    raw_discovery_leads: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {
        "gumtree": 0,
        "facebook_marketplace": 0,
        "google_places": 0,
    }
    discovery_result: Dict[str, Any] = {
        "success": False,
        "engine": "serper_multi_source_discovery",
        "count": 0,
        "sources": [],
        "source_counts": {},
        "source_diagnostics": [],
        "errors": [],
    }

    # 1. Serper public-web discovery across the 11 configured marketplace targets.
    if DISCOVERY_ENABLED and generate_discovery_leads:
        if (os.getenv("SERPER_API_KEY") or "").strip():
            print("Starting Serper discovery pipeline", flush=True)
            try:
                discovery_result = generate_discovery_leads(
                    location=location,
                    property_type=query,
                    max_results_per_source=DISCOVERY_MAX_RESULTS_PER_SOURCE,
                ) or discovery_result
                if not isinstance(discovery_result, dict):
                    raise RuntimeError("Discovery engine returned an unexpected response type")

                raw_discovery_leads = [
                    _normalise_discovery_record(item)
                    for item in (discovery_result.get("leads") or [])
                    if isinstance(item, dict)
                ]
                for source, count in (discovery_result.get("source_counts") or {}).items():
                    source_counts[source] = int(count or 0)
                raw_leads.extend(raw_discovery_leads)
                print("Search provider:", discovery_result.get("search_provider") or "Serper", flush=True)
                print("Serper discovery candidates added:", len(raw_discovery_leads), flush=True)
                for diagnostic in discovery_result.get("source_diagnostics", []):
                    if isinstance(diagnostic, dict):
                        print(
                            "Serper source:", diagnostic.get("source_name", diagnostic.get("source")),
                            "| status:", diagnostic.get("status"),
                            "| leads:", diagnostic.get("raw_count", 0),
                            "| seconds:", diagnostic.get("duration_seconds", 0),
                            "| note:", diagnostic.get("notes", ""),
                            "| error:", diagnostic.get("error", ""),
                        )
                if discovery_result.get("error"):
                    print("Serper discovery warning:", discovery_result.get("error"))
            except Exception as exc:
                discovery_result = dict(discovery_result)
                discovery_result["error"] = str(exc)
                print("Serper discovery integration error:", str(exc))
        else:
            discovery_result["error"] = "SERPER_API_KEY is not configured"
            print("Serper discovery skipped: SERPER_API_KEY is not configured", flush=True)
    elif not DISCOVERY_ENABLED:
        discovery_result["error"] = "Discovery disabled by DISCOVERY_ENABLED"
        print("Serper discovery skipped: DISCOVERY_ENABLED is false", flush=True)
    elif DISCOVERY_IMPORT_ERROR:
        discovery_result["error"] = DISCOVERY_IMPORT_ERROR
        print("Serper discovery import failed:", DISCOVERY_IMPORT_ERROR, flush=True)
    else:
        discovery_result["error"] = "Discovery function is unavailable for an unknown reason"
        print("Serper discovery skipped: function unavailable for an unknown reason", flush=True)

    # 2. Existing Gumtree source (unchanged call contract).
    print("Starting Gumtree")
    try:
        gumtree_results = search_gumtree(location=location, max_items=GUMTREE_MAX_ITEMS) or {}
        gumtree_leads = gumtree_results.get("leads", []) if gumtree_results.get("success") else []
        gumtree_leads = [item for item in gumtree_leads if isinstance(item, dict)]
        source_counts["gumtree"] = len(gumtree_leads)
        raw_leads.extend(gumtree_leads)
        print("Gumtree raw listings added:", len(gumtree_leads))
    except Exception as exc:
        print("Gumtree Error:", str(exc))

    # 3. Existing Facebook Marketplace source (enabled as in the latest file).
    if FACEBOOK_ENABLED:
        print("Starting Facebook Marketplace")
        try:
            facebook_leads = get_facebook_marketplace(
                location=location,
                max_items=FACEBOOK_MAX_ITEMS,
                query=query,
            ) or []
            facebook_leads = [item for item in facebook_leads if isinstance(item, dict)]
            source_counts["facebook_marketplace"] = len(facebook_leads)
            raw_leads.extend(facebook_leads)
            print("Facebook raw listings added:", len(facebook_leads))
        except Exception as exc:
            print("Facebook integration error:", str(exc))
    else:
        print("Facebook Marketplace disabled")

    # 4. Google Places remains fallback-only, preserving the previous behaviour.
    if not raw_leads:
        google_leads = get_google_supplemental(location, query=query)
        source_counts["google_places"] = len(google_leads)
        raw_leads.extend(google_leads)
        print("Google supplemental results added:", len(google_leads))
    else:
        print("Google Places skipped because another source returned raw records")

    print("RAW SOURCE COUNTS:", source_counts)
    print("TOTAL RAW RECORDS:", len(raw_leads))

    try:
        leads = filter_leads(raw_leads, requested_area=location)
    except Exception as exc:
        print("Filter Error:", str(exc))
        return {
            "success": False,
            "engine": "multi_source",
            "count": 0,
            "sources": list(source_counts.keys()),
            "source_counts": source_counts,
            "filtered_source_counts": {},
            "discovery": discovery_result,
            "leads": [],
            "error": str(exc),
        }

    _attach_discovery_fields(leads, raw_discovery_leads)

    filtered_source_counts: Dict[str, int] = {}
    for lead in leads:
        source = lead.get("source", "unknown")
        filtered_source_counts[source] = filtered_source_counts.get(source, 0) + 1

    print("FILTERED SOURCE COUNTS:", filtered_source_counts)
    print("Returning", len(leads), "qualified opportunities")

    return {
        "success": True,
        "engine": "multi_source",
        "count": len(leads),
        "sources": list(source_counts.keys()),
        "source_counts": source_counts,
        "filtered_source_counts": filtered_source_counts,
        "requested_location": location,
        "discovery": {
            "success": bool(discovery_result.get("success")),
            "engine": discovery_result.get("engine", "serper_multi_source_discovery"),
            "count": discovery_result.get("count", len(raw_discovery_leads)),
            "sources": discovery_result.get("sources", []),
            "successful_sources": discovery_result.get("successful_sources", []),
            "source_counts": discovery_result.get("source_counts", {}),
            "duplicate_count": discovery_result.get("duplicate_count", 0),
            "source_diagnostics": discovery_result.get("source_diagnostics", []),
            "errors": discovery_result.get("errors", []),
            "error": discovery_result.get("error"),
            "exclusivity_note": discovery_result.get("exclusivity_note"),
        },
        "leads": leads,
    }
