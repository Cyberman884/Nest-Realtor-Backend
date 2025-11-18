# database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv('POSTGRES_URL') or os.getenv('DATABASE_URL') or os.getenv('SQLITE_URL') or 'sqlite:///./nest_realtor.db'

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class BuyerLead(Base):
    __tablename__ = 'buyer_leads'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    price = Column(String)
    link = Column(String)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class SellerLead(Base):
    __tablename__ = 'seller_leads'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    link = Column(String)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class SocialLead(Base):
    __tablename__ = 'social_leads'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    platform = Column(String)
    title = Column(String)
    link = Column(String)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class UniversalScrape(Base):
    __tablename__ = 'universal_scrapes'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    source_url = Column(String)
    page_title = Column(String)
    preview_text = Column(Text)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class PaymentRecord(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    amount = Column(Integer)
    provider = Column(String)
    metadata = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserUsage(Base):
    __tablename__ = 'user_usage'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    used_searches = Column(Integer, default=0)
    credits = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
# database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv('POSTGRES_URL') or os.getenv('DATABASE_URL') or os.getenv('SQLITE_URL') or 'sqlite:///./nest_realtor.db'

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class BuyerLead(Base):
    __tablename__ = 'buyer_leads'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    price = Column(String)
    link = Column(String)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class SellerLead(Base):
    __tablename__ = 'seller_leads'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    link = Column(String)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class SocialLead(Base):
    __tablename__ = 'social_leads'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    platform = Column(String)
    title = Column(String)
    link = Column(String)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class UniversalScrape(Base):
    __tablename__ = 'universal_scrapes'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    source_url = Column(String)
    page_title = Column(String)
    preview_text = Column(Text)
    raw = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class PaymentRecord(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    amount = Column(Integer)
    provider = Column(String)
    metadata = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserUsage(Base):
    __tablename__ = 'user_usage'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    used_searches = Column(Integer, default=0)
    credits = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
