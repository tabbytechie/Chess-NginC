#!/usr/bin/env python
"""Recompute PROJECT_CHECKLIST.md counts and verify the Summary matches.

The hand-maintained Summary used to drift (it claimed totals the tables did not
have). This script parses every item row, tallies each status marker, and checks
that the "## Summary" numbers equal what the file actually contains. CI runs it,
so a status flip that forgets to update the Summary fails the build.

Usage::

    python scripts/check-checklist.py            # verify (exit 1 on drift)
    python scripts/check-checklist.py --print    # just print recomputed counts

Only the standard library is used.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHECKLIST = Path(__file__).resolve().parents[1] / "PROJECT_CHECKLIST.md"

# Status markers understood in the "Status" column, in report order.
MARKERS = ("x", " ", "~", "-", "!")
ID_RE = re.compile(r"^\|\s*[A-Z]+-\d+\s*\|")
STATUS_RE = re.compile(r"\|\s*\[([x ~\-!])\]\s*\|")
# Summary bullet: a leading "- **Label**" then the trailing integer on the line.
SUMMARY_RE = re.compile(r"^-\s*\*\*(.+?)\*\*:?\s*(\d+)\s*$")
# Status marker inside a Summary label, e.g. "Implemented & verified (`[x]`)".
LABEL_STATUS_RE = re.compile(r"\[([x ~\-!])\]")


def recount(text: str) -> dict[str, int]:
    counts = {m: 0 for m in MARKERS}
    total = 0
    for line in text.splitlines():
        if not ID_RE.match(line):
            continue
        total += 1
        status = STATUS_RE.search(line)
        if status:
            counts[status.group(1)] += 1
    counts["total"] = total
    return counts


def declared(text: str) -> dict[str, int]:
    """Pull the numbers the Summary claims, keyed the same way as ``recount``."""
    out: dict[str, int] = {}
    in_summary = False
    for line in text.splitlines():
        if line.startswith("## Summary"):
            in_summary = True
            continue
        if in_summary and line.startswith("## "):
            break
        if not in_summary:
            continue
        m = SUMMARY_RE.search(line)
        if not m:
            continue
        label, number = m.group(1), int(m.group(2))
        status = LABEL_STATUS_RE.search(label)
        if "Total items" in label:
            out["total"] = number
        elif status:
            out[status.group(1)] = number
    return out


def main() -> int:
    text = CHECKLIST.read_text()
    actual = recount(text)
    want = declared(text)

    if "--print" in sys.argv:
        print(f"total={actual['total']} " + " ".join(f"[{m}]={actual[m]}" for m in MARKERS))
        return 0

    problems: list[str] = []
    for key, label in [("total", "Total items"), *[(m, f"`[{m}]`") for m in MARKERS]]:
        if key not in want:
            problems.append(f"Summary is missing a count for {label}")
        elif want[key] != actual[key]:
            problems.append(f"{label}: Summary says {want[key]}, file actually has {actual[key]}")

    if problems:
        print("PROJECT_CHECKLIST.md Summary is out of sync:\n  - " + "\n  - ".join(problems))
        print("\nFix it with:  python scripts/check-checklist.py --print")
        return 1

    print(f"checklist counts OK ({actual['total']} items, {actual['x']} verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
