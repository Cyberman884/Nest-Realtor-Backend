# filter_leads.py

def filter_leads(raw_places):
    """
    Takes raw Google Places results and returns clean, usable leads
    """

    if not raw_places:
        return []

    filtered = []
    seen = set()  # for duplicate removal

    for place in raw_places:

        name = place.get("name")
        address = place.get("formatted_address") or place.get("vicinity")
        place_id = place.get("place_id")  # ✅ CRITICAL
        website = place.get("website")
        rating = place.get("rating")
        user_ratings_total = place.get("user_ratings_total")

        # ❌ Skip duplicates (based on name only for now)
        unique_key = f"{name}"
        if unique_key in seen:
            continue
        seen.add(unique_key)

        # 🎯 Basic scoring
        score = 0

        if website:
            score += 2
        if rating and rating >= 4:
            score += 1
        if user_ratings_total and user_ratings_total > 10:
            score += 1

        # 🏷️ Priority label
        if score >= 4:
            priority = "High"
        elif score >= 2:
            priority = "Medium"
        else:
            priority = "Low"

        # ✅ Clean lead object
        lead = {
            "name": name,
            "address": address,
            "place_id": place_id,  # 🔥 THIS FIXES PHONE NUMBERS
            "website": website,
            "rating": rating,
            "reviews": user_ratings_total,
            "priority": priority
        }

        filtered.append(lead)

    # 🔥 Sort by priority (High → Low)
    priority_order = {"High": 3, "Medium": 2, "Low": 1}
    filtered.sort(key=lambda x: priority_order[x["priority"]], reverse=True)

    return filtered