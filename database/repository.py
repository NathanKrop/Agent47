"""Database CRUD helpers."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, func, or_, and_
from sqlalchemy.orm import Session

from database.models import DoNotContact, Listing, OutreachLog, OutreachStatus, SessionLocal, WebsiteStatus


def listing_id(name: str, address: str) -> str:
    """Generate dedup ID from name + address."""
    raw = f"{name.strip().lower()}|{(address or '').strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_session() -> Session:
    return SessionLocal()


def get_listing(listing_id_str: str) -> dict[str, Any] | None:
    with get_session() as session:
        row = session.get(Listing, listing_id_str)
        return _listing_to_dict(row) if row else None


def upsert_listing(data: dict[str, Any]) -> str:
    lid = data.get("id") or listing_id(data.get("name", ""), data.get("address", ""))
    with get_session() as session:
        existing = session.get(Listing, lid)
        ws = data.get("website_status", "no_website")
        if isinstance(ws, str):
            try:
                ws = WebsiteStatus(ws.lower())
            except ValueError:
                ws = WebsiteStatus.NO_WEBSITE

        if existing:
            existing.name = data.get("name", existing.name)
            existing.address = data.get("address", existing.address)
            existing.county = data.get("county", existing.county)
            existing.category = data.get("category", existing.category)
            existing.google_maps_url = data.get("google_maps_url", existing.google_maps_url)
            existing.phone = data.get("phone", existing.phone)
            existing.email = data.get("email", existing.email)
            existing.website_url = data.get("website_url", existing.website_url)
            existing.website_status = ws
            existing.rating = data.get("rating", existing.rating)
            existing.review_count = data.get("review_count", existing.review_count)
            existing.score = data.get("score", existing.score)
            existing.priority = data.get("priority", existing.priority)
            existing.phone_verified = data.get("phone_verified", existing.phone_verified)
            existing.email_verified = data.get("email_verified", existing.email_verified)
            existing.active_recently = data.get("active_recently", existing.active_recently)
            existing.likely_closed = data.get("likely_closed", existing.likely_closed)
            existing.last_checked_at = datetime.now(timezone.utc)
        else:
            row = Listing(
                id=lid,
                name=data.get("name", ""),
                address=data.get("address"),
                county=data.get("county"),
                category=data.get("category"),
                google_maps_url=data.get("google_maps_url"),
                phone=data.get("phone"),
                email=data.get("email"),
                website_url=data.get("website_url"),
                website_status=ws,
                rating=data.get("rating"),
                review_count=data.get("review_count", 0),
                score=data.get("score", 0),
                priority=data.get("priority", "SKIP"),
                phone_verified=data.get("phone_verified", False),
                email_verified=data.get("email_verified", False),
                active_recently=data.get("active_recently", False),
                likely_closed=data.get("likely_closed", False),
                created_at=datetime.now(timezone.utc),
                last_checked_at=datetime.now(timezone.utc),
            )
            session.add(row)
        session.commit()
    return lid


def log_outreach(
    listing_id_str: str,
    channel: str,
    template_name: str,
    recipient: str,
    status: str,
    error_message: str | None = None,
) -> None:
    with get_session() as session:
        try:
            outreach_status = OutreachStatus(status)
        except ValueError:
            outreach_status = OutreachStatus.FAILED

        log = OutreachLog(
            listing_id=listing_id_str,
            channel=channel,
            template_name=template_name,
            recipient=recipient,
            status=outreach_status,
            sent_at=datetime.now(timezone.utc),
            error_message=error_message,
        )
        session.add(log)
        session.commit()


def is_do_not_contact(contact: str) -> bool:
    with get_session() as session:
        return session.query(DoNotContact).filter_by(contact=contact).first() is not None


def add_do_not_contact(contact: str, reason: str = "opt_out") -> None:
    with get_session() as session:
        if not session.query(DoNotContact).filter_by(contact=contact).first():
            session.add(DoNotContact(contact=contact, reason=reason, added_at=datetime.now(timezone.utc)))
            session.commit()


def mark_outreach_replied(recipient: str, channel: str | None = None) -> bool:
    with get_session() as session:
        query = session.query(OutreachLog).filter(OutreachLog.recipient == recipient)
        if channel:
            query = query.filter(OutreachLog.channel == channel)
        outreach = query.order_by(desc(OutreachLog.sent_at)).first()
        if not outreach:
            return False
        outreach.status = OutreachStatus.REPLIED
        outreach.replied_at = datetime.now(timezone.utc)
        session.commit()
        return True


def mark_outreach_opted_out(contact: str, channel: str | None = None, reason: str = "user_reply") -> bool:
    add_do_not_contact(contact, reason)
    with get_session() as session:
        query = session.query(OutreachLog).filter(OutreachLog.recipient == contact)
        if channel:
            query = query.filter(OutreachLog.channel == channel)
        outreach = query.order_by(desc(OutreachLog.sent_at)).first()
        if not outreach:
            return False
        outreach.status = OutreachStatus.OPTED_OUT
        session.commit()
        return True


def get_verified_leads_with_email(limit: int = 10) -> list[dict[str, Any]]:
    """Return leads that have an email address, ordered by score desc."""
    with get_session() as session:
        rows = (
            session.query(Listing)
            .filter(and_(Listing.email.isnot(None), Listing.email != ""))
            .filter(Listing.likely_closed.is_(False))
            .order_by(desc(Listing.score))
            .limit(limit)
            .all()
        )
        return [_listing_to_dict(r) for r in rows]


def get_outreach_candidates(min_priority: str = "PRIORITY_2", limit: int = 100) -> list[dict[str, Any]]:
    priority_order = {"PRIORITY_1": 3, "PRIORITY_2": 2, "PRIORITY_3": 1, "SKIP": 0}
    min_level = priority_order.get(min_priority, 2)

    with get_session() as session:
        rows = (
            session.query(Listing)
            .filter(Listing.priority != "SKIP")
            .filter(Listing.likely_closed.is_(False))
            .order_by(desc(Listing.score))
            .limit(limit * 3)
            .all()
        )
        results = []
        for row in rows:
            if priority_order.get(row.priority, 0) >= min_level:
                results.append(_listing_to_dict(row))
            if len(results) >= limit:
                break
        return results


def get_dashboard_stats() -> dict[str, Any]:
    with get_session() as session:
        total = session.query(func.count(Listing.id)).scalar() or 0
        no_website = (
            session.query(func.count(Listing.id))
            .filter(Listing.website_status == WebsiteStatus.NO_WEBSITE)
            .scalar()
            or 0
        )
        broken = (
            session.query(func.count(Listing.id))
            .filter(
                Listing.website_status.in_([
                    WebsiteStatus.BROKEN,
                    WebsiteStatus.PARKED,
                    WebsiteStatus.PLACEHOLDER,
                    WebsiteStatus.POOR,
                ])
            )
            .scalar()
            or 0
        )

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        sent_today = (
            session.query(func.count(OutreachLog.id))
            .filter(OutreachLog.sent_at >= today_start)
            .scalar()
            or 0
        )
        delivered = (
            session.query(func.count(OutreachLog.id))
            .filter(OutreachLog.status == OutreachStatus.DELIVERED)
            .scalar()
            or 0
        )
        total_sent = session.query(func.count(OutreachLog.id)).scalar() or 0
        replied = (
            session.query(func.count(OutreachLog.id))
            .filter(OutreachLog.status == OutreachStatus.REPLIED)
            .scalar()
            or 0
        )
        opt_outs = session.query(func.count(DoNotContact.id)).scalar() or 0

        delivery_rate = (delivered / total_sent * 100) if total_sent else 0.0
        response_rate = (replied / total_sent * 100) if total_sent else 0.0

        return {
            "total_listings": total,
            "no_website": no_website,
            "no_website_pct": round(no_website / total * 100, 1) if total else 0,
            "broken_website": broken,
            "broken_website_pct": round(broken / total * 100, 1) if total else 0,
            "messages_sent_today": sent_today,
            "delivery_rate": round(delivery_rate, 1),
            "response_rate": round(response_rate, 1),
            "opt_outs": opt_outs,
        }


def get_recent_logs(limit: int = 50) -> list[dict[str, Any]]:
    with get_session() as session:
        logs = (
            session.query(OutreachLog, Listing)
            .outerjoin(Listing, OutreachLog.listing_id == Listing.id)
            .order_by(desc(OutreachLog.sent_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": log.id,
                "channel": log.channel,
                "status": log.status.value if log.status else "unknown",
                "recipient": log.recipient,
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                "business_name": listing.name if listing else "Unknown",
                "county": listing.county if listing else "",
                "error_message": log.error_message,
            }
            for log, listing in logs
        ]


def get_verified_leads_with_email(limit: int = 20) -> list[dict[str, Any]]:
    """Fetch leads that have an email (used for batch test emails)."""
    with get_session() as session:
        rows = (
            session.query(Listing)
            .filter(
                Listing.email.isnot(None),
                Listing.email != "",
            )
            .order_by(desc(Listing.score))
            .limit(limit)
            .all()
        )
        return [_listing_to_dict(r) for r in rows]


def get_leads(
    page: int = 1,
    per_page: int = 50,
    priority: str | None = None,
    has_contact: str | None = None,
    q: str | None = None,
    min_score: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    with get_session() as session:
        query = session.query(Listing)
        if priority:
            query = query.filter(Listing.priority == priority)

        if q:
            qstr = f"%{q}%"
            query = query.filter(
                or_(
                    Listing.name.ilike(qstr),
                    Listing.address.ilike(qstr),
                    Listing.category.ilike(qstr),
                    Listing.county.ilike(qstr),
                    Listing.phone.ilike(qstr),
                    Listing.email.ilike(qstr),
                )
            )

        if min_score is not None:
            try:
                ms = int(min_score)
                query = query.filter(Listing.score >= ms)
            except Exception:
                pass

        if start_date:
            try:
                from datetime import date
                sd = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
                query = query.filter(Listing.created_at >= sd)
            except ValueError:
                pass

        if end_date:
            try:
                from datetime import date
                ed = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                query = query.filter(Listing.created_at <= ed)
            except ValueError:
                pass

        if has_contact is not None:
            val = str(has_contact).strip().lower()
            truthy = {"1", "true", "yes", "y", "has"}
            falsy = {"0", "false", "no", "n", "none", "missing"}
            if val in truthy:
                query = query.filter(
                    or_(
                        and_(Listing.phone.isnot(None), Listing.phone != ""),
                        and_(Listing.email.isnot(None), Listing.email != ""),
                    )
                )
            elif val in falsy:
                query = query.filter(
                    and_(
                        or_(Listing.phone.is_(None), Listing.phone == ""),
                        or_(Listing.email.is_(None), Listing.email == ""),
                    )
                )

        total = query.count()
        rows = (
            query.order_by(desc(Listing.score))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": [_listing_to_dict(r) for r in rows],
        }


def _listing_to_dict(row: Listing | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": row.id,
        "name": row.name,
        "address": row.address,
        "county": row.county,
        "category": row.category,
        "google_maps_url": row.google_maps_url,
        "phone": row.phone,
        "email": row.email,
        "website_url": row.website_url,
        "website_status": row.website_status.value if row.website_status else "no_website",
        "rating": row.rating,
        "review_count": row.review_count,
        "score": row.score,
        "priority": row.priority,
        "phone_verified": row.phone_verified,
        "email_verified": row.email_verified,
        "active_recently": row.active_recently,
        "likely_closed": row.likely_closed,
        "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
