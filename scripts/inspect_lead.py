#!/usr/bin/env python3
"""Inspect a lead by business name and show recent pipeline/outreach logs.

Usage: python scripts/inspect_lead.py "Shachif Health Unit"
"""
import sys
from pathlib import Path

# Ensure repo root is on sys.path when running this script directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.repository import get_session, get_listing, get_leads
from database.models import Listing, OutreachLog


def find_by_name(session, name):
    q = session.query(Listing).filter(Listing.name.ilike(f"%{name}%"))
    return q.first()


def recent_logs_for_listing(session, listing_id, limit=10):
    return (
        session.query(OutreachLog)
        .filter(OutreachLog.listing_id == listing_id)
        .order_by(OutreachLog.sent_at.desc())
        .limit(limit)
        .all()
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: inspect_lead.py \"Business Name\"")
        sys.exit(1)
    name = sys.argv[1]
    with get_session() as session:
        row = find_by_name(session, name)
        if not row:
            print(f"No listing found matching '{name}'")
            return
        print("--- Listing ---")
        for k, v in row.__dict__.items():
            if k.startswith("_"):
                continue
            print(f"{k}: {v}")

        logs = recent_logs_for_listing(session, row.id, limit=20)
        print("\n--- Recent Outreach Logs ---")
        if not logs:
            print("No outreach logs for this listing")
            return
        for l in logs:
            print(f"{l.sent_at} | {l.channel} | {l.status} | recipient={l.recipient} | error={l.error_message}")


if __name__ == '__main__':
    main()
