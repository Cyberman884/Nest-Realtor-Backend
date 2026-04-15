import os
import re
import requests
import logging
from typing import Dict, List, Optional

# =========================
# LOGGING (DEBUG MODE)
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lead-engine")

# =========================
# SAFE IMPORT
# =========================
try:
    from filter_leads import filter_leads
except Exception as e:
    logger.error(f"❌ Failed to import filter_leads: {e}")

    # fallback so app NEVER crashes
    def filter_leads(raw):
        return raw


# =========================
# CONFIG
# =========================
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

if GOOGLE_API_KEY:
    logger.info("✅ Google Places API key loaded")
else:
    logger.warning("⚠️ Google Places API key missing")


# =========================
# QUERY INTERPRETATION
# =========================
def interpret_query(query: str) -> Dict:
    try:
        query_lower = query.lower()

        location_match = re.search(r"in ([a-zA-Z\s]+)", query_lower)
        location = location_match.group(1).strip() if location_match else None

        intent = "agent"
        if "seller" in query_lower or "owner" in query_lower:
            intent = "seller"

        parsed = {
            "raw_query": query_lower,
            "location": location,
            "intent": intent
        }

        logger.info(f"🧠 Parsed query: {parsed}")
        return parsed

    except Exception as e:
        logger.error(f"❌ interpret_query failed: {e}")
        return {
            "raw_query": query,
            "location": None,
            "intent": "agent"
        }


# =========================
# GOOGLE PLACES FETCH
# =========================
def try_real_leads(filters: Dict) -> List[Dict]:

    try:
        if not GOOGLE_API_KEY:
            return []

        location = filters.get("location")
        if not location:
            logger.warning("⚠️ No location provided")
            return []

        query = f"real estate agent in {location}"

        logger.info(f"🌍 Google Places query: {query}")

        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "key": GOOGLE_API_KEY
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        raw_places = data.get("results", [])

        logger.info(f"📦 Raw places found: {len(raw_places)}")

        # =========================
        # FILTER PIPELINE
        # =========================
        clean_leads = filter_leads(raw_places)

        final_leads = []

        # =========================
        # ENRICH LEADS
        # =========================
        for lead in clean_leads:

            try:
                place_id = lead.get("place_id")
                phone = None

                if place_id:
                    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                    details_params = {
                        "place_id": place_id,
                        "fields": "formatted_phone_number",
                        "key": GOOGLE_API_KEY
                    }

                    details_res = requests.get(details_url, params=details_params, timeout=10)
                    details_data = details_res.json()

                    phone = details_data.get("result", {}).get("formatted_phone_number")

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

            except Exception as e:
                logger.warning(f"⚠️ Lead enrichment failed: {e}")
                continue

        logger.info(f"✅ Final leads generated: {len(final_leads)}")

        return final_leads

    except Exception as e:
        logger.error(f"❌ try_real_leads crashed: {e}")
        return []


# =========================
# FALLBACK LEAD
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
# MAIN ENTRY (SAFE)
# =========================
def generate_leads(query: str) -> Dict:

    try:
        logger.info(f"🚀 Incoming query: {query}")

        filters = interpret_query(query)
        leads = try_real_leads(filters)

        if leads:
            return {
                "success": True,
                "engine": "google-places",
                "count": len(leads),
                "leads": leads
            }

        return {
            "success": True,
            "engine": "fallback",
            "count": 1,
            "leads": [generate_fallback_lead(filters)]
        }

    except Exception as e:
        logger.error(f"💥 generate_leads crashed: {e}")

        return {
            "success": False,
            "error": str(e),
            "engine": "crash-safe-fallback",
            "leads": [
                generate_fallback_lead({"location": "unknown"})
            ]
        }