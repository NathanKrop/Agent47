"""SQLAlchemy models for listings, outreach logs, and DNC list."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import DATABASE_URL

Base = declarative_base()


class WebsiteStatus(enum.Enum):
    NO_WEBSITE = "no_website"
    BROKEN = "broken"
    PARKED = "parked"
    PLACEHOLDER = "placeholder"
    POOR = "poor"
    GOOD = "good"


class OutreachStatus(enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    REPLIED = "replied"
    OPTED_OUT = "opted_out"
    FAILED = "failed"
    DO_NOT_CONTACT = "do_not_contact"


class Listing(Base):
    __tablename__ = "listings"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String)
    county = Column(String)
    category = Column(String)
    google_maps_url = Column(String)
    phone = Column(String)
    email = Column(String)
    website_url = Column(String)
    website_status = Column(Enum(WebsiteStatus), default=WebsiteStatus.NO_WEBSITE)
    rating = Column(Float)
    review_count = Column(Integer, default=0)
    score = Column(Integer, default=0)
    priority = Column(String, default="SKIP")
    phone_verified = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    active_recently = Column(Boolean, default=False)
    likely_closed = Column(Boolean, default=False)
    outreach_status = Column(String, default="pending")
    last_checked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OutreachLog(Base):
    __tablename__ = "outreach_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(String, index=True)
    channel = Column(String)
    template_name = Column(String)
    recipient = Column(String)
    status = Column(Enum(OutreachStatus), default=OutreachStatus.PENDING)
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    delivered_at = Column(DateTime(timezone=True))
    replied_at = Column(DateTime(timezone=True))
    error_message = Column(Text)


class DoNotContact(Base):
    __tablename__ = "do_not_contact"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contact = Column(String, unique=True, index=True)
    reason = Column(String)
    added_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
