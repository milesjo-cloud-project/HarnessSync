"""Gym wall reports: owner-only, opt-in only, and anonymous at every level."""

from datetime import date
from unittest import mock

import pytest

from harnesssync import db_store, gym_report, profile_manager

OWNER = "owner@example.com"
CLIMBERS = [f"climber{i}@example.test" for i in range(1, 5)]


@pytest.fixture(autouse=True)
def database(tmp_path):
    db_store.configure(f"sqlite:///{(tmp_path / 'gyms.db').as_posix()}")
    with mock.patch("harnesssync.support_config.settings", return_value={"owner_emails": [OWNER]}):
        yield
    db_store.get_engine().dispose()


def _gym(name="Basalt Bouldering"):
    return gym_report.add_gym(OWNER, name)


def _climber(user, slug, joined=date(2026, 10, 1)):
    profile_manager.save_profile(user, user.split("@")[0].title())
    gym_report.join_gym(user, slug, joined)


def test_only_the_owner_can_add_gyms_or_build_reports():
    slug = _gym()
    with pytest.raises(PermissionError):
        gym_report.add_gym(CLIMBERS[0], "Another Gym")
    with pytest.raises(PermissionError):
        gym_report.owner_report(CLIMBERS[0], slug, 2026, 10)
    with pytest.raises(ValueError):
        gym_report.add_gym(OWNER, "basalt   bouldering")  # same slug
    assert [g["name"] for g in gym_report.list_gyms()] == ["Basalt Bouldering"]


def test_report_is_withheld_below_three_climbers():
    slug = _gym()
    for user in CLIMBERS[:2]:
        _climber(user, slug)
        profile_manager.log_climb(user, "Boulder", "V3", "Sent", "2026-10-05")
    report = gym_report.owner_report(OWNER, slug, 2026, 10)
    assert report["withheld"] and report["climbers"] == 2
    assert "logged" not in report and "disciplines" not in report
    assert "V3" not in gym_report.render_text(report)
    assert "V3" not in gym_report.render_html(report)


def test_counts_only_opted_in_gym_climbs_inside_the_month_after_joining():
    slug = _gym()
    for user in CLIMBERS[:3]:
        _climber(user, slug)
        profile_manager.log_climb(user, "Boulder", "V3", "Sent", "2026-10-06")     # Tuesday
        profile_manager.log_climb(user, "Boulder", "V4", "Attempt", "2026-10-06")
    late = CLIMBERS[2]
    gym_report.join_gym(late, slug, date(2026, 10, 1))  # no-op, already a member
    # None of these may count:
    profile_manager.log_climb(CLIMBERS[0], "Boulder", "V5", "Sent", "2026-10-07", environment="Outdoor")
    profile_manager.log_climb(CLIMBERS[0], "Boulder", "V5", "Sent", "2026-09-30")
    profile_manager.log_climb(CLIMBERS[0], "Boulder", "V5", "Sent", "2026-11-01")
    profile_manager.save_profile(CLIMBERS[3], "Not shared")
    profile_manager.log_climb(CLIMBERS[3], "Boulder", "V5", "Sent", "2026-10-07")  # never joined

    report = gym_report.owner_report(OWNER, slug, 2026, 10)
    assert not report["withheld"]
    assert (report["climbers"], report["members"], report["logged"], report["sends"]) == (3, 3, 6, 3)
    assert report["send_rate"] == 50
    assert report["busiest_day"] == "Tue"
    boulder = report["disciplines"][0]
    assert boulder["most_tried"] == "V4"
    assert [g["grade"] for g in boulder["grades"]] == ["V3", "V4"]


def test_climbs_before_a_climber_joined_never_count():
    slug = _gym()
    for user in CLIMBERS[:3]:
        _climber(user, slug, joined=date(2026, 10, 15))
        profile_manager.log_climb(user, "Boulder", "V2", "Sent", "2026-10-14")
        profile_manager.log_climb(user, "Boulder", "V2", "Sent", "2026-10-15")
    report = gym_report.owner_report(OWNER, slug, 2026, 10)
    assert report["logged"] == 3


def test_grades_with_few_climbers_are_grouped_so_no_one_stands_out():
    slug = _gym()
    for user in CLIMBERS[:3]:
        _climber(user, slug)
        profile_manager.log_climb(user, "Boulder", "V2", "Flash", "2026-10-10")
    profile_manager.log_climb(CLIMBERS[0], "Boulder", "V9", "Sent", "2026-10-11")
    profile_manager.log_climb(CLIMBERS[0], "Rope", "5.12a", "Redpoint", "2026-10-11")
    report = gym_report.owner_report(OWNER, slug, 2026, 10)
    boulder, rope = report["disciplines"]
    assert [g["grade"] for g in boulder["grades"]] == ["V2", gym_report.OTHER_GRADES]
    assert rope["grades"] == [{"grade": gym_report.OTHER_GRADES, "logged": 1, "sends": 1, "tries": 0}]
    assert rope["most_logged"] is None
    text = gym_report.render_text(report) + gym_report.render_html(report)
    assert "V9" not in text and "5.12a" not in text


def test_reports_contain_no_names_emails_routes_or_notes():
    slug = _gym()
    for user in CLIMBERS[:3]:
        _climber(user, slug)
        profile_manager.log_climb(user, "Boulder", "V3", "Sent", "2026-10-06",
                                  route_name="Secret Arete", location="Back cave", notes="my knee hurt")
    report = gym_report.owner_report(OWNER, slug, 2026, 10)
    outputs = [str(report), gym_report.render_text(report), gym_report.render_html(report)]
    for output in outputs:
        for private in ("climber1", "Climber1", "example.test", "Secret Arete", "Back cave", "knee"):
            assert private not in output


def test_gym_name_is_escaped_in_the_report_page():
    slug = gym_report.add_gym(OWNER, "<b>Rock & Roll</b> Gym")
    page = gym_report.render_html(gym_report.owner_report(OWNER, slug, 2026, 10))
    assert "<b>Rock" not in page and "&lt;b&gt;Rock &amp; Roll" in page


def test_switching_leaving_and_deleting_the_account_end_the_opt_in():
    first, second = _gym("First Gym"), _gym("Second Gym")
    user = CLIMBERS[0]
    _climber(user, first, joined=date(2026, 10, 1))
    gym_report.join_gym(user, second, date(2026, 10, 20))
    assert gym_report.get_membership(user) == {"user_id": user, "gym_slug": second, "joined_on": "2026-10-20"}
    gym_report.leave_gym(user)
    assert gym_report.get_membership(user) is None
    gym_report.join_gym(user, first, date(2026, 10, 21))
    profile_manager.delete_account(user)
    assert gym_report.get_membership(user) is None
    with pytest.raises(ValueError):
        gym_report.join_gym(user, "no-such-gym", date(2026, 10, 21))


def test_previous_month_wraps_the_year():
    assert gym_report.previous_month(date(2027, 1, 9)) == (2026, 12)
    assert gym_report.previous_month(date(2026, 11, 14)) == (2026, 10)
