# lead_engine.py

import os
import re
import requests
from typing import Dict, List
from filter_leads import filter_leads

# =========================
# CONFIG
# =========================

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


# =========================
# QUERY INTERPRETATION
# =========================

def interpret_query(query: str) -> Dict:
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

    # =========================
    # 🔥 FILTER PIPELINE
    # =========================

    raw_places = data.get("results", [])

    # Pass raw data into your filter system
    clean_leads = filter_leads(raw_places)

    # =========================
    # 🔥 ENRICH WITH PHONE NUMBERS
    # =========================

    final_leads = []

    for lead in clean_leads:
        place_id = lead.get("place_id")

        phone = None

        if place_id:
            try:
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                details_params = {
                    "place_id": place_id,
                    "fields": "formatted_phone_number",
                    "key": GOOGLE_API_KEY
                }

                details_res = requests.get(details_url, params=details_params, timeout=10)
                details_data = details_res.json()

                phone = details_data.get("result", {}).get("formatted_phone_number")

            except Exception:
                phone = None

        final_leads.append({
            "lead_type": "agent",
            "name": lead.get("name"),
            "agency": lead.get("name"),
            "address": lead.get("address"),
            "phone": phone,
            "website": lead.get("website"),
            "priority": lead.get("priority"),
            "source": "google-places"
        })

    return final_leads


# =========================
# FALLBACK LEAD GENERATOR
# =========================

def generate_fallback_lead(filters: Dict) -> Dict:
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

    filters = interpret_query(query)

    leads = try_real_leads(filters)

    if leads:
        return {
            "success": True,
            "engine": "google-places",
            "leads": leads
        }

    return {
        "success": True,
        "engine": "fallback",
        "leads": [generate_fallback_lead(filters)]
    }