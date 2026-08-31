"""AI climbing coach powered by the Claude API.

Three surfaces, all built on the same client/context helpers:
  - analyze_session(): one-shot written takeaway right after a session ends
  - stream_chat_reply(): free-form Q&A grounded in the climber's data
  - generate_training_plan(): structured (JSON-schema) multi-week plan
"""

import json
import os

import streamlit as st

try:
    import anthropic
except ImportError:
    anthropic = None

MODEL = "claude-opus-5"

SYSTEM_PROMPT = (
    "You are an expert rock climbing coach and sports scientist embedded in "
    "HarnessSync, a climbing log app. You give practical, safety-conscious "
    "coaching advice grounded in the specific data you're given: logged climbs "
    "(discipline, grade, send status, route/problem name, location) and personal "
    "best grades for bouldering (V-scale) and roped climbing (YDS). Be concise, "
    "encouraging but honest, and call out patterns worth attention (e.g. lots of "
    "falls at one grade suggests it's a good projecting target, or a big jump in "
    "grade suggests checking technique before pushing further). You are not a "
    "substitute for a real coach or doctor for injury concerns."
)

TRAINING_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "weeks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "week_number": {"type": "integer"},
                    "focus": {"type": "string"},
                    "sessions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "day": {"type": "string"},
                                "activity": {"type": "string"},
                                "notes": {"type": "string"},
                            },
                            "required": ["day", "activity", "notes"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["week_number", "focus", "sessions"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "weeks"],
    "additionalProperties": False,
}


def _get_api_key():
    try:
        anthropic_secrets = st.secrets.get("anthropic", {})
    except Exception:
        anthropic_secrets = {}
    key = anthropic_secrets.get("api_key") if anthropic_secrets else None
    return key or os.environ.get("ANTHROPIC_API_KEY")


@st.cache_resource
def _get_client():
    if anthropic is None:
        return None
    api_key = _get_api_key()
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def is_configured() -> bool:
    """Whether the AI coach has everything it needs to make API calls."""
    return _get_client() is not None


def analyze_session(climber_name, discipline, climb_entry, recent_climbs):
    """One-shot written takeaway for a climb that was just logged. Returns None if unconfigured."""
    client = _get_client()
    if client is None:
        return None

    context = {
        "climber_name": climber_name,
        "discipline": discipline,
        "climb_just_logged": climb_entry,
        "recent_climbs_this_discipline": recent_climbs,
    }
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                "Here is a climb that was just logged, plus recent history for the same "
                "discipline, as JSON. Give a short (3-5 sentence) coaching takeaway: what "
                "this climb suggests, what to watch out for, and one concrete suggestion "
                "for next session.\n\n"
                f"{json.dumps(context, indent=2, default=str)}"
            ),
        }],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def stream_chat_reply(history, context):
    """Yields text chunks for a chat turn. `history` is the full [{role, content}, ...] so far."""
    client = _get_client()
    if client is None:
        yield (
            "AI Coach isn't configured yet - add your Anthropic API key under "
            "`[anthropic]` in `.streamlit/secrets.toml` to enable it."
        )
        return

    system = (
        SYSTEM_PROMPT
        + "\n\nClimber context, as JSON (use it to ground your answers, don't just recite it):\n"
        + json.dumps(context, indent=2, default=str)
    )
    with client.messages.stream(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=history,
    ) as stream:
        for text in stream.text_stream:
            yield text


def generate_training_plan(climber_name, climber_profile, weeks=4, goal=""):
    """Structured multi-week training plan. Returns a dict matching TRAINING_PLAN_SCHEMA, or None."""
    client = _get_client()
    if client is None:
        return None

    prompt = (
        f"Build a {weeks}-week climbing training plan for {climber_name}. "
        f"Their stated goal: {goal or 'general strength and endurance improvement'}.\n\n"
        f"Their logged climbing history, as JSON:\n"
        f"{json.dumps(climber_profile, indent=2, default=str)}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": TRAINING_PLAN_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)
