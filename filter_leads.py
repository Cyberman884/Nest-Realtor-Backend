import re
from difflib import SequenceMatcher


# ============================================================
# GENERAL HELPERS
# ============================================================

def _text(value):
    if value is None:
        return ""

    if isinstance(
        value,
        (list, tuple, set)
    ):
        return " ".join(
            str(x)
            for x in value
        )

    if isinstance(value, dict):
        return " ".join(
            str(v)
            for v in value.values()
        )

    return str(value)


def _normalise(value):
    value = _text(
        value
    ).lower().strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


def _number(value):
    if value is None:
        return None

    if isinstance(
        value,
        (int, float)
    ):
        return float(value)

    text = _text(value)

    text = text.replace(
        ",", ""
    )
    text = text.replace(
        "R", ""
    )
    text = text.replace(
        "$", ""
    )
    text = text.replace(
        " ", ""
    )

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        text
    )

    if not match:
        return None

    try:
        return float(
            match.group()
        )
    except Exception:
        return None


def _first(place, keys):
    for key in keys:
        value = place.get(key)

        if value not in (
            None,
            "",
            [],
            {}
        ):
            return value

    return None


# ============================================================
# LOCATION MATCHING
# ============================================================

def _location_text(place):
    fields = [
        place.get("location"),
        place.get("address"),
        place.get("formatted_address"),
        place.get("formattedAddress"),
        place.get("vicinity"),
        place.get("suburb"),
        place.get("area"),
        place.get("city"),
        place.get("town"),
        place.get("region"),
        place.get("locality"),
        place.get("location_name"),
        place.get("description"),
        place.get("title"),
        place.get("name"),
    ]

    return " ".join(
        _normalise(value)
        for value in fields
        if value not in (
            None,
            "",
            [],
            {}
        )
    )


def _location_matches_text(
    place,
    requested_area
):
    requested = _normalise(
        requested_area
    )

    if not requested:
        return True

    text = _location_text(
        place
    )

    if not text:
        return False

    if requested in text:
        return True

    aliases = {
        "soshanguve": [
            "soshanguve",
        ],
        "pretoria": [
            "pretoria",
            "tshwane",
        ],
        "johannesburg": [
            "johannesburg",
            "joburg",
        ],
        "cape town": [
            "cape town",
            "capetown",
        ],
        "durban": [
            "durban",
        ],
        "gqeberha": [
            "gqeberha",
            "port elizabeth",
        ],
        "port elizabeth": [
            "port elizabeth",
            "gqeberha",
        ],
        "nelspruit": [
            "nelspruit",
            "mbombela",
        ],
    }

    for alias in aliases.get(
        requested,
        []
    ):
        if alias in text:
            return True

    requested_words = requested.split()

    if len(requested_words) > 1:
        matches = sum(
            1
            for word in requested_words
            if word in text
        )

        if matches >= len(
            requested_words
        ):
            return True

    return False


def _area_matches(
    place,
    requested_area=None
):
    """Validate the requested area without discarding usable
    coordinate evidence from the Gumtree scraper.

    SolidCode/Gumtree can sometimes mark location_verified=False
    even when location_check contains a valid coordinate match.
    We trust an explicit coordinate match only when it is inside
    the same 35 km safety radius used by the scraper.
    """
    if not requested_area:
        return True

    source = _normalise_source(place)

    # First honour an explicit successful validation.
    if place.get("location_verified") is True:
        return True

    # The scraper may expose useful coordinate evidence in
    # location_check while location_verified is False.
    location_check = _normalise(
        place.get("location_check")
    )

    match = re.search(
        r"coordinate\s+match\s*\(([-+]?[0-9]*\.?[0-9]+)\s*km\)",
        location_check
    )

    if match:
        try:
            distance = float(match.group(1))
            if distance <= 35:
                return True
        except (TypeError, ValueError):
            pass

    # Direct textual evidence is also valid when the source has
    # not provided a usable coordinate check.
    return _location_matches_text(
        place,
        requested_area
    )


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
    "apartment",
    "flat",
    "penthouse",
}

