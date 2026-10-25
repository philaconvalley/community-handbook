"""Checks the handbook for the kinds of drift that are easy to miss in review.

Errors (fail the check):
  - internal links to files or headings that don't exist
  - retired names and phrases listed in .github/retired-terms.txt
  - placeholders like [ADDRESS NEEDED] that still need real content

Warnings (reported, never fail the check):
  - documents whose Last Reviewed date is more than four months old

Run from the repository root: python3 .github/scripts/check_handbook.py
"""

import datetime
import os
import re
import sys
from pathlib import Path

STALE_AFTER_DAYS = 120
PLACEHOLDER = re.compile(r"\[[A-Z][A-Z ]* NEEDED\]")
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.M)
INLINE_CODE = re.compile(r"`[^`]*`")
LAST_REVIEWED = re.compile(r"\*\*Last Reviewed:\*\*\s*(\d{4}-\d{2}-\d{2})")
IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"

errors = 0


def report(level, path, line, message):
    global errors
    if level == "error":
        errors += 1
    if IN_ACTIONS:
        print(f"::{level} file={path},line={line}::{message}")
    else:
        print(f"{level.upper()}: {path}:{line}: {message}")


def slug(heading):
    """GitHub's anchor for a heading."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def anchors(path, cache={}):
    if path not in cache:
        cache[path] = {slug(h) for h in HEADING.findall(path.read_text())}
    return cache[path]


def load_retired_terms():
    terms = []
    for raw in Path(".github/retired-terms.txt").read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        pattern, _, hint = raw.partition(" | ")
        terms.append((re.compile(pattern.strip(), re.I), hint.strip()))
    return terms


def check(path, retired_terms, today):
    text = path.read_text()
    is_changelog = path.name == "CHANGELOG.md"

    for number, line in enumerate(text.splitlines(), start=1):
        for target in LINK.findall(line):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file_part, _, fragment = target.partition("#")
            linked = (path.parent / file_part).resolve() if file_part else path.resolve()
            if not linked.exists():
                report("error", path, number, f"Link points to a file that doesn't exist: {target}")
            elif fragment and linked.suffix == ".md" and fragment not in anchors(linked):
                report("error", path, number, f"Link points to a heading that doesn't exist: {target}")

        if not is_changelog:
            prose = INLINE_CODE.sub("", line)
            for pattern, hint in retired_terms:
                for match in pattern.finditer(prose):
                    report("error", path, number, f'"{match.group(0)}" is a retired term. Use {hint}.')

        for match in PLACEHOLDER.finditer(line):
            report("error", path, number, f"{match.group(0)} still needs to be filled in.")

        reviewed = LAST_REVIEWED.search(line)
        if reviewed:
            age = (today - datetime.date.fromisoformat(reviewed.group(1))).days
            if age > STALE_AFTER_DAYS:
                report("warning", path, number,
                       f"Last reviewed {age} days ago. It's due for the quarterly fact-check.")


def main():
    retired_terms = load_retired_terms()
    today = datetime.date.today()
    files = sorted(p for p in Path(".").rglob("*.md") if ".git" not in p.parts)
    for path in files:
        check(path, retired_terms, today)
    print(f"Checked {len(files)} documents: {errors} error(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
