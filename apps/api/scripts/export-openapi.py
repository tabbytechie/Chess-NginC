#!/usr/bin/env python
"""Dump the live OpenAPI document to JSON for frontend codegen (API-022).

The frontend generates its API types from this contract (``openapi-typescript``),
so the JSON is a committed artifact regenerated whenever the backend schemas
change. Run it from the API project, then regenerate the types::

    python scripts/export-openapi.py
    # then, in apps/web: npm run gen:api

Writes to ``apps/api/openapi.json`` by default; pass a path to override. This
only imports the FastAPI app and calls ``app.openapi()`` — it needs no database.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make `app` importable when run as `python scripts/export-openapi.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    document = app.openapi()
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"wrote OpenAPI document to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