NON_RESIDENTIAL_WORDS = {
    "office",
    "warehouse",
    "industrial",
    "retail",
    "shop",
    "restaurant",
    "hotel",
    "vacant land",
    "commercial property",
    "business premises",
    "parking bay",
    "garage only",
}


def _property_text(place):
    fields = [
        place.get("title"),
        place.get("name"),
        place.get("description"),
        place.get("property_type"),
        place.get("propertyType"),
        place.get("type"),
        place.get("category"),
        place.get("listing_type"),
    ]

    return " ".join(
        _normalise(value)
        for value in fields
        if value not in (
            None,
            "",
            [],
            {}
        )
    )


def _is_residential(place):
    text = _property_text(
        place
    )

    # Strong non-residential indicators.
    for word in NON_RESIDENTIAL_WORDS:
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
            ]
        )
    )

    if property_type:
        residential_types = [
            "house",
            "townhouse",
            "duplex",
            "villa",
            "cottage",
            "apartment",
            "flat",
            "residential",
            "home",
            "property",
        ]

        return any(
            x in property_type
            for x in residential_types
        )

    # If the source gives no usable property type,
    # don't reject solely because the field is absent.
    return True


# ============================================================
# SELLER SIGNAL
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
    "property management",
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
        _normalise(value)
        for value in fields
        if value not in (
            None,
            "",
            [],
            {}
        )
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
        return (
            "Owner/private seller",
            30
        )

    if agent_hits and not owner_hits:
        return (
            "Agent listing",
            -15
        )

    if owner_hits and agent_hits:
        return (
            "Mixed seller signal",
            10
        )

    return (
        "Seller not explicitly identified",
        0
    )


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
        ]
    )

    current_price = _first(
        place,
        [
            "price",
            "current_price",
            "currentPrice",
            "listing_price",
            "listingPrice",
        ]
    )

    old_number = _number(
        old_price
    )

    current_number = _number(
        current_price
    )

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

    reduction = (
        old_number
        - current_number
    )

    percentage = (
        reduction
        / old_number
    ) * 100

    if percentage >= 10:
        score = 25
    elif percentage >= 5:
        score = 15
    else:
        score = 8

    return {
        "detected": True,
        "percentage": round(
            percentage,
            1
        ),
        "reason": (
            f"Price reduced by "
            f"{percentage:.1f}%"
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
        ]
    )

    days = _number(
        value
    )

    if days is None:
        return {
            "detected": False,
            "days": None,
            "reason": None,
            "score": 0,
        }

    days = int(
        days
    )

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
            f"Listed for approximately "
            f"{days} days"
        )

    return {
        "detected": score > 0,
        "days": days,
        "reason": reason,
        "score": score,
    }


# ============================================================
# SOURCE
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
# REASONING
# ============================================================

