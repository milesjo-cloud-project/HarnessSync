"""Shared atomic-write JSON storage helpers.

Both profile_manager.py and feedback_manager.py persist one shared JSON file
to disk and need the same guarantees: a write interrupted partway through
can't corrupt the file, and concurrent Streamlit sessions (each running the
script in its own thread) can't interleave a read-modify-write and silently
drop each other's data. This module is the one place those guarantees live,
so both callers stay in lockstep instead of maintaining separate copies.
"""

import os
import json
import tempfile

FILE_ENCODING = "utf-8"


def ensure_file(dir_path, file_path, default):
    """Creates `dir_path` and seeds `file_path` with `default` if either is missing."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding=FILE_ENCODING) as f:
            json.dump(default, f)


def write_atomically(dir_path, file_path, data):
    """Write via a temp file + os.replace so an interrupted save can't leave a
    half-written (and therefore unparseable) file behind."""
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=FILE_ENCODING) as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, file_path)  # atomic on Windows and POSIX
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load(dir_path, file_path, default, expected_type):
    """Reads `file_path`, seeding it via `ensure_file` first. Returns
    `default` for a missing/truncated/wrong-shaped file rather than raising -
    a hand-edited or corrupted data file shouldn't crash the whole dashboard
    on import, it should just look like "nothing saved yet"."""
    ensure_file(dir_path, file_path, default)
    try:
        with open(file_path, "r", encoding=FILE_ENCODING) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return default
    return data if isinstance(data, expected_type) else default
