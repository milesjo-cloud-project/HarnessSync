"""Static translations; storage values and user-written text never change."""

import json
import re
from functools import lru_cache
from pathlib import Path

LANGUAGES = {"en": "English", "es": "Español", "fr": "Français", "ja": "日本語", "ko": "한국어", "zh": "简体中文"}


@lru_cache(maxsize=6)
def catalog(language):
    if language == "en" or language not in LANGUAGES:
        return {}
    path = Path(__file__).with_name("locales") / f"{language}.json"
    return {key.casefold(): value for key, value in json.loads(path.read_text(encoding="utf-8")).items()}


def translate(message, language="en", **values):
    """Keep decorative prefixes while translating fixed product copy.

    Missing translations fall back to English. Formatting happens *after*
    lookup so user names, notes, dates and route names are never translated.
    """
    prefix, key = re.match(r"^([^A-Za-z]*)(.*)$", message, re.DOTALL).groups()
    translated = catalog(language).get(key.casefold(), key)
    return (prefix + translated).format(**values) if values else prefix + translated
