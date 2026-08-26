from datetime import datetime, timezone
import re

LONG_LISTING_DAYS = 90

SCORES = {
    "long_listing": 20,
    "price_reduction": 15,
}


def parse_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            pass

    return None


def days_listed(posted_date):
    date = parse_date(posted_date)

    if not date:
        return None

    return max(
        (datetime.now(timezone.utc) - date).days,
        0
    )


def normalize_price(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = (
        str(value)
        .replace(",", "")
        .replace("R", "")
        .strip()
    )

    match = re.search(
        r"\d+(?:\.\d+)?",
        text
    )

    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def detect_price_reduction(lead):
    current = normalize_price(
        lead.get("price")
        or lead.get("current_price")
    )

    previous = normalize_price(
        lead.get("previous_price")
        or lead.get("old_price")
        or lead.get("original_price")
        or lead.get("price_before")
        or lead.get("last_price")
    )

    result = {
        "detected": False,
        "previous_price": previous,
        "current_price": current,
        "reduction_amount": None,
        "reduction_percent": None,
    }

    # Do not claim a price reduction unless
    # historical price data actually exists.
    if (
        previous is None
        or current is None
        or previous <= 0
        or current <= 0
        or current >= previous
    ):
        return result

    amount = previous - current

    percent = (
        amount / previous
    ) * 100

    result.update({
        "detected": True,
        "reduction_amount": round(
            amount,
            2
        ),
        "reduction_percent": round(
            percent,
            2
        ),
    })

    return result


def listing_identity(lead):
    """
    Used for basic duplicate prevention.

    Prefer the listing URL.
    Otherwise use title + location.
    """

    url = str(
        lead.get("url") or ""
    ).strip().lower()

    if url:
        return f"url:{url}"

    title = str(
        lead.get("title")
        or lead.get("name")
        or ""
    ).strip().lower()

    location = str(
        lead.get("location")
        or lead.get("address")
        or ""
    ).strip().lower()

    return f"listing:{title}|{location}"


def filter_leads(raw_places):
    """
    Convert raw listings into Nest Seller Opportunity Signals.

    Adds:

        opportunity_type
        opportunity_score
        opportunity_priority
        days_listed
        signals
        reasoning

    Price reduction is only reported when a previous price
    has actually been supplied by the collection/history layer.
    """

    if not raw_places:
        return []

    filtered = []
    seen = set()

    for place in raw_places:

        source = place.get(
            "source",
            "unknown"
        )

        # -------------------------------------------------
        # GOOGLE PLACES
        # -------------------------------------------------

        if source == "google_places":

            name = place.get(
                "name"
            )

            address = (
                place.get("address")
                or place.get("formatted_address")
                or place.get("vicinity")
            )

            website = place.get(
                "website"
            )

            place_id = place.get(
                "place_id"
            )

            rating = place.get(
                "rating"
            )

            reviews = (
                place.get(
                    "user_ratings_total"
                )
                or place.get(
                    "reviews"
                )
            )

        # -------------------------------------------------
        # GUMTREE
        # -------------------------------------------------

        elif source == "gumtree":

            name = place.get(
                "title"
            )

            address = place.get(
                "location"
            )

            website = place.get(
                "url"
            )

            place_id = None
            rating = None
            reviews = None

        # -------------------------------------------------
        # FACEBOOK MARKETPLACE
        # -------------------------------------------------

        elif source == "facebook_marketplace":

            name = place.get(
                "title"
            )

            address = place.get(
                "location"
            )

            website = place.get(
                "url"
            )

            place_id = None
            rating = None
            reviews = None

        # -------------------------------------------------
        # UNKNOWN SOURCE
        # -------------------------------------------------

        else:

            name = (
                place.get("name")
                or place.get("title")
            )

            address = (
                place.get("address")
                or place.get("formatted_address")
                or place.get("location")
            )

            website = (
                place.get("website")
                or place.get("url")
            )

            place_id = place.get(
                "place_id"
            )

            rating = place.get(
                "rating"
            )

            reviews = place.get(
                "user_ratings_total"
            )

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not name:
            continue

        unique_key = (
            f"{source}-{name}"
        )

        if unique_key in seen:
            continue

        seen.add(
            unique_key
        )

        # -------------------------------------------------
        # EXISTING QUALITY SCORE
        # -------------------------------------------------

        score = 0

        if website:
            score += 2

        if rating and rating >= 4:
            score += 1

        if reviews and reviews > 10:
            score += 1

        # -------------------------------------------------
        # NEST SELLER SIGNALS
        # -------------------------------------------------

        posted_date = (
            place.get("posted_date")
            or place.get("date_posted")
            or place.get("created_at")
        )

        age = days_listed(
            posted_date
        )

        # -------------------------------------------------
        # LONG TIME ON MARKET
        # -------------------------------------------------

        long_listing = (
            age is not None
            and age >= LONG_LISTING_DAYS
        )

        # -------------------------------------------------
        # PRICE REDUCTION
        # -------------------------------------------------

        price_reduction = (
            detect_price_reduction(
                place
            )
        )

        # -------------------------------------------------
        # OPPORTUNITY SCORE
        # -------------------------------------------------

        opportunity_score = 0

        reasoning = []

        if long_listing:

            opportunity_score += (
                SCORES[
                    "long_listing"
                ]
            )

            reasoning.append({
                "signal":
                    "Long time on market",

                "detail":
                    (
                        "Listing has been observed "
                        f"for approximately {age} days."
                    ),

                "evidence": {
                    "days_listed":
                        age,

                    "threshold_days":
                        LONG_LISTING_DAYS,
                },
            })

        if price_reduction[
            "detected"
        ]:

            opportunity_score += (
                SCORES[
                    "price_reduction"
                ]
            )

            previous = (
                price_reduction[
                    "previous_price"
                ]
            )

            current = (
                price_reduction[
                    "current_price"
                ]
            )

            percent = (
                price_reduction[
                    "reduction_percent"
                ]
            )

            reasoning.append({
                "signal":
                    "Price reduction",

                "detail":
                    (
                        f"Price reduced from "
                        f"R{previous:,.0f} "
                        f"to R{current:,.0f} "
                        f"({percent:.1f}% reduction)."
                    ),

                "evidence":
                    price_reduction,
            })

        # -------------------------------------------------
        # OPPORTUNITY PRIORITY
        # -------------------------------------------------

        if opportunity_score >= 90:

            opportunity_priority = (
                "Priority"
            )

        elif opportunity_score >= 70:

            opportunity_priority = (
                "High"
            )

        elif opportunity_score >= 40:

            opportunity_priority = (
                "Medium"
            )

        else:

            opportunity_priority = (
                "Low"
            )

        # -------------------------------------------------
        # EXISTING PRIORITY
        # -------------------------------------------------

        if score >= 4:

            priority = "High"

        elif score >= 2:

            priority = "Medium"

        else:

            priority = "Low"

        # -------------------------------------------------
        # RETURN OBJECT
        # -------------------------------------------------

        filtered.append({

            "name":
                name,

            "address":
                address,

            "place_id":
                place_id,

            "website":
                website,

            "rating":
                rating,

            "reviews":
                reviews,

            "priority":
                priority,

            "source":
                source,

            # ---------------------------------------------
            # NEST OPPORTUNITY DATA
            # ---------------------------------------------

            "opportunity_type":
                "Seller Opportunity Signal",

            "opportunity_score":
                opportunity_score,

            "opportunity_priority":
                opportunity_priority,

            "days_listed":
                age,

            "signal_count":
                len(reasoning),

            "signals": {

                "long_listing": {

                    "detected":
                        long_listing,

                    "days_listed":
                        age,

                    "threshold_days":
                        LONG_LISTING_DAYS,
                },

                "price_reduction":
                    price_reduction,
            },

            "reasoning":
                reasoning,
        })

    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------

    priority_order = {
        "High": 3,
        "Medium": 2,
        "Low": 1,
    }

    filtered.sort(
        key=lambda x: (
            x.get(
                "opportunity_score",
                0
   .         ),

            priority_order.get(
                x.get(
                    "priority",
                    "Low"
                ),
                1
            ),
        ),

        reverse=True,
    )

    return filtered