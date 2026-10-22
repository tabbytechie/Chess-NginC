"""Clock helpers, kept in one place so no module reaches for a naive `utcnow`."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Timezone-aware UTC now.

    SQLAlchemy column defaults use this instead of the deprecated, naive
    `datetime.utcnow`; naive timestamps are ambiguous once they leave the
    process and Postgres `timestamptz` columns reject the mismatch anyway.
    """
    return datetime.now(UTC)
