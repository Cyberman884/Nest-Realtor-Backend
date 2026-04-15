# filter_leads.py

def filter_leads(raw_places, target_area=None, min_price=None, max_price=None, property_type=None):
    """
    Takes raw Google Places results and returns clean, ranked, deal-relevant leads
    """

    if not raw_places:
        return []

    filtered = []
    seen = set()  # for duplicate removal

    for place in raw_places:

        name = place.get("name")
        address = place.get("formatted_address") or place.get("vicinity")
        place_id = place.get("place_id")
        website = place.get("website")
        rating = place.get("rating")
        user_ratings_total = place.get("user_ratings_total")

        # ❌ Skip duplicates
        unique_key = f"{name}"
        if unique_key in seen:
            continue
        seen.add(unique_key)

        # =========================
        # 🎯 DEAL MATCH SCORING
        # =========================
        score = 0
        reasons = []

        # 📍 Area match (basic keyword match)
        if target_area and address and target_area.lower() in address.lower():
            score += 3
            reasons.append("Operates in your target area")

        # 🌐 Website = more professional / reachable
        if website:
            score += 1
            reasons.append("Has active website")

        # ⭐ Rating quality
        if rating and rating >= 4:
            score += 1
            reasons.append("Highly rated")

        # 📊 Activity proxy (reviews)
        if user_ratings_total and user_ratings_total > 10:
            score += 1
            reasons.append("Active with client reviews")

        # 🏷️ Match level (RENAMED from priority)
        if score >= 5:
            match_level = "Strong Match"
        elif score >= 3:
            match_level = "Good Match"
        else:
            match_level = "Low Match"

        # 📊 Match score (visible to user)
        match_score = min(score * 20, 100)  # scale to 100

        # ✅ Final lead object
        lead = {
            "name": name,
            "address": address,
            "place_id": place_id,
            "website": website,
            "rating": rating,
            "reviews": user_ratings_total,
            "match_level": match_level,
            "match_score": match_score,
            "reasons": reasons
        }

        filtered.append(lead)

    # 🔥 Sort by best deal relevance
    filtered.sort(key=lambda x: x["match_score"], reverse=True)

    return filtered