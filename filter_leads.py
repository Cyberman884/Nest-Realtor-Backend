# filter_leads.py

def filter_leads(raw_places):

    if not raw_places:
        return []

    filtered = []
    seen = set()

    for place in raw_places:

        source = place.get("source", "unknown")

        # -------------------------
        # GOOGLE PLACES
        # -------------------------

        if source == "google_places":

            name = place.get("name")
            address = place.get("address") or place.get("formatted_address") or place.get("vicinity")
            website = place.get("website")
            place_id = place.get("place_id")
            rating = place.get("rating")
            reviews = place.get("user_ratings_total") or place.get("reviews")

        # -------------------------
        # GUMTREE
        # -------------------------

        elif source == "gumtree":

            name = place.get("title")
            address = place.get("location")
            website = place.get("url")
            place_id = None
            rating = None
            reviews = None

        # -------------------------
        # FACEBOOK
        # -------------------------

        elif source == "facebook_marketplace":

            name = place.get("title")
            address = place.get("location")
            website = place.get("url")
            place_id = None
            rating = None
            reviews = None

        # -------------------------
        # UNKNOWN
        # -------------------------

        else:

            name = place.get("name") or place.get("title")
            address = (
                place.get("address")
                or place.get("formatted_address")
                or place.get("location")
            )
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

        if score >= 4:
            priority = "High"
        elif score >= 2:
            priority = "Medium"
        else:
            priority = "Low"

        filtered.append({
            "name": name,
            "address": address,
            "place_id": place_id,
            "website": website,
            "rating": rating,
            "reviews": reviews,
            "priority": priority,
            "source": source
        })

    priority_order = {
        "High": 3,
        "Medium": 2,
        "Low": 1
    }

    filtered.sort(
        key=lambda x: priority_order.get(x["priority"], 1),
        reverse=True
    )

    return filtered