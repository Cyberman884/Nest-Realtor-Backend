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
    "flat",
    "apartment",
    "residential property",
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
    "commercial property",
    "industrial property",
    "vacant erf",
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
    """Only accept records with positive residential-property evidence."""
    text = _property_text(place)
    property_type = _normalise(_first(
        place,
        ["property_type", "propertyType", "type", "category", "listing_type"],
    ))

    # Reject clearly non-residential categories first.
    for word in NON_HOUSE_WORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", text):
            return False

    residential_terms = HOUSE_WORDS | {
        "flat", "apartment", "residential property", "sectional title",
    }
    if any(re.search(r"\b" + re.escape(word) + r"\b", text)
           for word in residential_terms):
        return True

    # Some feeds provide a clean property-type field even when title is generic.
    if property_type and any(term in property_type for term in (
        "residential", "house", "townhouse", "duplex", "flat",
        "apartment", "villa", "cottage", "farm"
    )):
        return True

    # Do not default unknown records to residential: this was admitting
    # unrelated Gumtree/Marketplace adverts as property opportunities.
    return False


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
        place.get("_all_title"),
        place.get("_all_description"),
        place.get("_all_seller"),
        place.get("_all_seller_type"),
        place.get("_all_listed_by"),
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
        return "Owner/private seller", 35

    if agent_hits and not owner_hits:
        return "Agent listing", -10

    if owner_hits and agent_hits:
        return "Mixed seller signal", 15

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
        score = 30
    elif percentage >= 5:
        score = 20
    else:
        score = 10

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
        score = 30
    elif days >= 120:
        score = 22
    elif days >= 90:
        score = 18
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

def _clean_match_text(value):
    value = re.sub(r"[^a-z0-9 ]", " ", _normalise(value))
    return re.sub(r"\s+", " ", value).strip()


def _find_property_group(groups, name, address):
    """Match only when both location and listing identity are sufficiently close."""
    clean_address = _clean_match_text(address)
    clean_name = _clean_match_text(name)
    for key, group in groups.items():
        existing = group["place"]
        other_address = _clean_match_text(existing.get("address"))
        other_name = _clean_match_text(existing.get("name") or existing.get("title"))
        if clean_address and other_address:
            address_match = clean_address == other_address or (
                SequenceMatcher(None, clean_address, other_address).ratio() >= 0.92
            )
            name_match = clean_name == other_name or (
                SequenceMatcher(None, clean_name, other_name).ratio() >= 0.78
            )
            if address_match and name_match:
                return key
        elif not clean_address and not other_address and clean_name and other_name:
            if clean_name == other_name or SequenceMatcher(None, clean_name, other_name).ratio() >= 0.90:
                return key
    return None


def _extract_source_list(place):
    values = []
    for key in ("sources", "source", "source_name", "platform"):
        value = place.get(key)
        if isinstance(value, (list, tuple, set)):
            values.extend(str(x) for x in value if x)
        elif value not in (None, "", [], {}):
            values.append(str(value))
    return sorted(set(_normalise(x) for x in values if _normalise(x)))


