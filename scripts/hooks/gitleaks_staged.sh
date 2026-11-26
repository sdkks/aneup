#!/bin/sh
# Pre-commit gate: staged content must be free of secrets/PII (gitleaks,
# when installed) and internal tracker identifiers (always checked).
# Degrades to a notice when gitleaks is absent. Excludes the hooks dir:
# these scripts contain the tracker pattern by necessity.
cd "$(git rev-parse --show-toplevel)" || exit 1

pattern='(EPIC|STORY|TASK|BUG)-[0-9]+'
leaks=$(git diff --cached --unified=0 -- . ':(exclude).githooks/**' ':(exclude)scripts/hooks/**' \
  | grep -E '^\+' | grep -Ev '^\+\+\+' | grep -inE "$pattern" || true)
if [ -n "$leaks" ]; then
  printf '%s\n' 'FAIL: staged content contains internal tracker identifiers:' \
    "$leaks" \
    'Describe the change by its content, not by its ticket.' >&2
  exit 1
fi

if command -v gitleaks >/dev/null 2>&1; then
  out=$(gitleaks git --pre-commit --staged --redact --verbose 2>&1)
  status=$?
  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$out" >&2
    echo "pre-commit: gitleaks flagged staged content — remove the secret/PII, add an inline 'gitleaks:allow' comment on the offending line, or unstage the change." >&2
    exit "$status"
  fi
else
  echo "note: gitleaks not installed; skipping secret scan (brew install gitleaks)" >&2
fi
exit 0
