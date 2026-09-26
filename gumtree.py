import math
import os

from apify_client import ApifyClient


# ==========================================================
# APIFY
# ==========================================================

APIFY_TOKEN = os.getenv("APIFY_TOKEN")

ACTOR_ID = "solidcode/gumtree-scraper"

client = ApifyClient(
    APIFY_TOKEN
)


# ==========================================================
# APPROXIMATE LOCATION GEO DATA
# ==========================================================
#
# These are practical sanity-check areas.
# They are NOT official municipal boundaries.
#
# They are used to reject obviously incorrect results.
# ==========================================================

LOCATION_GEO = {

    "soshanguve":
        (-25.52, 28.10, 22),

    "pretoria":
        (-25.75, 28.19, 35),

    "johannesburg":
        (-26.20, 28.05, 35),

    "durban":
        (-29.86, 31.02, 35),

    "cape town":
        (-33.93, 18.42, 40),

    "bloemfontein":
        (-29.12, 26.22, 35),

    "east london":
        (-33.02, 27.91, 30),

    "gqeberha":
        (-33.96, 25.60, 35),

    "port elizabeth":
        (-33.96, 25.60, 35),

    "nelspruit":
        (-25.47, 30.98, 30),

    "mbombela":
        (-25.47, 30.98, 30)
}


# ==========================================================
# LOCATION ALIASES
# ==========================================================

LOCATION_ALIASES = {

    "soshanguve": [
        "soshanguve",
        "soshanguve block"
    ],

    "pretoria": [
        "pretoria",
        "tshwane",
        "northern pretoria"
    ],

    "johannesburg": [
        "johannesburg",
        "joburg"
    ],

    "gqeberha": [
        "gqeberha",
        "port elizabeth"
    ],

    "port elizabeth": [
        "port elizabeth",
        "gqeberha"
    ],

    "nelspruit": [
        "nelspruit",
        "mbombela"
    ],

    "mbombela": [
        "mbombela",
        "nelspruit"
    ]
}


# ==========================================================
# VALUE HELPER
# ==========================================================

def _value(item, *keys):

    for key in keys:

        value = item.get(key)

        if value not in (
            None,
            "",
            [],
            {}
        ):

            return value

    return None


# ==========================================================
# NUMBER HELPER
# ==========================================================

def _number(value):

    if value is None:
        return None

    if isinstance(
        value,
        (int, float)
    ):

        return float(value)

    text = str(value)

    text = (
        text
        .replace(",", "")
        .replace("R", "")
        .replace("ZAR", "")
        .strip()
    )

    try:

        return float(text)

    except Exception:

        return None


# ==========================================================
# DISTANCE CALCULATOR
# ==========================================================

def _distance_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    radius = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)

    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (

        math.sin(dlat / 2) ** 2

        +

        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(dlon / 2) ** 2
    )

    return (
        radius
        *
        2
        *
        math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a)
        )
    )


# ==========================================================
# TEXT LOCATION
# ==========================================================

def _text_location(item):

    fields = [

        item.get("location"),

        item.get("postcode"),

        item.get("address"),

        item.get("formattedAddress"),

        item.get("suburb"),

        item.get("area"),

        item.get("city"),

        item.get("town"),

        item.get("locality"),

        item.get("region"),

        item.get("description"),

        item.get("title")
    ]

    parts = []

    for value in fields:

        if value in (
            None,
            "",
            [],
            {}
        ):

            continue

        if isinstance(
            value,
            dict
        ):

            value = " ".join(
                str(v)
                for v in value.values()
            )

        parts.append(
            str(value).lower()
        )

    return " ".join(parts)


# ==========================================================
# LOCATION VALIDATION
# ==========================================================

