"""Language changes affect presentation, never saved climbing enums or ownership."""

import json
from datetime import date
from pathlib import Path
from string import Formatter

import pytest
import sqlalchemy as sa
from PIL import ImageFont

from harnesssync import db_store, profile_manager
from harnesssync.achievements import achievements, achievement_card
from harnesssync.i18n import LANGUAGES, catalog, translate


def test_catalogs_have_matching_keys_and_placeholders():
    reference = set(catalog("es"))
    for code in LANGUAGES:
        if code == "en":
            continue
        messages = catalog(code)
        assert set(messages) == reference
        for source, target in messages.items():
            fields = lambda text: {name for _, name, _, _ in Formatter().parse(text) if name is not None}
            assert fields(source) == fields(target), (code, source)
            assert target.strip()


@pytest.mark.parametrize("language", LANGUAGES)
def test_cards_are_localized_but_milestone_keys_stay_stable(language):
    history = [{"date": "2026-01-01", "discipline": "Boulder", "grade": "V5", "status": "Flash"}]
    english = achievements(history, date(2026, 1, 2))
    translated = achievements(history, date(2026, 1, 2), language)
    assert [a.key for a in translated] == [a.key for a in english]
    if language != "en":
        assert translated[0].title != english[0].title
    assert achievement_card(translated[0], language).startswith(b"\x89PNG")


def test_bundled_font_has_glyphs_for_translated_card_copy():
    font = ImageFont.truetype("harnesssync/assets/card-font.otf", 24)
    missing = bytes(font.getmask("\U0010FFFF"))
    for code in ("ja", "ko", "zh"):
        for key in ("first send", "log a climb. see your progress.", "climbed on {date}"):
            for character in catalog(code)[key]:
                if character.isspace():
                    continue
                assert bytes(font.getmask(character)) != missing, (code, character)


def test_language_is_saved_per_account_without_changing_climbs(tmp_path):
    db_store.configure(f"sqlite:///{(tmp_path / 'languages.db').as_posix()}")
    try:
        for user in ("alice@example.test", "bob@example.test"):
            profile_manager.save_profile(user, user.split("@")[0])
        profile_manager.log_climb("alice@example.test", "Boulder", "V3", "Sent", "2026-01-01")
        before = profile_manager.get_climbs("alice@example.test")
        profile_manager.set_language("alice@example.test", "ja")
        assert profile_manager.get_profile("alice@example.test")["language"] == "ja"
        assert profile_manager.get_profile("bob@example.test")["language"] == "en"
        assert profile_manager.get_climbs("alice@example.test") == before
        with pytest.raises(ValueError):
            profile_manager.set_language("alice@example.test", "unsupported")
    finally:
        db_store.get_engine().dispose()


def test_legacy_profiles_gain_default_language_without_data_loss(tmp_path):
    url = f"sqlite:///{(tmp_path / 'legacy-language.db').as_posix()}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE profiles (user_id VARCHAR(320) PRIMARY KEY, display_name VARCHAR(40) NOT NULL, show_on_leaderboard BOOLEAN NOT NULL, created_at VARCHAR(32) NOT NULL)")
        conn.exec_driver_sql("INSERT INTO profiles VALUES ('legacy@example.test', 'Legacy', 0, '2026-01-01')")
    engine.dispose()
    db_store.configure(url)
    try:
        profile = profile_manager.get_profile("legacy@example.test")
        assert profile["display_name"] == "Legacy"
        assert profile["language"] == "en"
    finally:
        db_store.get_engine().dispose()


def test_unknown_language_falls_back_and_user_text_is_not_translated():
    assert translate("Save climb", "unknown") == "Save climb"
    assert translate("Hello {name}", "ja", name="Save climb") == "Hello Save climb"


def test_offline_catalog_matches_server_catalogs():
    source = Path("harnesssync/offline_web/locales.js").read_text(encoding="utf-8")
    data = json.loads(source.split("const hsCatalogs = ", 1)[1].rstrip(";\n"))
    for code in LANGUAGES:
        if code != "en":
            assert data[code] == catalog(code)
