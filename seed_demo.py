"""Seed demo data so the dashboard is populated on first view."""
import random
from datetime import datetime, timedelta, timezone

from database.models import DoNotContact, Listing, OutreachLog, OutreachStatus, SessionLocal, WebsiteStatus, init_db

BUSINESSES = [
    ("Nairobi Plumbing Services", "Tom Mboya St, Nairobi", "Nairobi", "plumber", None, "broken"),
    ("Mama Njeri Salon", "Kimathi St, Nairobi", "Nairobi", "salon", None, "no_website"),
    ("Grace Medical Clinic", "Moi Ave, Mombasa", "Mombasa", "clinic", "https://graceclinic.co.ke", "poor"),
    ("Sunrise Hardware", "Ngong Rd, Nairobi", "Nairobi", "hardware store", None, "no_website"),
    ("Kisumu Law Chambers", "Oginga Odinga St, Kisumu", "Kisumu", "law firm", None, "no_website"),
    ("Nakuru Electricals", "Kenyatta Ave, Nakuru", "Nakuru", "electrician", "http://nakuruelectric.co.ke", "broken"),
    ("Safari Events Planner", "Westlands, Nairobi", "Nairobi", "event planner", None, "no_website"),
    ("Mombasa Beach Hotel", "Nyali, Mombasa", "Mombasa", "hotel", "http://mombasa-hotel.com", "parked"),
    ("Thika Road Mechanics", "Thika Rd, Nairobi", "Nairobi", "mechanic", None, "no_website"),
    ("Kisii Pharmacy Plus", "Kisii Town", "Kisii", "pharmacy", None, "no_website"),
    ("Eldoret Printing Hub", "Uganda Rd, Eldoret", "Uasin Gishu", "printing shop", None, "no_website"),
    ("Nyeri Real Estate Co", "Nyeri Town", "Nyeri", "real estate agent", "https://nyerirealty.co.ke", "poor"),
    ("Garissa Catering Ltd", "Garissa Town", "Garissa", "catering", None, "no_website"),
    ("Limuru Tea Restaurant", "Limuru Rd", "Kiambu", "restaurant", None, "no_website"),
    ("Embu Tailors Fashion", "Embu Town", "Embu", "tailor", None, "no_website"),
]

CHANNELS = ["whatsapp", "sms", "email"]
STATUSES = ["sent", "sent", "sent", "delivered", "delivered", "failed"]


def seed():
    init_db()
    with SessionLocal() as session:
        if session.query(Listing).count() > 0:
            print("Demo data already seeded — skipping.")
            return

        import hashlib
        for i, (name, address, county, category, website_url, ws_str) in enumerate(BUSINESSES):
            lid = hashlib.md5(f"{name.lower()}|{address.lower()}".encode()).hexdigest()
            ws = WebsiteStatus(ws_str)
            score_map = {"no_website": 5, "broken": 4, "parked": 3, "poor": 2, "good": 0}
            score = score_map.get(ws_str, 1)
            priority = "PRIORITY_1" if score >= 4 else "PRIORITY_2" if score >= 2 else "PRIORITY_3"
            listing = Listing(
                id=lid, name=name, address=address, county=county, category=category,
                phone=f"+2547{random.randint(10000000, 99999999)}",
                email=f"info@{name.lower().replace(' ', '')}.co.ke" if i % 3 == 0 else None,
                website_url=website_url, website_status=ws,
                rating=round(random.uniform(3.0, 5.0), 1),
                review_count=random.randint(2, 120),
                score=score, priority=priority,
                phone_verified=True, email_verified=i % 3 == 0,
                active_recently=True, likely_closed=False,
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 14)),
                last_checked_at=datetime.now(timezone.utc),
            )
            session.add(listing)

            # Add 1-2 outreach log entries per listing
            for _ in range(random.randint(1, 2)):
                channel = random.choice(CHANNELS)
                status_str = random.choice(STATUSES)
                log = OutreachLog(
                    listing_id=lid,
                    channel=channel,
                    template_name="no_website_primary" if ws_str == "no_website" else "broken_website_primary",
                    recipient=f"+2547{random.randint(10000000, 99999999)}",
                    status=OutreachStatus(status_str),
                    sent_at=datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 480)),
                )
                session.add(log)

        # Add 2 DNC entries
        session.add(DoNotContact(contact="+254700000001", reason="opt_out", added_at=datetime.now(timezone.utc)))
        session.add(DoNotContact(contact="+254700000002", reason="opt_out", added_at=datetime.now(timezone.utc)))

        session.commit()
        print(f"Seeded {len(BUSINESSES)} listings + outreach logs + 2 DNC entries.")


if __name__ == "__main__":
    seed()
