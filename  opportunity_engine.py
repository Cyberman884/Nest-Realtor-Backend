from datetime import datetime

# -----------------------------------------
# SCORING VALUES
# -----------------------------------------
55 {
    "province_match": 25,
    "city_match": 20,
    "area_match": 20,
    "property_type_match": 15,
    "price_match": 10,

    "long_listing": 20,
    "price_drop": 15,
    "multi_source": 25,
    "fsbo": 40,
    "fresh_listing": 10
}

# -----------------------------------------
# PRIORITY LEVELS
# -----------------------------------------

def calculate_priority(score):

    if score >= 90:
        return "PRIORITY"

    elif score >= 70:
        return "HIGH"

    elif score >= 40:
        return "MEDIUM"

    return "LOW"


# -----------------------------------------
# DEFAULT OPPORTUNITY OBJECT
# -----------------------------------------

def create_opportunity():

    return {

        "score": 0,

        "priority": "LOW",

        "matched_preferences": False,

        "duplicate": False,

        "price_drop": False,

        "multi_source": False,

        "fsbo": False,

        "long_listing": False,

        "fresh_listing": False,

        "date_found": datetime.utcnow().isoformat()
    }# -----------------------------------------
# PREFERENCE MATCHING ENGINE
# -----------------------------------------

def match_preferences(opportunity, preferences):

    """
    opportunity = property/opportunity dictionary

    preferences = agent preferences dictionary

    Returns the updated opportunity object.
    """

    score = opportunity.get("score", 0)

    # -----------------------------
    # Province
    # -----------------------------
    if (
        preferences.get("province")
        and opportunity.get("province")
        and preferences["province"].lower() == opportunity["province"].lower()
    ):
        score += SCORES["province_match"]

    # -----------------------------
    # City
    # -----------------------------
    if (
        preferences.get("city")
        and opportunity.get("city")
        and preferences["city"].lower() == opportunity["city"].lower()
    ):
        score += SCORES["city_match"]

    # -----------------------------
    # Area / Suburb
    # -----------------------------
    if (
        preferences.get("area")
        and opportunity.get("area")
        and preferences["area"].lower() == opportunity["area"].lower()
    ):
        score += SCORES["area_match"]

    # -----------------------------
    # Property Type
    # -----------------------------
    if (
        preferences.get("property_type")
        and opportunity.get("property_type")
        and preferences["property_type"].lower()
        == opportunity["property_type"].lower()
    ):
        score += SCORES["property_type_match"]

    # -----------------------------
    # Price Range
    # -----------------------------
    min_price = preferences.get("min_price")
    max_price = preferences.get("max_price")
    property_price = opportunity.get("price")

    if (
        property_price is not None
        and min_price is not None
        and max_price is not None
    ):
        if min_price <= property_price <= max_price:
            score += SCORES["price_match"]

    # -----------------------------
    # Final Updates
    # -----------------------------
    opportunity["score"] = score
    opportunity["matched_preferences"] = score > 0
    opportunity["priority"] = calculate_priority(score)

    return opportunity
    # -----------------------------------------
# OPPORTUNITY INTELLIGENCE ENGINE
# -----------------------------------------

def score_opportunity(opportunity):

    score = opportunity.get("score", 0)

    # -----------------------------
    # FSBO (For Sale By Owner)
    # -----------------------------
    if opportunity.get("fsbo"):
        score += SCORES["fsbo"]

    # -----------------------------
    # Price Drop
    # -----------------------------
    if opportunity.get("price_drop"):
        score += SCORES["price_drop"]

    # -----------------------------
    # Multi-Source Verification
    # -----------------------------
    if opportunity.get("multi_source"):
        score += SCORES["multi_source"]

    # -----------------------------
    # Long Listing
    # -----------------------------
    if opportunity.get("long_listing"):
        score += SCORES["long_listing"]

    # -----------------------------
    # Fresh Listing
    # -----------------------------
    if opportunity.get("fresh_listing"):
        score += SCORES["fresh_listing"]

    # -----------------------------
    # Update Opportunity
    # -----------------------------
    opportunity["score"] = score
    opportunity["priority"] = calculate_priority(score)

    return opportunity
    # -----------------------------------------
