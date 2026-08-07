"""Lead scoring tests."""

from scoring.lead_scorer import LeadScorer


def test_score_max_priority_1():
    scorer = LeadScorer()
    listing = {
        "website_status": "no_website",
        "phone_verified": True,
        "phone": "+254712345678",
        "email_verified": True,
        "email": "info@clinic.co.ke",
        "review_count": 10,
        "category": "clinic",
        "active_recently": True,
    }
    score, tier = scorer.score(listing)
    assert score >= 5
    assert tier == "PRIORITY_1"


def test_skip_good_website():
    scorer = LeadScorer()
    listing = {
        "website_status": "good",
        "phone_verified": True,
        "review_count": 50,
        "category": "clinic",
    }
    score, tier = scorer.score(listing)
    assert score == 0
    assert tier == "SKIP"


def test_broken_website_priority_2():
    scorer = LeadScorer()
    listing = {
        "website_status": "broken",
        "phone_verified": True,
        "phone": "+254712345678",
        "review_count": 0,
        "category": "plumber",
    }
    score, tier = scorer.score(listing)
    assert score >= 2
    assert tier in ("PRIORITY_1", "PRIORITY_2")


def test_skip_likely_closed():
    scorer = LeadScorer()
    listing = {
        "website_status": "no_website",
        "phone_verified": True,
        "likely_closed": True,
    }
    score, tier = scorer.score(listing)
    assert tier == "SKIP"


def test_high_value_category():
    scorer = LeadScorer()
    assert scorer._is_high_value("clinic") is True
    assert scorer._is_high_value("plumber") is False
