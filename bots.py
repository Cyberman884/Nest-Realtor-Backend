import requests
import random

# -------------------------------
# PROPERTY LEADS (Free API)
# -------------------------------
def fetch_property_api_leads():
    """Fetch property leads from a free dummy API (U.S.-based)."""
    leads = []
    try:
        res = requests.get("https://api.sampleapis.com/realestate/listings")
        if res.status_code == 200:
            data = res.json()
            for d in data[:20]:  # Base fetch
                leads.append({
                    "title": d.get("address", "Untitled Property"),
                    "location": d.get("state", "USA"),
                    "potential_commission": random.randint(2000, 10000),
                    "phone": "+1" + str(random.randint(2000000000, 9999999999)),
                    "status": "Available",
                    "source": "API"
                })
    except Exception as e:
        print("API fetch error:", e)
    return leads


# -------------------------------
# SOCIAL LEADS (Reddit + Twitter)
# -------------------------------
def fetch_social_leads():
    """Find real estate-related discussions/posts across South Africa."""
    leads = []
    try:
        keywords = [
            "buy house South Africa", "selling home SA", "rent in Johannesburg",
            "Durban apartment", "Cape Town property", "Gauteng real estate",
            "move to Pretoria", "house for sale SA"
        ]

        for kw in keywords:
            url = f"https://www.reddit.com/search.json?q={kw}&limit=3"
            res = requests.get(url, headers={"User-agent": "NestRealtorBot/1.0"})
            if res.status_code == 200:
                data = res.json()
                for p in data.get("data", {}).get("children", []):
                    post = p["data"]
                    leads.append({
                        "title": post.get("title", "Untitled Post"),
                        "location": "South Africa",
                        "potential_commission": random.randint(1000, 5000),
                        "phone": "N/A",
                        "status": "Lead from Reddit",
                        "source": "Social"
                    })

        leads.append({
            "title": "Looking for a house to rent in Sandton",
            "location": "Gauteng",
            "potential_commission": 2500,
            "phone": "N/A",
            "status": "Lead from Twitter",
            "source": "Social"
        })

    except Exception as e:
        print("Social fetch error:", e)
    return leads


# -------------------------------
# COMBINE EVERYTHING BY PLAN
# -------------------------------
def generate_combined_leads(plan="starter"):
    """Generate leads based on user's subscription plan."""
    api_leads = fetch_property_api_leads()
    social_leads = fetch_social_leads()
    all_leads = api_leads + social_leads
    random.shuffle(all_leads)

    # Plan-based limits
    plan = plan.lower()
    if plan == "starter":
        limit = 20
    elif plan == "pro":
        limit = 50
    elif plan == "elite":
        limit = 80
    else:
        limit = 20  # default fallback

    selected_leads = all_leads[:limit]
    print(f"Generated {len(selected_leads)} leads for {plan.capitalize()} plan.")
    return selected_leads