def _location_is_plausible(
    item,
    requested_location
):

    requested = str(
        requested_location or ""
    ).strip().lower()

    if not requested:

        return (
            True,
            "No location filter"
        )


    # ------------------------------------------------------
    # RAW LOCATION
    # ------------------------------------------------------

    raw_location = str(
        item.get("location") or ""
    ).strip().lower()


    # ------------------------------------------------------
    # EXACT / DIRECT LOCATION MATCH
    # ------------------------------------------------------

    if requested in raw_location:

        return (
            True,
            "Direct location match"
        )


    # ------------------------------------------------------
    # ALIAS MATCH
    # ------------------------------------------------------

    aliases = LOCATION_ALIASES.get(
        requested,
        []
    )

    for alias in aliases:

        if alias in raw_location:

            return (
                True,
                "Location alias match"
            )


    # ------------------------------------------------------
    # BROADER TEXT CHECK
    # ------------------------------------------------------

    text = _text_location(item)

    if requested in text:

        return (
            True,
            "Text location match"
        )


    for alias in aliases:

        if alias in text:

            return (
                True,
                "Location alias text match"
            )


    # ------------------------------------------------------
    # COORDINATE CHECK
    # ------------------------------------------------------

    geo = LOCATION_GEO.get(
        requested
    )

    latitude = _number(
        _value(
            item,
            "latitude",
            "lat"
        )
    )

    longitude = _number(
        _value(
            item,
            "longitude",
            "lon",
            "lng"
        )
    )


    if (

        geo

        and

        latitude is not None

        and

        longitude is not None

    ):

        center_lat = geo[0]
        center_lon = geo[1]
        radius = geo[2]

        distance = _distance_km(

            center_lat,
            center_lon,

            latitude,
            longitude
        )

        if distance <= radius:

            return (
                True,
                (
                    "Coordinate match "
                    f"({distance:.1f} km)"
                )
            )

        return (
            False,
            (
                "Coordinate mismatch "
                f"({distance:.1f} km)"
            )
        )


    # ------------------------------------------------------
    # UNKNOWN / OTHER
    # ------------------------------------------------------

    if not raw_location:

        return (
            False,
            "No location evidence"
        )


    if raw_location in {
        "other",
        "other other"
    }:

        return (
            False,
            "Unverified 'Other' location"
        )


    return (
        False,
        "No reliable location match"
    )


# ==========================================================
# MAIN GUMTREE SEARCH
# ==========================================================