def filter_leads(raw_places, requested_area=None):
    """
    Normalise and qualify seller opportunities from all supported feeds.

    Compatibility: keeps the existing function signature and output fields.
    Existing scoring weights/thresholds are retained; this update improves
    qualification and combines the same property across different sources.
    """
    if not raw_places:
        return []

    grouped = {}
    for original in raw_places:
        if not isinstance(original, dict):
            continue
        place = dict(original)
        source = _normalise_source(place)

        if source == "google_places":
            name = _first(place, ["name", "title"])
            address = _first(place, ["address", "formatted_address", "vicinity", "location"])
            website = _first(place, ["website", "url"])
            place_id = place.get("place_id")
            rating = place.get("rating")
            reviews = _first(place, ["user_ratings_total", "reviews"])
        elif source in {"gumtree", "facebook_marketplace"}:
            name = _first(place, ["title", "name"])
            address = _first(place, ["location", "address", "suburb", "city", "town"])
            website = _first(place, ["url", "website", "link"])
            place_id = None
            rating = None
            reviews = None
        else:
            name = _first(place, ["name", "title", "headline"])
            address = _first(place, ["address", "formatted_address", "location", "suburb", "city", "town", "area"])
            website = _first(place, ["url", "link", "website", "listing_url"])
            place_id = place.get("place_id")
            rating = place.get("rating")
            reviews = _first(place, ["user_ratings_total", "reviews"])

        if not name:
            continue

        place["source"] = source
        place["name"] = name
        place["title"] = _first(place, ["title", "name", "headline"]) or name
        place["address"] = address
        place["location"] = address
        place["website"] = website

        if not _area_matches(place, requested_area):
            continue
        if not _is_residential(place):
            continue

        key = _find_property_group(grouped, name, address)
        if key is None:
            key = f"property_{len(grouped)}"
            grouped[key] = {
                "place": place,
                "sources": set(),
                "source_records": [],
            }
        group = grouped[key]
        group["sources"].add(source)
        group["sources"].update(_extract_source_list(place))
        group["source_records"].append(place)
        # Preserve signal text from every source so an owner/relisting clue
        # on a secondary source is not lost during grouping.
        for text_field in ("title", "description", "seller", "seller_type", "listed_by", "history"):
            value = place.get(text_field)
            if value not in (None, "", [], {}):
                existing_values = group["place"].get(f"_all_{text_field}", [])
                if not isinstance(existing_values, list):
                    existing_values = [existing_values]
                existing_values.append(value)
                group["place"][f"_all_{text_field}"] = existing_values

        # Merge useful evidence from later source records without overwriting
        # already populated fields with empty values.
        base = group["place"]
        for field, value in place.items():
            if base.get(field) in (None, "", [], {}) and value not in (None, "", [], {}):
                base[field] = value

    filtered = []
    for group in grouped.values():
        place = group["place"]
        source_names = sorted(group["sources"])
        source_count = max(1, len(source_names))
        place["sources"] = source_names
        place["source_count"] = source_count

        seller_reason, seller_score = _seller_signal(place)
        price_data = _price_reduction(place)
        market_data = _days_on_market(place)

        # Additional explicit seller-opportunity signals from feeds that
        # expose relisting / repeated-ad / valuation intent fields.
        signal_text = " ".join(_normalise(place.get(k)) for k in (
            "title", "description", "status", "listing_status", "history", "seller_type",
            "_all_title", "_all_description", "_all_history"
        ))
        relisted = bool(place.get("relisted") or place.get("is_relisted") or
                        place.get("relist_count") or place.get("relisting_count") or
                        "relisted" in signal_text or "re-listed" in signal_text)
        price_history = bool(place.get("price_history") or place.get("price_changes") or
                             place.get("price_drop") or place.get("price_dropped"))

        score = seller_score + price_data["score"] + market_data["score"]
        if source_count >= 3:
            score += 20
        elif source_count >= 2:
            score += 12
        if relisted and not market_data["detected"]:
            score += 12
        if price_history and not price_data["detected"]:
            score += 8

        # Do not make seller-intent evidence a hard requirement.
        # A valid residential listing in the requested area can still be
        # surfaced as a POTENTIAL opportunity while stronger signals rank higher.
        has_signal = bool(
            seller_score > 0 or price_data["detected"] or market_data["detected"]
            or source_count > 1 or relisted or price_history
        )
        if not has_signal:
            score = max(score, 15)  # baseline score for an unverified public listing
        score = max(0, min(100, int(score)))

        if score >= 80:
            priority = "Priority"
        elif score >= 65:
            priority = "High"
        elif score >= 40:
            priority = "Medium"
        else:
            priority = "Low"

        # Prefer the strongest/most complete listing URL and retain all sources.
        url = _first(place, ["url", "link", "website", "listing_url"])
        reasoning = _build_reasoning(place, seller_reason, price_data, market_data)
        if not has_signal:
            reasoning.append({
                "signal": "Public residential listing",
                "detail": "Valid residential listing in the requested area. Seller intent has not yet been independently verified.",
                "evidence": {"seller_intent_verified": False},
            })
        if source_count > 1:
            reasoning.append({
                "signal": "Multi-source evidence",
                "detail": f"Matching property information found across {source_count} sources.",
                "evidence": {"sources": source_names, "source_count": source_count},
            })
        if relisted:
            reasoning.append({"signal": "Relisting evidence", "detail": "The listing data contains a relisting signal.", "evidence": {"relisted": True}})
        if price_history:
            reasoning.append({"signal": "Price history evidence", "detail": "The listing data contains price-history evidence.", "evidence": {"price_history": True}})

        output = {
            "name": place.get("name"),
            "address": place.get("address"),
            "location": place.get("address"),
            "location_verified": bool(place.get("address")),
            "url": url,
            "phone": _first(place, ["phone", "formatted_phone_number", "contact_phone"]),
            "price": _first(place, ["price", "current_price", "currentPrice", "listing_price", "listingPrice"]),
            "seller_type": _first(place, ["seller_type", "sellerType", "contact_type"]),
            "place_id": place.get("place_id"),
            "website": place.get("website"),
            "rating": place.get("rating"),
            "reviews": _first(place, ["user_ratings_total", "reviews"]),
            "source": place.get("source"),
            "sources": source_names,
            "source_count": source_count,
            "priority": priority,
            "opportunity_priority": priority,
            "opportunity_type": (
                "Qualified Seller Opportunity" if has_signal
                else "Potential Seller Opportunity"
            ),
            "seller_signal": seller_reason,
            "price_reduction_detected": price_data["detected"],
            "price_reduction_percentage": price_data["percentage"],
            "long_time_on_market": market_data["detected"],
            "days_on_market": market_data["days"],
            "days_listed": market_data["days"],
            "signals": {
                "seller": {"detected": seller_score > 0, "type": seller_reason, "score": max(0, seller_score)},
                "price_reduction": {"detected": price_data["detected"], "reduction_percent": price_data["percentage"], "percentage": price_data["percentage"], "score": price_data["score"]},
                "long_listing": {"detected": market_data["detected"], "days_on_market": market_data["days"], "score": market_data["score"]},
                "multi_source": {"detected": source_count > 1, "source_count": source_count, "sources": source_names},
                "relisting": {"detected": relisted},
                "price_history": {"detected": price_history},
            },
            "reasoning": reasoning,
            "signal_count": sum(bool(x) for x in (
                seller_score > 0, price_data["detected"], market_data["detected"],
                source_count > 1, relisted, price_history
            )),
            "opportunity_score": score,
        }
        filtered.append(output)

    priority_order = {"Priority": 4, "High": 3, "Medium": 2, "Low": 1}
    filtered.sort(key=lambda x: (
        priority_order.get(x.get("opportunity_priority", "Low"), 1),
        x.get("opportunity_score", 0),
        x.get("signal_count", 0),
    ), reverse=True)
    return filtered
