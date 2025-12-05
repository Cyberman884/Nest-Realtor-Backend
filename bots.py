# bots.py — Final working version

import os
import requests
from bs4 import BeautifulSoup
import time
import urllib.parse

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# -------------------------------------------------------------
# Format Helpers
# -------------------------------------------------------------
def clean_price(price: str):
    try:
        return int("".join(filter(str.isdigit, price)))
    except:
        return None

# -------------------------------------------------------------
# 🔍 BUYER LEAD SCRAPER (Property24 / ScraperAPI)
# -------------------------------------------------------------
def search_buyer_leads(location: str, limit: int = 20):
    try:
        if SCRAPERAPI_KEY:
            url = (
                f"https://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url="
                + urllib.parse.quote(f"https://www.property24.com/for-sale/{location}/1")
            )
        else:
            url = f"https://www.property24.com/for-sale/{location}/1"

        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        listings = soup.select(".p24_regularTile") or soup.select(".listing,.listing-item")

        for item in listings[:limit]:
            title = item.select_one(".p24_title")
            price_tag = item.select_one(".p24_price")
            a = item.find("a")

            title = title.get_text(strip=True) if title else "Property Listing"
            price = price_tag.get_text(strip=True) if price_tag else ""
            link = (
                "https://www.property24.com" + a.get("href") 
                if a and a.get("href","").startswith("/") 
                else (a.get("href") if a else None)
            )

            results.append({
                "title": title,
                "price": clean_price(price),
                "raw_price": price,
                "link": link,
                "platform": "property24"
            })

        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# 🏡 SELLER LEAD SCRAPER (Gumtree)
# -------------------------------------------------------------
def search_seller_leads(location: str, limit: int = 20):
    try:
        if SCRAPERAPI_KEY:
            url = (
                f"https://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url=" +
                urllib.parse.quote(f"https://www.gumtree.co.za/s-houses-flats-for-sale/{location}/v1c9074l3100001p1")
            )
        else:
            url = f"https://www.gumtree.co.za/s-houses-flats-for-sale/{location}/v1c9074l3100001p1"

        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        listings = soup.select(".related-ad-title") or soup.select(".listing-title,.user-ad-row")

        for item in listings[:limit]:
            link = None
            a = item if item.name == "a" else item.find("a")
            if a:
                link = a.get("href")
                if link and link.startswith("/"):
                    link = "https://www.gumtree.co.za" + link

            title = item.get_text(strip=True)[:120]

            if link:
                results.append({
                    "title": title,
                    "link": link,
                    "platform": "gumtree"
                })
        return {"status": "success", "results": results}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# 🌐 SOCIAL SCRAPER
# -------------------------------------------------------------
def social_media_leads(query: str, platform: str = "instagram", limit: int = 10):
    try:
        results = []
        q = f"{platform} {query} real estate"

        # 🧠 SerpAPI if available
        if SERPAPI_KEY:
            api = f"https://serpapi.com/search.json?engine=google&q={urllib.parse.quote(q)}&api_key={SERPAPI_KEY}"
            data = requests.get(api, timeout=15).json()
            for item in (data.get("organic_results") or [])[:limit]:
                results.append({
                    "title": item.get("title")[:120],
                    "link": item.get("link"),
                    "snippet": item.get("snippet",""),
                    "platform": platform
                })
            return {"status": "success", "results": results}

        # 🌍 Google fallback
        url = f"https://www.google.com/search?q={urllib.parse.quote(q)}"
        headers = {"User-Agent":"Mozilla/5.0 (compatible; NestRealtorBot/1.0)"}
        soup = BeautifulSoup(requests.get(url, headers=headers, timeout=12).text, "html.parser")

        for item in (soup.select("div.g") or [])[:limit]:
            a = item.find("a")
            if not a: continue
            results.append({
                "title": item.get_text(strip=True)[:120],
                "link": a.get("href"),
                "platform": platform
            })
            time.sleep(0.1)

        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# 🌍 UNIVERSAL SCRAPER (Webhook Save)
# -------------------------------------------------------------
def universal_lead_scraper(url: str):
    try:
        final_url = (f"https://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={urllib.parse.quote(url)}"
                     if SCRAPERAPI_KEY else url)
        soup = BeautifulSoup(requests.get(final_url, timeout=30).text, "html.parser")

        return {
            "status": "success",
            "source_url": url,
            "page_title": soup.title.get_text(strip=True) if soup.title else "No Title",
            "preview_text": soup.get_text(" ", strip=True)[:1800]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# 🎯 SINGLE LEAD GENERATOR (used by /generate-lead)
# -------------------------------------------------------------
async def generate_lead(user_id: str, body: dict):
    location = body.get("location","").replace(" ", "-").lower()
    lead_type = body.get("type","buyer")

    if lead_type == "seller":
        data = search_seller_leads(location, limit=1)
    else:
        data = search_buyer_leads(location, limit=1)

    if data.get("status") != "success" or not data.get("results"):
        return None
    
    lead = data["results"][0]
    lead["user_id"] = user_id
    return lead
