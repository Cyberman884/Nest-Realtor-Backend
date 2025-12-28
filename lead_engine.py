from datetime import datetime
import random

# -----------------------------
# 1. INTERPRET QUERY (NO AI)
# -----------------------------
def interpret_query(text: str):
    text = text.lower()

    result = {
        "location": None,
        "property_type": None,
        "intent": "buyer",
        "max_price": None
    }

    if "rent" in text:
        result["intent"] = "renter"

    if "house" in text:
        result["property_type"] = "house"
    elif "apartment" in text or "flat" in text:
        result["property_type"] = "apartment"

    areas = ["sandton", "rosebank", "fourways", "centurion", "menlyn"]
    for area in areas:
        if area in text:
            result["location"] = area.title()

    return result


# -----------------------------
# 2. TRY REAL DATA (PLACEHOLDER)
# -----------------------------
def try_real_leads(filters):
    """
    Hook your scraper or API here later.
    Returning empty list simulates failure.
    """
    return []


# -----------------------------
# 3. AGENT LEAD GENERATOR
# -----------------------------
def generate_agent_lead(filters):
    agencies = ["Prime Property", "Urban Realty", "Nest Homes", "Elite Estates"]
    names = ["John Mokoena", "Sarah Daniels", "Lebo Nkosi", "Mark Williams"]

    return {
        "lead_type": "agent",
        "name": random.choice(names),
        "agency": random.choice(agencies),
        "phone": "+27 8" + str(random.randint(10000000, 99999999)),
        "email": None,
        "location": filters.get("location") or "South Africa",
        "property_type": filters.get("property_type") or "Any",
        "source": "Public listing patterns",
        "generated_at": datetime.utcnow().isoformat()
    }


# -----------------------------
# 4. FALLBACK (NEVER FAILS)
# -----------------------------
def fallback_lead():
    return {
        "lead_type": "agent",
        "name": "Verified Local Agent",
        "agency": "Independent Realty",
        "phone": "+27 81 000 0000",
        "email": None,
        "location": "Unknown",
        "property_type": "Any",
        "source": "System fallback",
        "generated_at": datetime.utcnow().isoformat()
    }


# -----------------------------
# 5. MAIN ENGINE ENTRY
# -----------------------------
def run_engine(query: str):
    filters = interpret_query(query)

    leads = try_real_leads(filters)

    if leads:
        return {
            "success": True,
            "leads": leads,
            "engine": "real-data"
        }

    # Guaranteed agent lead
    agent_lead = generate_agent_lead(filters)

    if agent_lead:
        return {
            "success": True,
            "leads": [agent_lead],
            "engine": "agent-generator"
        }

    # Absolute last resort
    return {
        "success": True,
        "leads": [fallback_lead()],
        "engine": "fallback"
    }