def search_gumtree(
    location,
    max_items=4
):

    """
    Search South African Gumtree property listings
    using SolidCode's Gumtree Scraper.

    SolidCode replaces the previous crawlerbros actor.

    The function keeps the same return structure expected
    by the Nest Realtor lead engine.
    """

    print(
        "🚀 Starting SolidCode Gumtree"
    )

    print(
        "📍 Requested location:",
        location
    )

    print(
        "🔢 Max items:",
        max_items
    )


    # ======================================================
    # VALIDATE APIFY TOKEN
    # ======================================================

    if not APIFY_TOKEN:

        print(
            "❌ APIFY_TOKEN is missing"
        )

        return {

            "success": False,

            "engine": "gumtree",

            "count": 0,

            "leads": [],

            "error":
                "APIFY_TOKEN is not configured"
        }


    # ======================================================
    # SOLIDCODE INPUT
    # ======================================================

    run_input = {

        "searchKeyword":
            "houses for sale",

        "region":
            "za",

        "location":
            str(location or "").strip(),

        "category":
            "property",

        "sortBy":
            "most_recent",

        "maxResults":
            int(max_items),

        "includeListingDetails":
            True,

        "includePhone":
            False
    }


    print(
        "🧾 SolidCode input:",
        run_input
    )


    try:

        # ==================================================
        # RUN SOLIDCODE ACTOR
        # ==================================================

        run = client.actor(
            ACTOR_ID
        ).call(
            run_input=run_input
        )


        # ==================================================
        # DATASET ID
        # ==================================================

        dataset_id = getattr(
            run,
            "default_dataset_id",
            None
        )


        if (

            not dataset_id

            and

            isinstance(
                run,
                dict
            )

        ):

            dataset_id = (

                run.get(
                    "defaultDatasetId"
                )

                or

                run.get(
                    "default_dataset_id"
                )
            )


        if not dataset_id:

            raise RuntimeError(
                "SolidCode Gumtree run did "
                "not return a dataset ID"
            )


        print(
            "📦 Dataset:",
            dataset_id
        )


        # ==================================================
        # READ DATASET
        # ==================================================

        dataset = client.dataset(
            dataset_id
        )

        leads = []


        # ==================================================
        # PROCESS LISTINGS
        # ==================================================

        for item in dataset.iterate_items():

            # ----------------------------------------------
            # BASIC FIELDS
            # ----------------------------------------------

            title = _value(
                item,
                "title",
                "name"
            )


            price = _value(
                item,
                "price",
                "currentPrice",
                "listingPrice"
            )


            if price is None:

                price = _number(
                    item.get(
                        "priceRaw"
                    )
                )


            currency = _value(
                item,
                "currency"
            )


            location_value = _value(
                item,
                "location"
            )


            description = _value(
                item,
                "description",
                "details"
            )


            # ----------------------------------------------
            # SELLER
            # ----------------------------------------------

            seller_name = _value(
                item,
                "sellerName",
                "seller_name",
                "seller"
            )


            seller_type = _value(
                item,
                "sellerType",
                "seller_type"
            )


            # ----------------------------------------------
            # DATE / MARKET TIME
            # ----------------------------------------------

            posted_date = _value(
                item,
                "postedAt",
                "postedDate",
                "posted_date",
                "datePosted"
            )


            days_on_market = _value(
                item,
                "daysOnSite",
                "daysOnMarket",
                "days_on_market",
                "daysListed",
                "days_listed"
            )


            # ----------------------------------------------
            # LOCATION
            # ----------------------------------------------

            latitude = _number(
                _value(
                    item,
                    "latitude",
                    "lat"
                )
            )


            longitude = _number(
                _value(
                    item,
                    "longitude",
                    "lon",
                    "lng"
                )
            )


            # ----------------------------------------------
            # CATEGORY
            # ----------------------------------------------

            category = _value(
                item,
                "category",
                "propertyType",
                "property_type"
            )


            # ----------------------------------------------
            # ATTRIBUTES
            # ----------------------------------------------

            attributes = _value(
                item,
                "attributes"
            )


            if not isinstance(
                attributes,
                dict
            ):

                attributes = {}


            # ----------------------------------------------
            # IMAGE
            # ----------------------------------------------

            images = item.get(
                "images"
            )

            image = None

            if isinstance(
                images,
                list
            ) and images:

                image = images[0]

            else:

                image = _value(
                    item,
                    "image",
                    "imageUrl",
                    "image_url"
                )


            # ----------------------------------------------
            # LOCATION CHECK
            # ----------------------------------------------

            plausible, location_reason = (
                _location_is_plausible(
                    item,
                    location
                )
            )


            # ----------------------------------------------
            # BUILD STANDARD NEST LEAD
            # ----------------------------------------------

            lead = {

                "title":
                    title,

                "price":
                    price,

                "price_raw":
                    item.get(
                        "priceRaw"
                    ),

                "previous_price":
                    None,

                "currency":
                    currency,

                "location":
                    location_value,

                "address":
                    location_value,

                "suburb":
                    location_value,

                "city":
                    None,

                "category":
                    category,

                "property_type":
                    category,

                "seller_type":
                    seller_type,

                "seller":
                    seller_name,

                "seller_name":
                    seller_name,

                "description":
                    description,

                "posted_date":
                    posted_date,

                "days_on_market":
                    days_on_market,

                "days_on_site":
                    days_on_market,

                "url":
                    _value(
                        item,
                        "url",
                        "link",
                        "listingUrl",
                        "sourceUrl"
                    ),

                "image":
                    image,

                "images":
                    images if isinstance(
                        images,
                        list
                    ) else [],

                "image_count":
                    _value(
                        item,
                        "imageCount"
                    ),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "listing_id":
                    _value(
                        item,
                        "listingId",
                        "shortId"
                    ),

                "short_id":
                    item.get(
                        "shortId"
                    ),

                "attributes":
                    attributes,

                "featured":
                    item.get(
                        "featured"
                    ),

                "urgent":
                    item.get(
                        "urgent"
                    ),

                "source":
                    "gumtree",

                # Diagnostic fields
                "location_verified":
                    plausible,

                "location_check":
                    location_reason
            }


            leads.append(
                lead
            )


            # ----------------------------------------------
            # LOG
            # ----------------------------------------------

            print(
                "🔎 SolidCode listing:",
                title
            )

            print(
                "   Location:",
                location_value
            )

            print(
                "   Price:",
                item.get(
                    "priceRaw"
                )
            )

            print(
                "   Seller:",
                seller_name
            )

            print(
                "   Seller type:",
                seller_type
            )

            print(
                "   Posted:",
                posted_date
            )

            print(
                "   Days on site:",
                days_on_market
            )

            print(
                "   Location verified:",
                plausible
            )

            print(
                "   Location check:",
                location_reason
            )


        # ==================================================
        # FINAL RESULT
        # ==================================================

        print(
            f"✅ SolidCode Gumtree returned "
            f"{len(leads)} listings"
        )


        return {

            "success":
                True,

            "engine":
                "gumtree",

            "count":
                len(leads),

            "leads":
                leads
        }


    except Exception as e:

        print(
            "❌ SolidCode Gumtree Error:",
            str(e)
        )


        return {

            "success":
                False,

            "engine":
                "gumtree",

            "count":
                0,

            "leads":
                [],

            "error":
                str(e)
        }