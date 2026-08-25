from pathlib import Path

code = '''from datetime import datetime, timezone
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
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None

def days_listed(posted_date):
    date = parse_date(posted_date)
    if not date:
        return None
    return max((datetime.now(timezone.utc) - date).days, 0)

def normalize_price(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).replace(",", "").replace("R", "").strip()
    match = re.search(r"\\d+(?:\\.\\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None

def detect_price_reduction(lead):
    current = normalize_price(
        lead.get("price") or lead.get("current_price")
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

    # Never claim a price reduction without historical price data.
    if (
        previous is None
        or current is None
        or previous <= 0
        or current <= 0
        or current >= previous
    ):
        return result

    amount = previous - current
    percent = (amount / previous) * 100

    result.update({
        "detected": True,
        "reduction_amount": round(amount, 2),
        "reduction_percent": round(percent, 2),
    })

    return result

def listing_identity(lead):
    url = str(lead.get("url") or "").strip().lower()

    if url:
        return f"url:{url}"

    title = str(
        lead.get("title") or lead.get("name") or ""
    ).strip().lower()

    location = str(
        lead.get("location") or lead.get("address") or ""
    ).strip().lower()

    return f"listing:{title}|{location}"

def filter_leads(leads):
    """
    Convert raw listings into Nest Seller Opportunity Signals.

    Adds:
      - opportunity_type
      - opportunity_score
      - priority
      - days_listed
      - signals
      - reasoning

    Price reduction is only reported when a previous price
    has actually been supplied by the collection/history layer.
    """

    if not leads:
        return []

    unique = []
    seen = set()

    for lead in leads:
        identity = listing_identity(lead)

        if identity in seen:
            continue

        seen.add(identity)
        unique.append(dict(lead))

    opportunities = []

    for lead in unique:
        score = 0
        reasoning = []

        posted_date = (
            lead.get("posted_date")
            or lead.get("date_posted")
            or lead.get("created_at")
        )

        age = days_listed(posted_date)

        # LONG TIME ON MARKET
        long_listing = (
            age is not None and age >= LONG_LISTING_DAYS
        )

        if long_listing:
            score += SCORES["long_listing"]

            reasoning.append({
                "signal": "Long time on market",
                "detail": (
                    f"Listing has been observed for "
                    f"approximately {age} days."
                ),
                "evidence": {
                    "days_listed": age,
                    "threshold_days": LONG_LISTING_DAYS,
                },
            })

        # PRICE REDUCTION
        price_reduction = detect_price_reduction(lead)

        if price_reduction["detected"]:
            score += SCORES["price_reduction"]

            previous = price_reduction["previous_price"]
            current = price_reduction["current_price"]
            percent = price_reduction["reduction_percent"]

            reasoning.append({
                "signal": "Price reduction",
                "detail": (
                    f"Price reduced from R{previous:,.0f} "
                    f"to R{current:,.0f} "
                    f"({percent:.1f}% reduction)."
                ),
                "evidence": price_reduction,
            })

        # PRIORITY
        if score >= 90:
            priority = "Priority"
        elif score >= 70:
            priority = "High"
        elif score >= 40:
            priority = "Medium"
        else:
            priority = "Low"

        lead["opportunity_type"] = "Seller Opportunity Signal"
        lead["opportunity_score"] = score
        lead["priority"] = priority
        lead["days_listed"] = age

        lead["signals"] = {
            "long_listing": {
                "detected": long_listing,
                "days_listed": age,
                "threshold_days": LONG_LISTING_DAYS,
            },
            "price_reduction": price_reduction,
        }

        lead["reasoning"] = reasoning
        lead["signal_count"] = len(reasoning)

        opportunities.append(lead)

    opportunities.sort(
        key=lambda item: item.get("opportunity_score", 0),
        reverse=True,
    )

    return opportunities
'''

path = Path("/mnt/data/filter_leads.py")
path.write_text(code, encoding="utf-8")
print(path)
