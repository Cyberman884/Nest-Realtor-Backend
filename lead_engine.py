import os
import requests
from typing import Dict

from filter_leads import filter_leads
from gumtree import search_gumtree


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# ==========================================================
# TEST MODE
# ==========================================================

# Facebook Marketplace is disabled for now.
#
# Reason:
# During testing the Facebook actor returned listings
# from the USA even when Soshanguve was requested.
#
# It was also consuming Apify usage.
#
# We will re-enable it after the Gumtree pipeline works.
FACEBOOK_ENABLED = False


# Keep Gumtree scraping small while testing.
GUMTREE_MAX_ITEMS = 4


# ==========================================================
# GOOGLE PLACES
# ==========================================================

def get_place_details(place_id):

    try:

        url = (
            "https://maps.googleapis.com/maps/api/"
            "place/details/json"
        )

        params = {

            "place_id": place_id,

            "fields": (
                "name,"
                "formatted_phone_number,"
                "website"
            ),

            "key": GOOGLE_API_KEY
        }

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        data = response.json()

        if data.get("status") == "OK":

            result = data.get(
                "result",
                {}
            )

            return {

                "phone": result.get(
                    "formatted_phone_number"
                ),

                "website": result.get(
                    "website"
                )
            }

        return {}

    except Exception as e:

        print(
            "❌ Place Details Error:",
            str(e)
        )

        return {}


def get_google_supplemental(
    location,
    query="houses for sale"
):

    """
    Google Places is supplemental only.

    It is not treated as the primary
    seller-listing source.
    """

    if not GOOGLE_API_KEY:

        print(
            "⚠️ GOOGLE_API_KEY not configured"
        )

        return []

    try:

        print(
            "🚀 Starting Google Places "
            "(supplemental)"
        )

        url = (
            "https://maps.googleapis.com/maps/api/"
            "place/textsearch/json"
        )

        params = {

            "query": (
                f"{query} in {location}"
            ),

            "key": GOOGLE_API_KEY
        }

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        data = response.json()

        if data.get("status") != "OK":

            print(
                "⚠️ Google Places unavailable:",
                data.get("status")
            )

            return []

        leads = []

        for place in data.get(
            "results",
            []
        )[:10]:

            place_id = place.get(
                "place_id"
            )

            details = (
                get_place_details(
                    place_id
                )
                if place_id
                else {}
            )

            address = place.get(
                "formatted_address"
            )

            leads.append({

                "name": place.get(
                    "name"
                ),

                "title": place.get(
                    "name"
                ),

                "address": address,

                "location": address,

                "rating": place.get(
                    "rating"
                ),

                "user_ratings_total":
                    place.get(
                        "user_ratings_total"
                    ),

                "phone": details.get(
                    "phone"
                ),

                "website": details.get(
                    "website"
                ),

                "source": "google_places",

                "location_verified": bool(
                    address
                ),

                "supplemental": True
            })

        print(
            "✅ Google supplemental results:",
            len(leads)
        )

        return leads

    except Exception as e:

        print(
            "❌ Google Places Exception:",
            str(e)
        )

        return []


# ==========================================================
# MAIN LEAD ENGINE
# ==========================================================

def generate_leads(
    query: str,
    location: str
) -> Dict:

    location = str(
        location or ""
    ).strip()

    if not location:

        return {

            "success": False,

            "engine": "multi_source",

            "count": 0,

            "sources": [],

            "leads": [],

            "error": "Location is required"
        }


    raw_leads = []


    # Track what each source actually produced.
    source_counts = {

        "gumtree": 0,

        "facebook_marketplace": 0,

        "google_places": 0
    }


    # ======================================================
    # PRIMARY SOURCE: GUMTREE
    # ======================================================

    print(
        "🚀 Starting Gumtree"
    )

    try:

        gumtree_results = search_gumtree(

            location=location,

            max_items=GUMTREE_MAX_ITEMS
        )


        if gumtree_results.get(
            "success"
        ):

            gumtree_leads = (
                gumtree_results.get(
                    "leads",
                    []
                )
            )

        else:

            gumtree_leads = []


        source_counts[
            "gumtree"
        ] = len(
            gumtree_leads
        )


        raw_leads.extend(
            gumtree_leads
        )


        print(
            "📦 Gumtree raw listings added:",
            len(gumtree_leads)
        )


    except Exception as e:

        print(
            "❌ Gumtree Error:",
            str(e)
        )


    # ======================================================
    # FACEBOOK
    # ======================================================

    if FACEBOOK_ENABLED:

        print(
            "⚠️ Facebook is enabled."
        )

        # Facebook is intentionally not called
        # in this test version.

    else:

        print(
            "⏸️ Facebook Marketplace disabled "
            "for current testing."
        )


    # ======================================================
    # GOOGLE SUPPLEMENTAL FALLBACK
    # ======================================================

    # Google is only used if Gumtree produced
    # absolutely no raw listings.
    #
    # This prevents Google business results
    # from replacing actual Gumtree listing data.

    if not raw_leads:

        google_leads = (
            get_google_supplemental(
                location,
                query=(
                    query
                    or "houses for sale"
                )
            )
        )


        source_counts[
            "google_places"
        ] = len(
            google_leads
        )


        raw_leads.extend(
            google_leads
        )


        print(
            "📦 Google supplemental "
            "results added:",
            len(google_leads)
        )


    else:

        print(
            "ℹ️ Google Places skipped because "
            "Gumtree returned raw listing data."
        )


    # ======================================================
    # RAW SOURCE DIAGNOSTICS
    # ======================================================

    print(
        "📊 RAW SOURCE COUNTS:",
        source_counts
    )

    print(
        "📊 TOTAL RAW LISTINGS:",
        len(raw_leads)
    )


    # ======================================================
    # FILTER + QUALIFICATION
    # ======================================================

    try:

        leads = filter_leads(

            raw_leads,

            requested_area=location
        )

    except Exception as e:

        print(
            "❌ Filter Error:",
            str(e)
        )

        return {

            "success": False,

            "engine": "multi_source",

            "count": 0,

            "sources": [
                "gumtree"
            ],

            "source_counts":
                source_counts,

            "filtered_source_counts":
                {},

            "leads": [],

            "error": str(e)
        }


    # ======================================================
    # FILTERED SOURCE COUNTS
    # ======================================================

    filtered_source_counts = {}


    for lead in leads:

        source = lead.get(
            "source",
            "unknown"
        )

        filtered_source_counts[
            source
        ] = (
            filtered_source_counts.get(
                source,
                0
            ) + 1
        )


    print(
        "📊 FILTERED SOURCE COUNTS:",
        filtered_source_counts
    )


    print(
        "✅ Returning",
        len(leads),
        "qualified opportunities"
    )


    # ======================================================
    # FINAL RESPONSE
    # ======================================================

    return {

        "success": True,

        "engine": "multi_source",

        "count": len(leads),

        "sources": list(
            source_counts.keys()
        ),

        "source_counts":
            source_counts,

        "filtered_source_counts":
            filtered_source_counts,

        "requested_location":
            location,

        "leads":
            leads
    }