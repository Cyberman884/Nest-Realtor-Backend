import os
import re
import requests
from typing import Dict, List

# =========================
# CONFIG
# =========================

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


# =========================
# QUERY INTERPRETATION
# =========================

def interpret_query(query: str) -> Dict:
    """
    Very lightweight intent + location extractor.
    This does NOT need to be perfect.
    """
    query = query.lower()

    location_match = re.search(r"in ([a-zA-Z\s]+)", query)
    location = location_match.group(1).strip() if location_match else None

    intent = "agent"
    if "seller" in query or "owner" in query:
        intent = "seller"

    return {
        "raw_query": query,
        "location": location,
        "intent": intent
    }


# =========================
# REAL LEAD ENGINE (GOOGLE PLACES)
# =========================

def try_real_leads(filters: Dict) -> List[Dict]:
    """
    Attempts to fetch REAL leads using Google Places API.
    If anything fails, returns [] and allows fallback.
    """

    if not GOOGLE_API_KEY:
        return []

    location = filters.get("location")
    if not location:
        return []

    query = f"real estate agent in {location}"

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": GOOGLE_API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    leads = []

    for place in data.get("results", [])[:5]:
        leads.append({
            "lead_type": "agent",
            "name": place.get("name"),
            "agency": place.get("name"),
            "address": place.get("formatted_address"),
            "source": "google-places"
        })

    return leads


# =========================
# FALLBACK LEAD GENERATOR
# =========================

def generate_fallback_lead(filters: Dict) -> Dict:
    """
    Guaranteed non-empty fallback so the API never fails.
    """
    location = filters.get("location") or "your area"

    return {
        "lead_type": "agent",
        "name": "Local Real Estate Agent",
        "agency": f"{location.title()} Realty",
        "address": location,
        "source": "fallback"
    }


# =========================
# MAIN ENGINE ENTRY
# =========================

def generate_leads(query: str) -> Dict:
    """
    Main engine entry point.
    This is what main.py should call.
    """

    filters = interpret_query(query)

    leads = try_real_leads(filters)

    if leads:
        return {
            "success": True,
            "engine": "google-places",
            "leads": leads
        }

    # fallback
    return {
        "success": True,
        "engine": "fallback",
        "leads": [generate_fallback_lead(filters)]
    }
