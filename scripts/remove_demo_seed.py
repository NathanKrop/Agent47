"""Remove demo seed data while preserving real scraped listings.

Removes the 15 demo businesses from `seed_demo.py`, their fabricated outreach
logs, and the 2 demo Do-Not-Contact entries. Real pipeline-discovered listings
are left untouched.

Usage:
    python -m scripts.remove_demo_seed
"""

import hashlib
import shutil
from pathlib import Path

from database.models import (
    DoNotContact,
    Listing,
    OutreachLog,
    SessionLocal,
    init_db,
)

# Mirror the demo businesses exactly as defined in seed_demo.py
DEMO_BUSINESSES = [
    ("Nairobi Plumbing Services", "Tom Mboya St, Nairobi"),
    ("Mama Njeri Salon", "Kimathi St, Nairobi"),
    ("Grace Medical Clinic", "Moi Ave, Mombasa"),
    ("Sunrise Hardware", "Ngong Rd, Nairobi"),
    ("Kisumu Law Chambers", "Oginga Odinga St, Kisumu"),
    ("Nakuru Electricals", "Kenyatta Ave, Nakuru"),
    ("Safari Events Planner", "Westlands, Nairobi"),
    ("Mombasa Beach Hotel", "Nyali, Mombasa"),
    ("Thika Road Mechanics", "Thika Rd, Nairobi"),
    ("Kisii Pharmacy Plus", "Kisii Town"),
    ("Eldoret Printing Hub", "Uganda Rd, Eldoret"),
    ("Nyeri Real Estate Co", "Nyeri Town"),
    ("Garissa Catering Ltd", "Garissa Town"),
    ("Limuru Tea Restaurant", "Limuru Rd"),
    ("Embu Tailors Fashion", "Embu Town"),
]

# Demo DNC entries from seed_demo.py
DEMO_DNC_CONTACTS = ["+254700000001", "+254700000002"]


def _demo_listing_ids() -> set[str]:
    """Return the deterministic ids for demo businesses (same as seed script)."""
    ids = set()
    for name, address in DEMO_BUSINESSES:
        raw = f"{name.lower()}|{address.lower()}"
        ids.add(hashlib.md5(raw.encode()).hexdigest())
    return ids


def backup_database() -> None:
    """Make a timestamped backup copy of the SQLite DB before mutating it."""
    db_path = Path(__file__).resolve().parent.parent / "kenya_agent.db"
    if db_path.exists():
        backup = db_path.with_name(f"kenya_agent_backup_demoseed_{int(db_path.stat().st_mtime)}.db")
        shutil.copy2(db_path, backup)
        print(f"Backup created: {backup.name}")


def remove_demo_seed() -> None:
    init_db()
    demo_ids = _demo_listing_ids()

    with SessionLocal() as session:
        # Demo listings
        demo_listings = session.query(Listing).filter(Listing.id.in_(demo_ids)).all()
        removed_listings = len(demo_listings)

        # Remove outreach logs linked to demo listings (both demo-fabbed and any real)
        demo_log_listing_ids = {l.id for l in demo_listings}
        removed_logs = 0
        if demo_log_listing_ids:
            removed_logs = (
                session.query(OutreachLog)
                .filter(OutreachLog.listing_id.in_(demo_log_listing_ids))
                .delete(synchronize_session=False)
            )

        # Also remove demo logs that don't link to a listing but match demo recipients
        # (demo seed used random recipients; those are tied to listing ids above).
        for l in demo_listings:
            session.delete(l)

        # Demo DNC entries
        removed_dnc = 0
        for contact in DEMO_DNC_CONTACTS:
            dnc = session.query(DoNotContact).filter_by(contact=contact).first()
            if dnc:
                session.delete(dnc)
                removed_dnc += 1

        session.commit()

        remaining_listings = session.query(Listing).count()
        remaining_logs = session.query(OutreachLog).count()
        remaining_dnc = session.query(DoNotContact).count()

    print(f"Removed demo listings:      {removed_listings}")
    print(f"Removed linked demo logs:   {removed_logs}")
    print(f"Removed demo DNC entries:   {removed_dnc}")
    print("-" * 40)
    print(f"Remaining real listings:    {remaining_listings}")
    print(f"Remaining outreach logs:    {remaining_logs}")
    print(f"Remaining DNC entries:      {remaining_dnc}")


if __name__ == "__main__":
    backup_database()
    remove_demo_seed()

