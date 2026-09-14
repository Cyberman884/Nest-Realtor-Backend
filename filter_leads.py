# filter_leads.py

import re
from difflib import SequenceMatcher


# ============================================================
# HELPERS
# ============================================================

def _text(value):
    if value is None:
        return ""

    if isinstance(value, (list, tuple, set)):
        return " ".join(str(x) for x in value)

    if isinstance(value, dict):
        return " ".join(str(v) for v in value.values())

    return str(value)


def _normalise(value):
    value = _text(value).lower().strip()
    value = re.sub(r"\s+", " ", value)
    return value


def _number(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = _text(value)
    text = text.replace(",", "")
    text = text.replace("R", "")
    text = text.replace("$", "")
    text = text.replace(" ", "")

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except Exception:
        return None


def _first(place, keys):
    for key in keys:
        value = place.get(key)

        if value not in (None, "", [], {}):
            return value

    return None


# ============================================================
# AREA FILTERING
# ============================================================

def _area_matches(place, requested_area=None):

    if not requested_area:
        return True

    requested = _normalise(requested_area)

    if not requested:
        return True

    area_fields = [
        place.get("location"),
        place.get("address"),
        place.get("formatted_address"),
        place.get("vicinity"),
        place.get("suburb"),
        place.get("area"),
        place.get("city"),
        place.get("town"),
        place.get("region"),
        place.get("locality"),
        place.get("location_name"),
        place.get("address_locality"),
    ]

    combined = " ".join(
        _normalise(x)
        for x in area_fields
        if x not in (None, "", [], {})
    )

    if not combined:
        return False

    if requested in combined:
        return True

    requested_words = requested.split()

    if len(requested_words) == 1:
        return requested in combined

    matches = sum(
        1 for word in requested_words
        if word in combined
    )

    return matches >= max(1, len(requested_words) - 1)


# ============================================================
# PROPERTY TYPE
# ============================================================

HOUSE_WORDS = {
    "house",
    "home",
    "free standing",
    "freestanding",
    "residential house",
    "family home",
    "townhouse",
    "town house",
    "duplex",
    "villa",
    "cottage",
    "farm house",
    "farmhouse",
}

NON_HOUSE_WORDS = {
    "office",
    "commercial",
    "warehouse",
    "industrial",
    "retail",
    "shop",
    "business",
    "restaurant",
    "hotel",
    "vacant land",
    "land",
    "plot",
    "stand",
    "parking",
    "garage only",
    "apartment block",
}


def _property_text(place):

    fields = [
        place.get("title"),
        place.get("name"),
        place.get("description"),
        place.get("property_type"),
        place.get("type"),
        place.get("category"),
        place.get("propertyType"),
        place.get("listing_type"),
    ]

    return " ".join(
        _normalise(x)
        for x in fields
        if x not in (None, "", [], {})
    )


def _is_residential(place):

    text = _property_text(place)

    for word in NON_HOUSE_WORDS:
        if word in text:
            return False

    for word in HOUSE_WORDS:
        if word in text:
            return True

    property_type = _normalise(
        _first(
            place,
            [
                "property_type",
                "propertyType",
                "type",
                "category",
            ],
        )
    )

    if property_type:

        residential_types = [
            "house",
            "townhouse",
            "duplex",
            "villa",
            "cottage",
            "residential",
            "home",
        ]

        return any(
            x in property_type
            for x in residential_types
        )

    return True


# ============================================================
# SELLER / OWNER SIGNALS
# ============================================================

OWNER_WORDS = {
    "owner",
    "private seller",
    "private",
    "direct owner",
    "owner listed",
    "owner listing",
    "selling privately",
    "no agent",
    "by owner",
    "for sale by owner",
    "fsbo",
}

AGENT_WORDS = {
    "estate agent",
    "real estate agent",
    "property agent",
    "realtor",
    "agency",
    "estate agency",
    "property group",
    "property specialist",
}


def _seller_signal(place):

    fields = [
        place.get("seller"),
        place.get("seller_name"),
        place.get("seller_type"),
        place.get("contact_type"),
        place.get("description"),
        place.get("title"),
        place.get("agent"),
        place.get("agency"),
        place.get("listed_by"),
        place.get("listing_agent"),
    ]

    text = " ".join(
        _normalise(x)
        for x in fields
        if x not in (None, "", [], {})
    )

    owner_hits = [
        word
        for word in OWNER_WORDS
        if word in text
    ]

    agent_hits = [
        word
        for word in AGENT_WORDS
        if word in text
    ]

    if owner_hits and not agent_hits:
        return "Owner/private seller", 30

    if agent_hits and not owner_hits:
        return "Agent listing", -15

    if owner_hits and agent_hits:
        return "Mixed seller signal", 10

    return "Seller not explicitly identified", 0


# ============================================================
# PRICE REDUCTION
# ============================================================

def _price_reduction(place):

    old_price = _first(
        place,
        [
            "previous_price",
            "old_price",
            "original_price",
            "previousPrice",
            "oldPrice",
            "originalPrice",
            "price_before",
            "priceBefore",
        ],
    )

    current_price = _first(
        place,
        [
            "price",
            "current_price",
            "currentPrice",
            "listing_price",
            "listingPrice",
        ],
    )

    old_number = _number(old_price)
    current_number = _number(current_price)

    if (
        old_number is None
        or current_number is None
        or old_number <= 0
        or current_number <= 0
        or current_number >= old_number
    ):
        return {
            "detected": False,
            "percentage": None,
            "reason": None,
            "score": 0,
        }

    reduction = old_number - current_number

    percentage = (
        reduction / old_number
    ) * 100

    if percentage >= 10:
        score = 25
    elif percentage >= 5:
        score = 15
    else:
        score = 8

    return {
        "detected": True,
        "percentage": round(percentage, 1),
        "reason": (
            f"Price reduced by {percentage:.1f}%"
        ),
        "score": score,
    }


# ============================================================
# TIME ON MARKET
# ============================================================

def _days_on_market(place):

    value = _first(
        place,
        [
            "days_on_market",
            "daysOnMarket",
            "days_listed",
            "daysListed",
            "listing_days",
            "listingDays",
            "days",
        ],
    )

    days = _number(value)

    if days is None:
        return {
            "detected": False,
            "days": None,
            "reason": None,
            "score": 0,
        }

    days = int(days)

    if days >= 180:
        score = 25
    elif days >= 90:
        score = 15
    elif days >= 60:
        score = 8
    else:
        score = 0

    reason = None

    if score > 0:
        reason = (
            f"Listed for approximately {days} days"
        )

    return {
        "detected": score > 0,
        "days": days,
        "reason": reason,
        "score": score,
    }


# ============================================================
# MULTI-SOURCE SIGNAL
# ============================================================

def _source_count(place):

    values = []

    for key in [
        "sources",
        "source",
        "source_count",
        "sourceCount",
        "listing_sources",
        "listingSources",
    ]:

        value = place.get(key)

        if value not in (None, "", [], {}):
            values.append(value)

    if not values:
        return 1

    source_value = values[0]

    if isinstance(
        source_value,
        (list, tuple, set)
    ):
        return max(
            1,
            len(source_value)
        )

    number = _number(source_value)

    if number is not None:
        return max(
            1,
            int(number)
        )

    return 1


# ============================================================
# REASONING
# ============================================================

def _build_reasoning(
    place,
    seller_reason,
    price_data,
    market_data,
):

    reasons = []

    # Seller signal
    if (
        seller_reason
        and seller_reason !=
        "Seller not explicitly identified"
    ):

        reasons.append({
            "signal": seller_reason,
            "detail": (
                "Listing contains an "
                "owner/private or seller-type signal."
                if "Owner" in seller_reason
                or "private" in seller_reason.lower()
                else seller_reason
            ),
            "evidence": {
                "seller_signal": seller_reason
            },
        })

    # Price reduction
    if price_data["detected"]:

        reasons.append({
            "signal": "Price reduction",
            "detail": price_data["reason"],
            "evidence": price_data,
        })

    # Time on market
    if market_data["detected"]:

        reasons.append({
            "signal": "Long time on market",
            "detail": market_data["reason"],
            "evidence": {
                "days_on_market":
                    market_data["days"],
                "threshold_days": 180,
            },
        })

    # Source
    source = place.get("source")

    if source:

        source_name = (
            str(source)
            .replace("_", " ")
            .title()
        )

        reasons.append({
            "signal": "Source",
            "detail": (
                f"Found via {source_name}."
            ),
            "evidence": {
                "source": source
            },
        })

    # Multi-source
    source_count = _source_count(place)

    if source_count > 1:

        reasons.append({
            "signal": "Multi-source evidence",
            "detail": (
                f"Information found across "
                f"{source_count} sources."
            ),
            "evidence": {
                "source_count": source_count
            },
        })

    # Fallback
    if not reasons:

        reasons.append({
            "signal": "Public listing signal",
            "detail": (
                "Potential seller opportunity "
                "identified from available "
                "public listing information."
            ),
            "evidence": {},
        })

    return reasons


# ============================================================
# SOURCE NORMALISATION
# ============================================================

def _normalise_source(place):

    source = _normalise(
        place.get(
            "source",
            "unknown"
        )
    )

    if source in {
        "facebook",
        "facebook marketplace",
        "facebook_marketplace",
    }:
        return "facebook_marketplace"

    if source in {
        "gumtree",
        "gumtree south africa",
    }:
        return "gumtree"

    if source in {
        "google",
        "google places",
        "google_places",
        "google places api",
    }:
        return "google_places"

    return source or "unknown"


# ============================================================
# MAIN FILTER
# ============================================================

def filter_leads(
    raw_places,
    requested_area=None
):

    if not raw_places:
        return []

    filtered = []
    seen = set()

    for place in raw_places:

        if not isinstance(place, dict):
            continue

        source = _normalise_source(place)

        # ----------------------------------------------------
        # FIELD NORMALISATION
        # ----------------------------------------------------

        if source == "google_places":

            name = _first(
                place,
                [
                    "name",
                    "title",
                ],
            )

            address = _first(
                place,
                [
                    "address",
                    "formatted_address",
                    "vicinity",
                    "location",
                ],
            )

            website = _first(
                place,
                [
                    "website",
                    "url",
                ],
            )

            place_id = place.get(
                "place_id"
            )

            rating = place.get(
                "rating"
            )

            reviews = _first(
                place,
                [
                    "user_ratings_total",
                    "reviews",
                ],
            )

        elif source == "gumtree":

            name = _first(
                place,
                [
                    "title",
                    "name",
                ],
            )

            address = _first(
                place,
                [
                    "location",
                    "address",
                    "suburb",
                    "city",
                ],
            )

            website = _first(
                place,
                [
                    "url",
                    "website",
                ],
            )

            place_id = None
            rating = None
            reviews = None

        elif source == "facebook_marketplace":

            name = _first(
                place,
                [
                    "title",
                    "name",
                ],
            )

            address = _first(
                place,
                [
                    "location",
                    "address",
                    "suburb",
                    "city",
                ],
            )

            website = _first(
                place,
                [
                    "url",
                    "website",
                ],
            )

            place_id = None
            rating = None
            reviews = None

        else:

            name = _first(
                place,
                [
                    "name",
                    "title",
                ],
            )

            address = _first(
                place,
                [
                    "address",
                    "formatted_address",
                    "location",
                    "suburb",
                    "city",
                ],
            )

            website = _first(
                place,
                [
                    "website",
                    "url",
                ],
            )

            place_id = place.get(
                "place_id"
            )

            rating = place.get(
                "rating"
            )

            reviews = _first(
                place,
                [
                    "user_ratings_total",
                    "reviews",
                ],
            )

        # ----------------------------------------------------
        # NAME REQUIRED
        # ----------------------------------------------------

        if not name:
            continue

        # ----------------------------------------------------
        # AREA FILTER
        # ----------------------------------------------------

        if not _area_matches(
            place,
            requested_area
        ):
            continue

        # ----------------------------------------------------
        # RESIDENTIAL FILTER
        # ----------------------------------------------------

        if not _is_residential(place):
            continue

        # ----------------------------------------------------
        # DEDUPLICATION
        # ----------------------------------------------------

        unique_key = (
            f"{source}-"
            f"{_normalise(name)}-"
            f"{_normalise(address)}"
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)

        # ----------------------------------------------------
        # SELLER SIGNAL
        # ----------------------------------------------------

        seller_reason, seller_score = (
            _seller_signal(place)
        )

        # ----------------------------------------------------
        # PRICE SIGNAL
        # ----------------------------------------------------

        price_data = _price_reduction(
            place
        )

        # ----------------------------------------------------
        # MARKET TIME SIGNAL
        # ----------------------------------------------------

        market_data = _days_on_market(
            place
        )

        # ----------------------------------------------------
        # OPPORTUNITY SCORE
        # ----------------------------------------------------

        score = 0

        # Strong seller signal
        score += seller_score

        # Price reduction
        score += price_data["score"]

        # Time on market
        score += market_data["score"]

        # Multi-source evidence
        source_count = _source_count(
            place
        )

        if source_count >= 3:
            score += 15

        elif source_count >= 2:
            score += 8

        # ----------------------------------------------------
        # SCORE LIMIT
        # ----------------------------------------------------

        score = max(
            0,
            min(
                100,
                int(score)
            )
        )

        # ----------------------------------------------------
        # PRIORITY
        # ----------------------------------------------------

        if score >= 80:
            priority = "Priority"

        elif score >= 65:
            priority = "High"

        elif score >= 40:
            priority = "Medium"

        else:
            priority = "Low"

        # ----------------------------------------------------
        # REASONING
        # ----------------------------------------------------

        reasoning = _build_reasoning(
            place,
            seller_reason,
            price_data,
            market_data,
        )

        # ----------------------------------------------------
        # OUTPUT
        # ----------------------------------------------------

        filtered.append({

            "name": name,

            "address": address,

            "place_id": place_id,

            "website": website,

            "rating": rating,

            "reviews": reviews,

            "source": source,

            "priority": priority,

            "opportunity_priority": priority,

            "opportunity_type":
                "Seller Opportunity Signal",

            # Seller signal
            "seller_signal":
                seller_reason,

            # Price signal
            "price_reduction_detected":
                price_data["detected"],

            "price_reduction_percentage":
                price_data["percentage"],

            # Market-time signal
            "long_time_on_market":
                market_data["detected"],

            "days_on_market":
                market_data["days"],

            "days_listed":
                market_data["days"],

            # Structured signals
            "signals": {

                "seller": {
                    "detected":
                        seller_score > 0,
                    "type":
                        seller_reason,
                    "score":
                        max(
                            0,
                            seller_score
                        ),
                },

                "price_reduction": {
                    "detected":
                        price_data[
                            "detected"
                        ],
                    "reduction_percent":
                        price_data[
                            "percentage"
                        ],
                    "percentage":
                        price_data[
                            "percentage"
                        ],
                    "score":
                        price_data[
                            "score"
                        ],
                },

                "long_listing": {
                    "detected":
                        market_data[
                            "detected"
                        ],
                    "days_on_market":
                        market_data[
                            "days"
                        ],
                    "score":
                        market_data[
                            "score"
                        ],
                },

                "multi_source": {
                    "detected":
                        source_count > 1,
                    "source_count":
                        source_count,
                },
            },

            # Reasoning
            "reasoning":
                reasoning,

            "signal_count":
                sum(
                    1
                    for signal in [
                        seller_score > 0,
                        price_data[
                            "detected"
                        ],
                        market_data[
                            "detected"
                        ],
                        source_count > 1,
                    ]
                    if signal
                ),

            # Final score
            "opportunity_score":
                score,
        })

    # ========================================================
    # SORT
    # ========================================================

    priority_order = {
        "Priority": 4,
        "High": 3,
        "Medium": 2,
        "Low": 1,
    }

    filtered.sort(
        key=lambda x: (
            priority_order.get(
                x.get(
                    "opportunity_priority",
                    "Low"
                ),
                1,
            ),
            x.get(
                "opportunity_score",
                0
            ),
        ),
        reverse=True,
    )

    return filtered