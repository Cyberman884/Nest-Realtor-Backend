import math
import os

from apify_client import ApifyClient


APIFY_TOKEN = os.getenv("APIFY_TOKEN")

ACTOR_ID = "JziY9YnglkuoWMDsq"


client = ApifyClient(
    APIFY_TOKEN
)


# ==========================================================
# GUMTREE URLS
# ==========================================================

GUMTREE_URLS = {

    "johannesburg":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "johannesburg/"
        "v1c9074l3100090p1",

    "pretoria":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "pretoria-tshwane/"
        "v1c9074l3100094p1",

    "cape town":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "cape-town/"
        "v1c9074l3100006p1",

    "durban":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "durban-city/"
        "v1c9074l3100149p1",

    "port elizabeth":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "port-elizabeth/"
        "v1c9074l3100306p1",

    "gqeberha":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "port-elizabeth/"
        "v1c9074l3100306p1",

    "east london":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "east-london/"
        "v1c9074l3100300p1",

    "bloemfontein":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "bloemfontein/"
        "v1c9074l3100460p1",

    "nelspruit":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "nelspruit/"
        "v1c9074l3100398p1"
}


# ==========================================================
# APPROXIMATE LOCATION GEO DATA
# ==========================================================

# These are practical sanity-check areas.
#
# They are NOT official municipal boundaries.
#
# They are used to catch obviously incorrect results,
# such as a Soshanguve search returning Cape Town.

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
# BUILD GUMTREE URL
# ==========================================================

def build_gumtree_url(location):

    location = str(
        location or ""
    ).strip().lower()


    if location in GUMTREE_URLS:

        return GUMTREE_URLS[
            location
        ]


    if location in {
        "south africa",
        "sa",
        "rsa",
        "all",
        ""
    }:

        return (
            "https://www.gumtree.co.za/"
            "s-houses-flats-for-sale/"
            "v1c9074p1"
        )


    slug = (
        location
        .replace(
            " ",
            "-"
        )
        .replace(
            "_",
            "-"
        )
    )


    return (
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        f"{slug}/v1c9074p1"
    )


# ==========================================================
# VALUE HELPER
# ==========================================================

def _value(
    item,
    *keys
):

    for key in keys:

        value = item.get(
            key
        )

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

        return float(
            value
        )


    text = str(
        value
    ).replace(
        ",",
        ""
    )


    try:

        return float(
            text
        )

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

    """
    Haversine distance in kilometres.
    """

    radius = 6371.0


    lat1 = math.radians(
        lat1
    )

    lon1 = math.radians(
        lon1
    )

    lat2 = math.radians(
        lat2
    )

    lon2 = math.radians(
        lon2
    )


    dlat = (
        lat2 - lat1
    )

    dlon = (
        lon2 - lon1
    )


    a = (

        math.sin(
            dlat / 2
        ) ** 2

        +

        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(
            dlon / 2
        ) ** 2
    )


    return (

        radius
        *
        2
        *
        math.atan2(
            math.sqrt(a),
            math.sqrt(
                1 - a
            )
        )
    )


# ==========================================================
# TEXT LOCATION
# ==========================================================

