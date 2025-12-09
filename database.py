# database.py (FINAL — auto-create)
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import json

DATABASE_URL = (
    os.getenv("POSTGRES_URL")
    or os.getenv("DATABASE_URL")
    or os.getenv("SQLITE_URL")
    or "sqlite:///./nest_realtor.db"
)

# Support SQLite in local dev
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --------------- MODELS --------------- #

class BuyerLead(Base):
    __tablename__ = "buyer_leads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    price = Column(String)
    link = Column(String)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SellerLead(Base):
    __tablename__ = "seller_leads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    link = Column(String)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SocialLead(Base):
    __tablename__ = "social_leads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    platform = Column(String)
    title = Column(String)
    link = Column(String)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class UniversalScrape(Base):
    __tablename__ = "universal_scrapes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    source_url = Column(String)
    page_title = Column(String)
    preview_text = Column(Text)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class PaymentRecord(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    amount = Column(Integer)
    provider = Column(String)
    extra_metadata = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserUsage(Base):
    __tablename__ = "user_usage"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    used_searches = Column(Integer, default=0)
    credits = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)


class AutoLeadSetting(Base):
    """
    Stores automation rules per user.
    - filters: JSON string with filter params (location, etc.)
    """
    __tablename__ = "auto_lead_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    name = Column(String, default="default")
    filters = Column(Text, default="{}")
    interval_minutes = Column(Integer, default=360)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_run = Column(DateTime, nullable=True)

    def get_filters(self):
        try:
            return json.loads(self.filters or "{}")
        except Exception:
            return {}


# --------------- CREATE TABLES ON IMPORT --------------- #

def init_db():
    Base.metadata.create_all(bind=engine)

# Run on import (Fixes "no such table" forever)
init_db()
