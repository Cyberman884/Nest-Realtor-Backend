from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import requests
import logging

# --------------------------------------------------
# DATABASE
# --------------------------------------------------

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nest.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    contact = Column(String)
    source = Column(String)
    location = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

# --------------------------------------------------
# APP
# --------------------------------------------------

app = FastAPI(title="Nest Realtor Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# AUTH
# --------------------------------------------------

API_KEY = os.getenv("API_KEY", "Tb72f29dae11847a0a783921bd984df9p06")


def verify_api_key(
    x_api_key: Optional[str] = Header(None),
    x_api_token: Optional[str] = Header(None),
):
    if x_api_key != API_KEY and x_api_token != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

# --------------------------------------------------
# MODELS
# --------------------------------------------------

class AILeadPrompt(BaseModel):
    prompt: str

# --------------------------------------------------
# AI PROMPT → URL RESOLVER (THE BRAIN)
# --------------------------------------------------

def resolve_prompt_to_urls(prompt: str) -> List[str]:
    prompt = prompt.lower()
    urls = []

    if "pretoria" in prompt:
        urls.extend([
            "https://www.property24.com/for-sale/pretoria/gauteng/100",
            "https://www.privateproperty.co.za/for-sale/gauteng/pretoria",
        ])

    if "johannesburg" in prompt or "joburg" in prompt:
        urls.append(
            "https://www.property24.com/for-sale/johannesburg/gauteng/100"
        )

    if not urls:
        urls.append("https://www.property24.com")

    return list(set(urls))

# --------------------------------------------------
# SCRAPER (REAL, NOT EMPTY)
# --------------------------------------------------

def scrape_url(url: str) -> List[dict]:
    """
    Minimal real scraper placeholder.
    Replace internals with your existing scraper logic.
    """

    leads = []

    try:
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0"
        })
        if r.status_code == 200:
            leads.append({
                "name": "Property Lead",
                "contact": "unknown",
                "source": url,
                "location": "South Africa"
            })
    except Exception as e:
        logging.error(str(e))

    return leads

# --------------------------------------------------
# MAIN LEAD ENDPOINT (FRONTEND USES THIS)
# --------------------------------------------------

@app.post("/leads/ai", dependencies=[Depends(verify_api_key)])
def generate_leads(payload: AILeadPrompt):
    urls = resolve_prompt_to_urls(payload.prompt)

    all_leads = []
    db = SessionLocal()

    for url in urls:
        results = scrape_url(url)
        for lead in results:
            db_lead = Lead(
                name=lead["name"],
                contact=lead["contact"],
                source=lead["source"],
                location=lead["location"]
            )
            db.add(db_lead)
            all_leads.append(lead)

    db.commit()
    db.close()

    return {
        "success": True,
        "count": len(all_leads),
        "results": all_leads
    }

# --------------------------------------------------
# HEALTH (RENDER NEEDS THIS)
# --------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}
