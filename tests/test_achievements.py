"""Milestones count completed climbs and share only deliberate public copy."""

from datetime import date, timedelta
from io import BytesIO

from PIL import Image

from harnesssync.achievements import achievements, achievement_card


TODAY = date(2026, 10, 25)


def climb(day="2026-10-01", **values):
    return {"date": day, "discipline": "Boulder", "grade": "V3", "status": "Sent", **values}


def test_attempts_invalid_dates_and_future_sends_do_not_unlock_awards():
    assert achievements([
        climb(status="Attempt"), climb(status="Project"),
        climb("bad-date"), climb(None), climb("2099-01-01"),
    ], TODAY) == []


def test_thresholds_use_chronological_dates_and_distinct_climbing_days():
    history = [climb((TODAY - timedelta(days=i)).isoformat(), id=i) for i in range(10)]
    awards = {a.key: a for a in achievements(history, TODAY)}
    assert awards["sends-1"].earned_on == "2026-10-16"
    assert awards["sends-10"].earned_on == "2026-10-25"
    assert awards["days-5"].earned_on == "2026-10-20"
    assert "days-20" not in awards
    assert len([a for a in awards if a.startswith("grade-")]) == 1
    same_day = {a.key for a in achievements([climb()] * 10, TODAY)}
    assert "sends-10" in same_day
    assert "days-5" not in same_day


def test_first_try_styles_grade_scales_and_edits():
    history = [climb(status="Flash"), climb(grade="V5", status="Attempt"),
               climb(discipline="Rope", grade="5.10a", status="Onsight"),
               climb(grade="legacy")]
    keys = {a.key for a in achievements(history, TODAY)}
    assert "first-try-1" in keys
    assert "grade-rope-5.10a" in keys
    assert "grade-boulder-V5" not in keys
    assert "grade-boulder-legacy" not in keys
    assert achievements([], TODAY) == []
    assert "first-try-1" not in {a.key for a in achievements([climb()], TODAY)}


def test_card_is_valid_png_without_private_climb_fields():
    private = climb(user_id="private@example.com", route_name="Secret route", notes="Private beta", location="Hidden gym")
    award = achievements([private], TODAY)[0]
    plain_award = achievements([climb()], TODAY)[0]
    card = achievement_card(award)
    assert card == achievement_card(plain_award)
    with Image.open(BytesIO(card)) as image:
        assert image.format == "PNG"
        assert image.size == (1200, 630)
        image.verify()
