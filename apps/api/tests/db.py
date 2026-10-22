"""Test-database plumbing shared by every fixture in this suite.

Lives in its own module (not `conftest`) so test files that build their own
sessions import the *test* engine instead of `app.core.database.engine`. Using
the app engine here would run `drop_all` against a real developer database.
"""

import os

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

# The suite runs `drop_all` after every test, so it must never point at a
# database anyone else uses. Env wins (CI injects `database_url`), and the
# fallback is a throwaway `chess_test` schema on the local server.
TEST_DB_NAME = "chess_test"
# No explicit role in the fallback: libpq uses the OS user, which is the local
# superuser on a Homebrew/`initdb --user` cluster and avoids baking a developer
# username into tracked source. CI always injects `database_url`.
TEST_DB_URL = (
    os.environ.get("database_url")  # noqa: SIM112 — compose/CI inject lowercase (REL-001)
    or os.environ.get("DATABASE_URL")
    or f"postgresql+psycopg://localhost:5432/{TEST_DB_NAME}"
)

# Databases that must never be wiped by a test run.
_FORBIDDEN_TEST_DATABASES = frozenset(
    {"chess", "chess_engine", "postgres", "template0", "template1"}
)


def _assert_safe_test_database(url: str) -> None:
    """Refuse to run against a developer or maintenance database.

    Raised at import time so collection fails before any table is dropped.
    """
    name = make_url(url).database or ""
    if name in _FORBIDDEN_TEST_DATABASES:
        raise RuntimeError(
            f"Refusing to run tests against database {name!r}: the suite drops and "
            f"recreates every table. Point database_url at a throwaway database "
            f"(for example {TEST_DB_NAME!r}), or unset it to use the local default."
        )


def _ensure_test_database(url: str) -> None:
    """Create the throwaway test database if the server allows it.

    Best-effort: connection failures fall through to `engine` creation below
    and to the first connect, where SQLAlchemy reports the real cause.
    """
    target = make_url(url)
    if (target.database or "") != TEST_DB_NAME:
        return
    admin: URL = target.set(database="postgres")
    try:
        probe = create_engine(admin, isolation_level="AUTOCOMMIT")
    except sqlalchemy.exc.SQLAlchemyError:
        return
    try:
        with probe.connect() as conn:
            exists = conn.execute(
                sqlalchemy.text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DB_NAME},
            ).scalar()
            if not exists:
                conn.exec_driver_sql(f'CREATE DATABASE "{TEST_DB_NAME}"')
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    finally:
        probe.dispose()


_assert_safe_test_database(TEST_DB_URL)
_ensure_test_database(TEST_DB_URL)

engine = create_engine(TEST_DB_URL)
TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def new_session() -> Session:
    """A session bound to the throwaway test database."""
    return TestingSession()


def dispose() -> None:
    """Release every pooled connection.

    Call this before `drop_all` when a test has used sessions that are still in
    a transaction: Postgres cannot drop a table another session holds locks on.
    """
    engine.dispose()
