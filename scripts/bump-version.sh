#!/usr/bin/env bash
# Bump the [project] version in pyproject.toml, mirror it into
# src/aneup/__init__.py, refresh uv.lock, and stamp CHANGELOG.md: the
# [Unreleased] section becomes [x.y.z] - <today> and a fresh [Unreleased]
# section is inserted above it. Never commits or tags.
#
# Failure behavior: if the uv.lock refresh or version mirroring fails, the
# stamped files are restored and the script exits non-zero — nothing is left
# half-bumped. Rerun with VERSION=<target> to retry the same version.
set -euo pipefail

bump=${1:-}
exact=${2:-}
if [[ -n "$bump" && -n "$exact" ]]; then
  echo 'Choose BUMP or VERSION, not both.' >&2
  exit 1
fi
choice=${exact:-${bump:-patch}}
case "$choice" in
  major|minor|patch) ;;
  *) [[ "$choice" =~ ^(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})$ ]] || { echo 'Expected major, minor, patch, or stable x.y.z.' >&2; exit 1; } ;;
esac

cd "$(git rev-parse --show-toplevel)"

tmp_pp=$(mktemp ./pyproject.toml.bump.XXXXXX)
tmp_init=$(mktemp ./src/aneup/__init__.py.bump.XXXXXX)
tmp_backup=$(mktemp ./pyproject.toml.orig.XXXXXX)
tmp_stamp=""
cleanup() { rm -f "$tmp_pp" "$tmp_init" "$tmp_backup" "$tmp_stamp"; }
trap cleanup EXIT

awk -v choice="$choice" '
  /^[ \t]*\[/ {
    project=($0 ~ /^[ \t]*\[project\][ \t]*(#.*)?$/)
    if (project) projects++
  }
  project && /^[ \t]*version[ \t]*=/ {
    versions++
    if ($0 !~ /^[ \t]*version[ \t]*=[ \t]*"[0-9]+\.[0-9]+\.[0-9]+"[ \t]*(#.*)?$/) { bad=1; next }
    old=$0; sub(/^[^"]*"/,"",old); sub(/".*$/,"",old)
    split(old,v,".")
    if (choice=="major") nextversion=(v[1]+1) ".0.0"
    else if (choice=="minor") nextversion=v[1] "." (v[2]+1) ".0"
    else if (choice=="patch") nextversion=v[1] "." v[2] "." (v[3]+1)
    else nextversion=choice
    sub(/"[0-9]+\.[0-9]+\.[0-9]+"/,"\"" nextversion "\"")
  }
  { print }
  END {
    if (projects!=1 || versions!=1 || bad) {
      print "Expected exactly one literal stable [project] version." > "/dev/stderr"
      exit 1
    }
  }
' pyproject.toml > "$tmp_pp"
chmod 644 "$tmp_pp"

new_version=$(sed -n 's/^[ \t]*version[ \t]*=[ \t]*"\([0-9][0-9.]*\)".*/\1/p' "$tmp_pp" | head -1)

# Mirror the version into the package (__version__), then refresh uv.lock.
# Any failure restores both stamped files: nothing is left half-bumped, and
# a rerun with VERSION=<target> retries the exact same version.
cp pyproject.toml "$tmp_backup"
mv "$tmp_pp" pyproject.toml
if ! sed -E -i.bump.bak "s/^__version__ = \"[0-9]+\\.[0-9]+\\.[0-9]+\"/__version__ = \"$new_version\"/" src/aneup/__init__.py; then
  mv "$tmp_backup" pyproject.toml
  rm -f src/aneup/__init__.py.bump.bak
  echo "Could not mirror the version into src/aneup/__init__.py; pyproject.toml restored." >&2
  exit 1
fi
rm -f src/aneup/__init__.py.bump.bak
mirrored=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/aneup/__init__.py | head -1)
if [[ "$mirrored" != "$new_version" ]]; then
  mv "$tmp_backup" pyproject.toml
  sed -E -i.bump.bak "s/^__version__ = \"[0-9]+\\.[0-9]+\\.[0-9]+\"/__version__ = \"$mirrored\"/" src/aneup/__init__.py
  rm -f src/aneup/__init__.py.bump.bak
  echo "Version mirroring mismatch; both files restored." >&2
  exit 1
fi
if ! uv lock >/dev/null 2>&1; then
  mv "$tmp_backup" pyproject.toml
  sed -i.bump.bak "s/^__version__ = \"[0-9]+\.[0-9]+\.[0-9]+\"/__version__ = \"$mirrored\"/" src/aneup/__init__.py
  rm -f src/aneup/__init__.py.bump.bak
  tmp_backup=""
  echo "uv lock refresh failed; pyproject.toml and __init__.py restored. Fix the cause, then rerun with VERSION=$new_version." >&2
  exit 1
fi
rm -f "$tmp_backup"
tmp_backup=""

stamp_changelog() {
  local cl=CHANGELOG.md today
  today=$(date +%Y-%m-%d)
  if [[ ! -f "$cl" ]]; then
    printf '# Changelog\n\nAll notable changes to this project will be documented in this file.\n\nThe format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)\n\n## [Unreleased]\n\n## [%s] - %s\n\n### Changed\n* Bumped version to %s\n' "$new_version" "$today" "$new_version" > "$cl"
    chmod 644 "$cl"
    return
  fi
  # Already stamped for this version (e.g. retry after a partial run): skip.
  if grep -q "^## \[$new_version\] - " "$cl"; then
    return
  fi
  if grep -q '^## \[Unreleased\]' "$cl"; then
    tmp_stamp=$(mktemp "$cl.stamp.XXXXXX")
    awk -v ver="$new_version" -v today="$today" '
      /^## \[Unreleased\]/ && !done {
        print "## [Unreleased]"; print ""; print "## [" ver "] - " today; print "";
        done=1; next
      }
      { print }
    ' "$cl" > "$tmp_stamp"
    chmod 644 "$tmp_stamp"
    mv "$tmp_stamp" "$cl"
    tmp_stamp=""
  else
    tmp_stamp=$(mktemp "$cl.stamp.XXXXXX")
    awk -v ver="$new_version" -v today="$today" '
      !inserted && /^## / {
        print "## [Unreleased]"; print ""; print "## [" ver "] - " today; print "";
        inserted=1
      }
      { print }
      END { if (!inserted) { print ""; print "## [Unreleased]"; print ""; print "## [" ver "] - " today; print "" } }
    ' "$cl" > "$tmp_stamp"
    chmod 644 "$tmp_stamp"
    mv "$tmp_stamp" "$cl"
    tmp_stamp=""
  fi
  # A release section must not be empty: if the freshly stamped section has no
  # bullet points, record the bump itself.
  if ! awk -v ver="$new_version" '
    index($0, "## [" ver "] - ") == 1 { insec = 1; next }
    insec && /^## / { insec = 0 }
    insec && /^[*] / { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$cl"; then
    tmp_note=$(mktemp "$cl.note.XXXXXX")
    awk -v ver="$new_version" '
      index($0, "## [" ver "] - ") == 1 {
        print; print ""; print "### Changed"; print "* Bumped version to " ver; print "";
        next
      }
      { print }
    ' "$cl" > "$tmp_note"
    chmod 644 "$tmp_note"
    mv "$tmp_note" "$cl"
    tmp_note=""
  fi
}

stamp_changelog

printf '%s\n' "Version bumped to $new_version; inspect pyproject.toml, src/aneup/__init__.py, uv.lock and CHANGELOG.md before committing."
