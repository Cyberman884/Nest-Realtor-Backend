from fastapi import FastAPI, Request
from pydantic import BaseModel
import openai
import requests
import os

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")

# ==========================
# Helper: Generate Leads
# ==========================
def get_property_leads(location: str, limit: int = 5):
    # Your scraping / API logic will plug in here
    # For demo purposes this returns dummy leads
    leads = []
    for i in range(limit):
        leads.append({
            "title": f"{location} Property #{i+1}",
            "price": f"${(i+1)*100000}",
            "url": f"https://example.com/{location.lower()}/{i+1}"
        })
    return leads

# ==========================
# Models
# ==========================
class ChatRequest(BaseModel):
    user_id: str
    message: str

# ==========================
# Conversation State
# ==========================
user_sessions = {}

def user_is_asking_for_properties(msg: str) -> bool:
    keywords = [
        "send me leads",
        "properties in",
        "houses in",
        "listings",
        "show me properties",
        "buyers in",
        "sellers in",
        "real estate in"
    ]
    return any(k in msg.lower() for k in keywords)

# ==========================
# Router
# ==========================
@app.post("/chat")
async def chat(req: ChatRequest):
    user_id = req.user_id
    msg = req.message.strip()

    # Create user session if first time
    if user_id not in user_sessions:
        user_sessions[user_id] = {"lead_requests": 0}

    # ------------------------------
    # 1. If user is clearly asking for leads
    # ------------------------------
    if user_is_asking_for_properties(msg):

        # Extract location from message (simple extraction)
        words = msg.split()
        location = None
        for i, w in enumerate(words):
            if w.lower() in ["in", "at"]:
                if i + 1 < len(words):
                    location = words[i+1]
        
        if not location:
            location = "your selected area"

        # Count how many leads they want
        lead_count = 10
        for n in range(5, 51):
            if str(n) in msg:
                lead_count = n
                break

        user_sessions[user_id]["lead_requests"] += lead_count

        leads = get_property_leads(location, lead_count)

        return {
            "reply": (
                f"Here are {lead_count} properties I found in **{location}** 👇\n\n"
                f"Each lead is counted separately.\n\n"
                f"Current total leads used: {user_sessions[user_id]['lead_requests']}"
            ),
            "leads": leads
        }

    # ------------------------------
    # 2. If user is NOT asking for leads — normal AI assistant
    # ------------------------------
    completion = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are Nest Realtor AI. Only give leads when asked. Otherwise act like a normal assistant."},
            {"role": "user", "content": msg}
        ]
    )
    
    ai_reply = completion.choices[0].message["content"]

    return {"reply": ai_reply}
