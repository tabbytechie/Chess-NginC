# Stockfish sidecar — the ONLY image that ships the Stockfish binary.
#
# Kept as its own container so the API image stays binary-free and Stockfish's
# GPL-3.0 never enters it (REL-011 / ADR-006). Reachable only on a private Docker
# network; it has no auth and no DB — network isolation is the access control.
FROM ubuntu:noble

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Stockfish is packaged by Ubuntu (tested against the `stockfish` apt package;
# the version recorded in app/engine/stockfish.py: STOCKFISH_APT_VERSION).
# python3 + venv give the sidecar a pinned dependency environment without the
# system-Python PEP 668 restrictions.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        stockfish \
        python3 \
        python3-venv \
        python3-pip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps into an isolated venv first for layer caching.
COPY requirements.txt ./
RUN python3 -m venv /venv \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt

COPY app.py ./

# Non-root runtime user (no home, no shell) — the sidecar writes nothing.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin engine
USER engine

# Engine path is fixed inside this image; concurrency and search bounds are env-tuned.
ENV STOCKFISH_PATH=/usr/games/stockfish \
    MAX_CONCURRENT_SEARCHES=4 \
    ENGINE_THREADS=1 \
    ENGINE_HASH_MB=64 \
    ACQUIRE_TIMEOUT_S=8

EXPOSE 8050

# Liveness gates `depends_on: service_healthy` in compose: the boot-time UCI
# handshake (uciok) must have succeeded before the API relies on this service.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD ["/venv/bin/python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8050/healthz', timeout=4).status == 200 else 1)"]

CMD ["/venv/bin/python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8050"]
