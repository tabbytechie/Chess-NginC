"""Explicit transaction boundaries: the unit of work lives in the service layer.

Repositories flush but never commit, so a service function can group several
writes into one atomic unit. Without this, `submit_move` committed the move row
and *then* validated the version — a rejected write left an orphan move behind
and answered 500 instead of 409.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


@contextmanager
def transaction(db: Session) -> Iterator[None]:
    """Commit on a clean exit, roll back on any exception.

    Usage:

        with transaction(db):
            repo.add_move(game, ...)
            if repo.apply_state(...) == 0:
                raise StaleVersionError(...)   # move insert is rolled back too

    A failed flush leaves the session in "pending rollback", and the rollback
    itself re-raises that flush error. The transaction is being discarded
    either way, so cleanup never gets to replace the real cause — a rejected
    move must surface as 409, not as the rollback's own exception.
    """
    try:
        yield
        db.commit()
    except BaseException:
        try:  # noqa: SIM105 - the outer exception must still propagate
            db.rollback()
        except SQLAlchemyError:  # pragma: no cover - cleanup must not mask the cause
            pass
        raise