# DUPLICATE DETECTION ENGINE
# -----------------------------------------

def detect_duplicates(opportunities):

    """
    Removes duplicate opportunities.

    Returns a new list containing only unique opportunities.
    """

    unique_opportunities = []
    seen = set()

    for opportunity in opportunities:

        key = (
            str(opportunity.get("address", "")).strip().lower(),
            str(opportunity.get("city", "")).strip().lower(),
            str(opportunity.get("property_type", "")).strip().lower(),
            opportunity.get("price")
        )

        if key in seen:
            opportunity["duplicate"] = True
            continue

        opportunity["duplicate"] = False
        seen.add(key)
        unique_opportunities.append(opportunity)

    return unique_opportunities
    # -----------------------------------------
# OPPORTUNITY RANKING ENGINE
# -----------------------------------------

def rank_opportunities(opportunities, minimum_score=40):

    """
    Filters and ranks opportunities from highest
    score to lowest.
    """

    ranked = []

    for opportunity in opportunities:

        # Ignore duplicates
        if opportunity.get("duplicate"):
            continue

        # Ignore low-quality opportunities
        if opportunity.get("score", 0) < minimum_score:
            continue

        ranked.append(opportunity)

    # Highest score first
    ranked.sort(
        key=lambda opportunity: opportunity["score"],
        reverse=True
    )

    return ranked
    # -----------------------------------------
# OPPORTUNITY ASSIGNMENT ENGINE
# -----------------------------------------

PLAN_LIMITS = {
    "starter": 10,
    "growth": 20,
    "professional": 30
}


def assign_opportunities(agent, ranked_opportunities):

    """
    Assign opportunities to an agent based on
    their subscription plan.
    """

    plan = agent.get("plan", "starter").lower()

    limit = PLAN_LIMITS.get(plan, 10)

    assigned = ranked_opportunities[:limit]

    for opportunity in assigned:
        opportunity["assigned_to"] = agent.get("id")
        opportunity["assigned_at"] = datetime.utcnow().isoformat()

    return assigned# -----------------------------------------
# MONTHLY DELIVERY ENGINE
# -----------------------------------------

def run_monthly_delivery(agents, opportunities):

    """
    Complete monthly opportunity pipeline.

    Returns a dictionary containing each agent's
    assigned opportunities.
    """

    # Remove duplicates
    opportunities = detect_duplicates(opportunities)

    # Rank opportunities
    ranked = rank_opportunities(opportunities)

    deliveries = {}

    for agent in agents:

        assigned = assign_opportunities(
            agent,
            ranked
        )

        deliveries[agent["id"]] = assigned

    return deliveries
    # -----------------------------------------
# DATABASE SAVE ENGINE
# -----------------------------------------

def prepare_opportunity_record(opportunity):

    """
    Creates a clean database record
    ready to insert into Supabase.
    """

    return {

        "address": opportunity.get("address"),

        "province": opportunity.get("province"),

        "city": opportunity.get("city"),

        "area": opportunity.get("area"),

        "property_type": opportunity.get("property_type"),

        "price": opportunity.get("price"),

        "score": opportunity.get("score"),

        "priority": opportunity.get("priority"),

        "matched_preferences": opportunity.get("matched_preferences"),

        "duplicate": opportunity.get("duplicate"),

        "fsbo": opportunity.get("fsbo"),

        "price_drop": opportunity.get("price_drop"),

        "multi_source": opportunity.get("multi_source"),

        "long_listing": opportunity.get("long_listing"),

        "fresh_listing": opportunity.get("fresh_listing"),

        "assigned_to": opportunity.get("assigned_to"),

        "assigned_at": opportunity.get("assigned_at"),

        "date_found": opportunity.get("date_found")
    }


def prepare_database_batch(opportunities):

    """
    Converts a list of opportunities into
    records ready for database insertion.
    """

    records = []

    for opportunity in opportunities:
        records.append(
            prepare_opportunity_record(opportunity)
        )

    return records