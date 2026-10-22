# Chess Engine API — production image (REL-001/REL-010).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/api

# Install runtime deps first for layer caching.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

# Migrations ship with the image; applied by a separate one-shot `migrate`
# service in compose so serving and migrating are distinct steps (REL-006).
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Unprivileged runtime user. The app writes nothing to disk at serve time, so
# it needs no writable paths beyond the read-only package (Phase 5 hardening).
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin apiuser \
    && chown -R apiuser:apiuser /srv/api
USER apiuser

EXPOSE 8000

# Serve only. `--proxy-headers` with a trusted proxy range makes uvicorn rewrite
# the client address from X-Forwarded-For, so rate limiting keys on the real
# client behind nginx rather than the shared proxy IP (SEC-012).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS:-172.16.0.0/12}\""]