def _text_location(item):

    fields = [

        item.get(
            "location"
        ),

        item.get(
            "locationName"
        ),

        item.get(
            "location_name"
        ),

        item.get(
            "address"
        ),

        item.get(
            "formattedAddress"
        ),

        item.get(
            "suburb"
        ),

        item.get(
            "area"
        ),

        item.get(
            "city"
        ),

        item.get(
            "town"
        ),

        item.get(
            "region"
        ),

        item.get(
            "locality"
        ),

        item.get(
            "description"
        ),

        item.get(
            "title"
        )
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


    return " ".join(
        parts
    )


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


    text = _text_location(
        item
    )


    # ------------------------------------------------------
    # DIRECT TEXT MATCH
    # ------------------------------------------------------

    if requested in text:

        return (
            True,
            "Text location match"
        )


    # ------------------------------------------------------
    # LOCATION ALIASES
    # ------------------------------------------------------

    aliases = {

        "soshanguve": [
            "soshanguve",
            "soshanguve block"
        ],

        "pretoria": [
            "pretoria",
            "tshwane"
        ],

        "johannesburg": [
            "johannesburg",
            "joburg"
        ],

        "gqeberha": [
            "gqeberha",
            "port elizabeth"
        ],

        "nelspruit": [
            "nelspruit",
            "mbombela"
        ]
    }


    for alias in aliases.get(
        requested,
        []
    ):

        if alias in text:

            return (
                True,
                "Location alias match"
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

    if not text:

        return (
            False,
            "No location evidence"
        )


    if text.strip() in {
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
    Fetch a small number of Gumtree listings.

    The Actor can sometimes return geographically
    incorrect listings. We therefore preserve the
    location evidence and validation result so the
    qualification filter can reject bad records.
    """


    search_url = str(
        location or ""
    ).strip()


    if not search_url.startswith(
        "http"
    ):

        search_url = build_gumtree_url(
            search_url
        )


    print(
        "🚀 Starting Gumtree"
    )

    print(
        "📍 Requested location:",
        location
    )

    print(
        "🔗 Gumtree URL:",
        search_url
    )

    print(
        "🔢 Max items:",
        max_items
    )


    # ======================================================
    # APIFY INPUT
    # ======================================================

    run_input = {

        "startUrls": [

            {
                "url": search_url
            }

        ],

        "maxItems":
            max_items,

        "includeListingDetails":
            True,

        "cookies": [],

        "proxy": {

            "useApifyProxy":
                True
        }
    }


    try:

        # ==================================================
        # RUN ACTOR
        # ==================================================

        run = client.actor(
            ACTOR_ID
        ).call(
            run_input=run_input
        )


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

                "Gumtree Apify run did not "
                "return a dataset ID"
            )


        # ==================================================
        # READ DATASET
        # ==================================================

        dataset = client.dataset(
            dataset_id
        )


        leads = []


        for item in dataset.iterate_items():

            # ----------------------------------------------
            # LOCATION
            # ----------------------------------------------

            latitude = _value(

                item,

                "latitude",

                "lat"
            )


            longitude = _value(

                item,

                "longitude",

                "lon",

                "lng"
            )


            location_value = _value(

                item,

                "location",

                "locationName",

                "location_name",

                "address",

                "formattedAddress",

                "suburb",

                "area",

                "city",

                "town"
            )


            # ----------------------------------------------
            # SELLER
            # ----------------------------------------------

            seller_type = _value(

                item,

                "sellerType",

                "seller_type",

                "DwellingForSaleBy"
            )


            seller_name = _value(

                item,

                "sellerName",

                "seller_name",

                "seller"
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
            # BUILD LEAD
            # ----------------------------------------------

            lead = {

                "title": _value(

                    item,

                    "title",

                    "name"
                ),


                "price": _value(

                    item,

                    "price",

                    "currentPrice",

                    "listingPrice"
                ),


                "previous_price": _value(

                    item,

                    "previousPrice",

                    "previous_price",

                    "oldPrice",

                    "originalPrice"
                ),


                "currency": _value(

                    item,

                    "currency"
                ),


                "location":
                    location_value,


                "address": _value(

                    item,

                    "address",

                    "formattedAddress"
                ),


                "suburb": _value(

                    item,

                    "suburb",

                    "area"
                ),


                "city": _value(

                    item,

                    "city",

                    "town"
                ),


                "category": _value(

                    item,

                    "category",

                    "propertyType",

                    "property_type"
                ),


                "seller_type":
                    seller_type,


                "seller":
                    seller_name,


                "description": _value(

                    item,

                    "description",

                    "details"
                ),


                "posted_date": _value(

                    item,

                    "postedDate",

                    "posted_date",

                    "datePosted"
                ),


                "days_on_market": _value(

                    item,

                    "daysOnMarket",

                    "days_on_market",

                    "daysListed",

                    "days_listed"
                ),


                "url": _value(

                    item,

                    "link",

                    "url",

                    "listingUrl",

                    "sourceUrl"
                ),


                "image": _value(

                    item,

                    "image",

                    "imageUrl",

                    "image_url"
                ),


                "latitude":
                    latitude,


                "longitude":
                    longitude,


                "source":
                    "gumtree",


                # Diagnostic fields.
                "location_verified":
                    plausible,


                "location_check":
                    location_reason
            }


            leads.append(
                lead
            )


            print(

                "🧭 Gumtree location check:",

                location_reason
            )


        print(

            f"✅ Gumtree returned "
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
            "❌ Gumtree Error:",
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

import math
import os

from apify_client import ApifyClient


APIFY_TOKEN = os.getenv("APIFY_TOKEN")

ACTOR_ID = "JziY9YnglkuoWMDsq"


client = ApifyClient(
    APIFY_TOKEN
)


# ==========================================================
# GUMTREE URLS
# ==========================================================

GUMTREE_URLS = {

    "johannesburg":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "johannesburg/"
        "v1c9074l3100090p1",

    "pretoria":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "pretoria-tshwane/"
        "v1c9074l3100094p1",

    "cape town":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "cape-town/"
        "v1c9074l3100006p1",

    "durban":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "durban-city/"
        "v1c9074l3100149p1",

    "port elizabeth":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "port-elizabeth/"
        "v1c9074l3100306p1",

    "gqeberha":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "port-elizabeth/"
        "v1c9074l3100306p1",

    "east london":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "east-london/"
        "v1c9074l3100300p1",

    "bloemfontein":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "bloemfontein/"
        "v1c9074l3100460p1",

    "nelspruit":
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        "nelspruit/"
        "v1c9074l3100398p1"
}


# ==========================================================
# APPROXIMATE LOCATION GEO DATA
# ==========================================================

# These are practical sanity-check areas.
#
# They are NOT official municipal boundaries.
#
# They are used to catch obviously incorrect results,
# such as a Soshanguve search returning Cape Town.

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
# BUILD GUMTREE URL
# ==========================================================

def build_gumtree_url(location):

    location = str(
        location or ""
    ).strip().lower()


    if location in GUMTREE_URLS:

        return GUMTREE_URLS[
            location
        ]


    if location in {
        "south africa",
        "sa",
        "rsa",
        "all",
        ""
    }:

        return (
            "https://www.gumtree.co.za/"
            "s-houses-flats-for-sale/"
            "v1c9074p1"
        )


    slug = (
        location
        .replace(
            " ",
            "-"
        )
        .replace(
            "_",
            "-"
        )
    )


    return (
        "https://www.gumtree.co.za/"
        "s-houses-flats-for-sale/"
        f"{slug}/v1c9074p1"
    )


# ==========================================================
# VALUE HELPER
# ==========================================================

def _value(
    item,
    *keys
):

    for key in keys:

        value = item.get(
            key
        )

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

        return float(
            value
        )


    text = str(
        value
    ).replace(
        ",",
        ""
    )


    try:

        return float(
            text
        )

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

    """
    Haversine distance in kilometres.
    """

    radius = 6371.0


    lat1 = math.radians(
        lat1
    )

    lon1 = math.radians(
        lon1
    )

    lat2 = math.radians(
        lat2
    )

    lon2 = math.radians(
        lon2
    )


    dlat = (
        lat2 - lat1
    )

    dlon = (
        lon2 - lon1
    )


    a = (

        math.sin(
            dlat / 2
        ) ** 2

        +

        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(
            dlon / 2
        ) ** 2
    )


    return (

        radius
        *
        2
        *
        math.atan2(
            math.sqrt(a),
            math.sqrt(
                1 - a
            )
        )
    )


# ==========================================================
# TEXT LOCATION
# ==========================================================

def _text_location(item):

    fields = [

        item.get(
            "location"
        ),

        item.get(
            "locationName"
        ),

        item.get(
            "location_name"
        ),

        item.get(
            "address"
        ),

        item.get(
            "formattedAddress"
        ),

        item.get(
            "suburb"
        ),

        item.get(
            "area"
        ),

        item.get(
            "city"
        ),

        item.get(
            "town"
        ),

        item.get(
            "region"
        ),

        item.get(
            "locality"
        ),

        item.get(
            "description"
        ),

        item.get(
            "title"
        )
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


    return " ".join(
        parts
    )


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


    text = _text_location(
        item
    )


    # ------------------------------------------------------
    # DIRECT TEXT MATCH
    # ------------------------------------------------------

    if requested in text:

        return (
            True,
            "Text location match"
        )


    # ------------------------------------------------------
    # LOCATION ALIASES
    # ------------------------------------------------------

    aliases = {

        "soshanguve": [
            "soshanguve",
            "soshanguve block"
        ],

        "pretoria": [
            "pretoria",
            "tshwane"
        ],

        "johannesburg": [
            "johannesburg",
            "joburg"
        ],

        "gqeberha": [
            "gqeberha",
            "port elizabeth"
        ],

        "nelspruit": [
            "nelspruit",
            "mbombela"
        ]
    }


    for alias in aliases.get(
        requested,
        []
    ):

        if alias in text:

            return (
                True,
                "Location alias match"
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

    if not text:

        return (
            False,
            "No location evidence"
        )


    if text.strip() in {
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
    Fetch a small number of Gumtree listings.

    The Actor can sometimes return geographically
    incorrect listings. We therefore preserve the
    location evidence and validation result so the
    qualification filter can reject bad records.
    """


    search_url = str(
        location or ""
    ).strip()


    if not search_url.startswith(
        "http"
    ):

        search_url = build_gumtree_url(
            search_url
        )


    print(
        "🚀 Starting Gumtree"
    )

    print(
        "📍 Requested location:",
        location
    )

    print(
        "🔗 Gumtree URL:",
        search_url
    )

    print(
        "🔢 Max items:",
        max_items
    )


    # ======================================================
    # APIFY INPUT
    # ======================================================

    run_input = {

        "startUrls": [

            {
                "url": search_url
            }

        ],

        "maxItems":
            max_items,

        "includeListingDetails":
            True,

        "cookies": [],

        "proxy": {

            "useApifyProxy":
                True
        }
    }


    try:

        # ==================================================
        # RUN ACTOR
        # ==================================================

        run = client.actor(
            ACTOR_ID
        ).call(
            run_input=run_input
        )


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

                "Gumtree Apify run did not "
                "return a dataset ID"
            )


        # ==================================================
        # READ DATASET
        # ==================================================

        dataset = client.dataset(
            dataset_id
        )


        leads = []


        for item in dataset.iterate_items():

            # ----------------------------------------------
            # LOCATION
            # ----------------------------------------------

            latitude = _value(

                item,

                "latitude",

                "lat"
            )


            longitude = _value(

                item,

                "longitude",

                "lon",

                "lng"
            )


            location_value = _value(

                item,

                "location",

                "locationName",

                "location_name",

                "address",

                "formattedAddress",

                "suburb",

                "area",

                "city",

                "town"
            )


            # ----------------------------------------------
            # SELLER
            # ----------------------------------------------

            seller_type = _value(

                item,

                "sellerType",

                "seller_type",

                "DwellingForSaleBy"
            )


            seller_name = _value(

                item,

                "sellerName",

                "seller_name",

                "seller"
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
            # BUILD LEAD
            # ----------------------------------------------

            lead = {

                "title": _value(

                    item,

                    "title",

                    "name"
                ),


                "price": _value(

                    item,

                    "price",

                    "currentPrice",

                    "listingPrice"
                ),


                "previous_price": _value(

                    item,

                    "previousPrice",

                    "previous_price",

                    "oldPrice",

                    "originalPrice"
                ),


                "currency": _value(

                    item,

                    "currency"
                ),


                "location":
                    location_value,


                "address": _value(

                    item,

                    "address",

                    "formattedAddress"
                ),


                "suburb": _value(

                    item,

                    "suburb",

                    "area"
                ),


                "city": _value(

                    item,

                    "city",

                    "town"
                ),


                "category": _value(

                    item,

                    "category",

                    "propertyType",

                    "property_type"
                ),


                "seller_type":
                    seller_type,


                "seller":
                    seller_name,


                "description": _value(

                    item,

                    "description",

                    "details"
                ),


                "posted_date": _value(

                    item,

                    "postedDate",

                    "posted_date",

                    "datePosted"
                ),


                "days_on_market": _value(

                    item,

                    "daysOnMarket",

                    "days_on_market",

                    "daysListed",

                    "days_listed"
                ),


                "url": _value(

                    item,

                    "link",

                    "url",

                    "listingUrl",

                    "sourceUrl"
                ),


                "image": _value(

                    item,

                    "image",

                    "imageUrl",

                    "image_url"
                ),


                "latitude":
                    latitude,


                "longitude":
                    longitude,


                "source":
                    "gumtree",


                # Diagnostic fields.
                "location_verified":
                    plausible,


                "location_check":
                    location_reason
            }


            leads.append(
                lead
            )


            print(

                "🧭 Gumtree location check:",

                location_reason
            )


        print(

            f"✅ Gumtree returned "
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
            "❌ Gumtree Error:",
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