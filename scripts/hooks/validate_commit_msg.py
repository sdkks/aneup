#!/usr/bin/env python3
"""Validate a commit message: Conventional Commits style, no tracker IDs.

Usage: validate_commit_msg.py <commit-msg-file>

Rules:
- First line must be `type(scope)?: description`, 72 characters max.
- Allowed types: feat fix docs style refactor perf test build ci chore revert.
- Git-generated lines (Merge ..., Revert "...") pass through.
- Internal tracker identifiers (EPIC-123, TASK-42, ...) must never appear
  in the message: describe the change by its content, not its ticket.
"""

import re
import sys
from pathlib import Path

TYPES = "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
LINE = re.compile(rf"^({TYPES})(\([a-z0-9][a-z0-9._-]*\))?(!)?: (.{{1,72}})$")
TRACKER = re.compile(r"\b(?:EPIC|STORY|TASK|BUG)-[0-9]+\b", re.IGNORECASE)


def main(argv):
    if len(argv) != 2:
        print("usage: validate_commit_msg.py <commit-msg-file>", file=sys.stderr)
        return 1
    msg_file = Path(argv[1])
    if not msg_file.is_file():
        print(f"commit message file not found: {msg_file}", file=sys.stderr)
        return 1

    lines = msg_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        print("FAIL: empty commit message", file=sys.stderr)
        return 1
    first = lines[0]

    if first.startswith("Merge ") or re.match(r'^Revert ".+"$', first):
        return 0

    if not LINE.match(first):
        print(
            "FAIL: expected type(scope)!: description (1-72 characters).\n"
            "Types: feat fix docs style refactor perf test build ci chore revert",
            file=sys.stderr,
        )
        return 1

    leak = TRACKER.search("\n".join(lines))
    if leak:
        print(
            f"FAIL: commit message contains a tracker identifier ({leak.group(0)}).\n"
            "Describe the change by its content, not its ticket.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
