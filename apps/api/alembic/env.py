import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401
from alembic import context

# Import Base and all models for autogenerate support.
# Models must be imported (not just Base) so their tables are
# registered on Base.metadata before autogenerate inspects it.
from app.core.database import Base, settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def _database_url() -> str:
    """Resolve the DB URL: env var wins, then app settings, then alembic.ini.

    Production deploys inject ``DATABASE_URL``/``database_url`` (managed Postgres,
    the ``db`` service in compose). Migrations must target *that* database, not
    the hardcoded dev URL in ``alembic.ini`` — otherwise the app and migrations
    would point at different schemas.

    Falling back to ``settings.database_url`` keeps a single source of truth for
    local runs: it honours both the environment and ``apps/api/.env``, so
    ``alembic upgrade head`` can never migrate a different database than the one
    the API is serving (REL-006).
    """
    # Prefer an injected DSN (compose sets lowercase `database_url`; pydantic-settings
    # is case-insensitive so `DATABASE_URL` works too). noqa: honoring the lowercase
    # compose var is intentional (REL-001).
    url = os.environ.get("DATABASE_URL") or os.environ.get("database_url")  # noqa: SIM112
    return url or settings.database_url or config.get_main_option("sqlalchemy.url") or ""


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Honour injected DATABASE_URL/database_url so migrations target the
    # deployed database (REL-006); override the ini's hardcoded dev URL.
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
