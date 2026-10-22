#!/usr/bin/env python
"""Delete expired sessions (SEC-021).

`authenticate` already lazy-deletes a session when it is next touched, but that
only ever clears a session a client returns for. This sweep removes the rest so
the table cannot grow unbounded. Run it from cron/systemd, e.g. hourly::

    python scripts/prune-sessions.py

Uses the app's own settings, so it points at the same database as the API.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `app` importable when run as `python scripts/prune-sessions.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.service import prune_expired_sessions  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        removed = prune_expired_sessions(db)
    finally:
        db.close()
    print(f"pruned {removed} expired session(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