def _build_reasoning(
    place,
    seller_reason,
    price_data,
    market_data
):
    reasons = []

    if (
        seller_reason
        and seller_reason
        != "Seller not explicitly identified"
    ):
        if seller_reason == "Owner/private seller":
            detail = (
                "The listing contains an "
                "owner/private seller signal."
            )
        elif seller_reason == "Agent listing":
            detail = (
                "The listing appears to "
                "be advertised by an agent "
                "or agency."
            )
        else:
            detail = seller_reason

        reasons.append({
            "signal": seller_reason,
            "detail": detail,
            "evidence": {
                "seller_signal":
                    seller_reason
            },
        })

    if price_data["detected"]:
        reasons.append({
            "signal": "Price reduction",
            "detail":
                price_data["reason"],
            "evidence":
                price_data,
        })

    if market_data["detected"]:
        reasons.append({
            "signal":
                "Long time on market",
            "detail":
                market_data["reason"],
            "evidence": {
                "days_on_market":
                    market_data["days"],
                "threshold_days":
                    180,
            },
        })

    source = place.get(
        "source"
    )

    if source:
        source_name = (
            str(source)
            .replace(
                "_",
                " "
            )
            .title()
        )

        reasons.append({
            "signal": "Source",
            "detail": (
                f"Found via "
                f"{source_name}."
            ),
            "evidence": {
                "source": source
            },
        })

    location_check = place.get(
        "location_check"
    )

    if location_check:
        reasons.append({
            "signal":
                "Location validation",
            "detail":
                str(location_check),
            "evidence": {
                "location_verified":
                    place.get(
                        "location_verified"
                    )
            },
        })

    if not reasons:
        reasons.append({
            "signal":
                "Public listing signal",
            "detail": (
                "Potential seller opportunity "
                "identified from the available "
                "public listing information."
            ),
            "evidence": {},
        })

    return reasons


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

    print(
        "🔎 FILTER INPUT:",
        len(raw_places)
    )

    for place in raw_places:

        if not isinstance(
            place,
            dict
        ):
            continue

        source = _normalise_source(
            place
        )

        name = _first(
            place,
            [
                "title",
                "name"
            ]
        )

        if not name:
            print(
                "⏭️ Rejected: no name/title"
            )
            continue

        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        if not _area_matches(
            place,
            requested_area
        ):
            print(
                "⏭️ Rejected location:",
                source,
                name,
                place.get(
                    "location_check",
                    place.get(
                        "location"
                    )
                )
            )
            continue

        # ----------------------------------------------------
        # PROPERTY TYPE
        # ----------------------------------------------------

        if not _is_residential(
            place
        ):
            print(
                "⏭️ Rejected non-residential:",
                name
            )
            continue

        # ----------------------------------------------------
        # DEDUPLICATION
        # ----------------------------------------------------

        address = _first(
            place,
            [
                "address",
                "formatted_address",
                "formattedAddress",
                "location",
                "suburb",
                "city",
            ]
        )

        url = _first(
            place,
            [
                "url",
                "link",
                "listingUrl"
            ]
        )

        unique_key = (
            f"{source}|"
            f"{_normalise(name)}|"
            f"{_normalise(address)}|"
            f"{_normalise(url)}"
        )

        if unique_key in seen:
            print(
                "⏭️ Rejected duplicate:",
                name
            )
            continue

        seen.add(
            unique_key
        )

        # ----------------------------------------------------
        # SIGNALS
        # ----------------------------------------------------

        seller_reason, seller_score = (
            _seller_signal(
                place
            )
        )

        price_data = _price_reduction(
            place
        )

        market_data = _days_on_market(
            place
        )

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------
        # Relevance points describe whether this is a useful
        # property for the requested search. Opportunity points
        # describe evidence that the seller may be motivated.

        location_score = 20
        location_detail = (
            place.get("location_check")
            or "Requested location matched"
        )

        property_score = 15
        property_detail = "Residential property"

        # Freshness is useful context, but is not a seller-intent
        # signal on its own.
        days_value = market_data.get("days")
        if days_value is not None and days_value <= 30:
            fresh_score = 10
            fresh_detected = True
            fresh_detail = f"Listed approximately {days_value} days ago"
        else:
            fresh_score = 0
            fresh_detected = False
            fresh_detail = None

        # Keep the intended opportunity weights.
        long_score = min(20, market_data["score"])
        reduction_score = min(15, price_data["score"])

        # FSBO/private owner is a strong seller-intent signal.
        # Agent/business listings remain valid opportunities but do
        # not receive the owner bonus.
        seller_text = _normalise(
            " ".join(
                str(place.get(key) or "")
                for key in [
                    "seller_type",
                    "seller",
                    "seller_name",
                    "description",
                    "title",
                ]
            )
        )

        fsbo_terms = [
            "fsbo",
            "for sale by owner",
            "private seller",
            "private owner",
            "owner listed",
            "selling privately",
            "by owner",
        ]

        fsbo_detected = any(
            term in seller_text
            for term in fsbo_terms
        )

        if fsbo_detected:
            seller_score_final = 40
            seller_signal_final = "Owner/private seller"
        else:
            seller_score_final = 0
            seller_signal_final = seller_reason

        # Count independent sources for the same listing.
        # At the moment the engine normally supplies one source, so
        # this remains 0 unless duplicate evidence is actually present.
        listing_key = _normalise(
            url or name
        )
        source_count = len({
            _normalise_source(item)
            for item in raw_places
            if _normalise(item.get("url") or item.get("link") or item.get("listingUrl") or item.get("title") or item.get("name")) == listing_key
        })
        multi_source_score = 25 if source_count > 1 else 0

        raw_score = (
            location_score
            + property_score
            + fresh_score
            + long_score
            + reduction_score
            + seller_score_final
            + multi_source_score
        )

        score = max(
            0,
            min(100, int(raw_score))
        )

        if score >= 90:
            priority = "Priority"
        elif score >= 70:
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
            market_data
        )

        signal_count = sum(
            1
            for signal in [
                fsbo_detected,
                price_data[
                    "detected"
                ],
                market_data[
                    "detected"
                ],
                source_count > 1,
            ]
            if signal
        )

        # ----------------------------------------------------
        # OUTPUT
        # ----------------------------------------------------

        lead = dict(place)

        lead.update({
            "name": name,
            "title": _first(
                place,
                [
                    "title",
                    "name"
                ]
            ),
            "address": address,
            "source": source,
            "priority": priority,
            "opportunity_priority":
                priority,
            "opportunity_type":
                "Seller Opportunity Signal",

            "seller_signal":
                seller_signal_final,

            "price_reduction_detected":
                price_data[
                    "detected"
                ],

            "price_reduction_percentage":
                price_data[
                    "percentage"
                ],

            "long_time_on_market":
                market_data[
                    "detected"
                ],

            "days_on_market":
                market_data[
                    "days"
                ],

            "days_listed":
                market_data[
                    "days"
                ],

            "signals": {
                "location": {
                    "detected": True,
                    "score": location_score,
                    "detail": location_detail,
                },
                "property_type": {
                    "detected": True,
                    "score": property_score,
                    "detail": property_detail,
                },
                "seller": {
                    "detected": fsbo_detected,
                    "type": seller_signal_final,
                    "score": seller_score_final,
                },
                "fresh_listing": {
                    "detected": fresh_detected,
                    "score": fresh_score,
                    "detail": fresh_detail,
                },
                "price_reduction": {
                    "detected":
                        price_data[
                            "detected"
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
                    "detected": source_count > 1,
                    "source_count": source_count,
                    "score": multi_source_score,
                },

            },

            "reasoning":
                reasoning,

            "signal_count":
                signal_count,

            "score_breakdown": {
                "location": location_score,
                "property_type": property_score,
                "fresh_listing": fresh_score,
                "long_listing": long_score,
                "price_reduction": reduction_score,
                "fsbo_owner": seller_score_final,
                "multi_source": multi_source_score,
                "raw_score": raw_score,
                "final_score": score,
            },

            "opportunity_score":
                score,
        })

        filtered.append(
            lead
        )

        print(
            "✅ Accepted:",
            source,
            name,
            "score=",
            score
        )

    priority_order = {
        "Priority": 4,
        "High": 3,
        "Medium": 2,
        "Low": 1,
    }

    filtered.sort(
        key=lambda item: (
            priority_order.get(
                item.get(
                    "opportunity_priority",
                    "Low"
                ),
                1
            ),
            item.get(
                "opportunity_score",
                0
            )
        ),
        reverse=True
    )

    print(
        "🎯 FILTER OUTPUT:",
        len(filtered)
    )

    return filtered
