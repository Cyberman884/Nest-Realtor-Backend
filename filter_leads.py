from pathlib import Path
p = Path("/mnt/data/filter_leads_backend_compatible.py")
p.write_text("""from datetime import datetime, timezone
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
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).replace(tzinfo=timezone.utc)
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
    match = re.search(r"\\d+(?:\\.\\d+)?", str(value).replace(",", "").replace("R", ""))
    return float(match.group(0)) if match else None

def detect_price_reduction(lead):
    current = normalize_price(lead.get("price") or lead.get("current_price"))
    previous = normalize_price(
        lead.get("previous_price") or lead.get("old_price")
        or lead.get("original_price") or lead.get("price_before")
        or lead.get("last_price")
    )
    result = {
        "detected": False,
        "previous_price": previous,
        "current_price": current,
        "reduction_amount": None,
        "reduction_percent": None,
    }
    if previous is None or current is None or previous <= 0 or current <= 0 or current >= previous:
        return result
    amount = previous - current
    result.update({
        "detected": True,
        "reduction_amount": round(amount, 2),
        "reduction_percent": round((amount / previous) * 100, 2),
    })
    return result

def filter_leads(raw_places):
    if not raw_places:
        return []

    filtered = []
    seen = set()

    for place in raw_places:
        source = place.get("source", "unknown")

        if source == "google_places":
            name = place.get("name")
            address = place.get("address") or place.get("formatted_address") or place.get("vicinity")
            website = place.get("website")
            place_id = place.get("place_id")
            rating = place.get("rating")
            reviews = place.get("user_ratings_total") or place.get("reviews")

        elif source == "gumtree":
            name = place.get("title")
            address = place.get("location")
            website = place.get("url")
            place_id = rating = reviews = None

        elif source == "facebook_marketplace":
            name = place.get("title")
            address = place.get("location")
            website = place.get("url")
            place_id = rating = reviews = None

        else:
            name = place.get("name") or place.get("title")
            address = place.get("address") or place.get("formatted_address") or place.get("location")
            website = place.get("website") or place.get("url")
            place_id = place.get("place_id")
            rating = place.get("rating")
            reviews = place.get("user_ratings_total")

        if not name:
            continue

        unique_key = f"{source}-{name}"
        if unique_key in seen:
            continue
        seen.add(unique_key)

        score = 0
        if website:
            score += 2
        if rating and rating >= 4:
            score += 1
        if reviews and reviews > 10:
            score += 1

        age = days_listed(
            place.get("posted_date")
            or place.get("date_posted")
            or place.get("created_at")
        )

        long_listing = age is not None and age >= LONG_LISTING_DAYS
        price_reduction = detect_price_reduction(place)

        opportunity_score = 0
        reasoning = []

        if long_listing:
            opportunity_score += SCORES["long_listing"]
            reasoning.append({
                "signal": "Long time on market",
                "detail": f"Listing has been observed for approximately {age} days.",
                "evidence": {"days_listed": age, "threshold_days": LONG_LISTING_DAYS},
            })

        if price_reduction["detected"]:
            opportunity_score += SCORES["price_reduction"]
            previous = price_reduction["previous_price"]
            current = price_reduction["current_price"]
            percent = price_reduction["reduction_percent"]
            reasoning.append({
                "signal": "Price reduction",
                "detail": f"Price reduced from R{previous:,.0f} to R{current:,.0f} ({percent:.1f}% reduction).",
                "evidence": price_reduction,
            })

        if score >= 4:
            priority = "High"
        elif score >= 2:
            priority = "Medium"
        else:
            priority = "Low"

        if opportunity_score >= 90:
            opportunity_priority = "Priority"
        elif opportunity_score >= 70:
            opportunity_priority = "High"
        elif opportunity_score >= 40:
            opportunity_priority = "Medium"
        else:
            opportunity_priority = "Low"

        filtered.append({
            "name": name,
            "address": address,
            "place_id": place_id,
            "website": website,
            "rating": rating,
            "reviews": reviews,
            "priority": priority,
            "source": source,
            "opportunity_type": "Seller Opportunity Signal",
            "opportunity_score": opportunity_score,
            "opportunity_priority": opportunity_priority,
            "days_listed": age,
            "signal_count": len(reasoning),
            "signals": {
                "long_listing": {
                    "detected": long_listing,
                    "days_listed": age,
                    "threshold_days": LONG_LISTING_DAYS,
                },
                "price_reduction": price_reduction,
            },
            "reasoning": reasoning,
        })

    priority_order = {"High": 3, "Medium": 2, "Low": 1}
    filtered.sort(
        key=lambda x: (x.get("opportunity_score", 0), priority_order.get(x["priority"], 1)),
        reverse=True,
    )
    return filtered
""", encoding="utf-8")
print(p)
