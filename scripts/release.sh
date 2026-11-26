#!/usr/bin/env bash
# One-shot local release: bump the version (via bump-version.sh), run the
# test suite, commit the stamped files (pyproject.toml,
# src/aneup/__init__.py, uv.lock, CHANGELOG.md) with a conventional
# message, and create the annotated vX.Y.Z tag. Never pushes: review the
# printed next steps, then push the branch and the tag yourself (pushing
# the tag triggers the release workflow, which re-runs the gates and
# publishes to PyPI via Trusted Publishing).
#
# Refuses to run when tracked files other than the stamped four have
# pending changes, and restores the stamped files if post-bump validation
# or the tests fail, so a failed run leaves the tree exactly as it started.
set -euo pipefail

bump=${1:-}
exact=${2:-}

cd "$(git rev-parse --show-toplevel)"

# Fail fast on unrelated tracked changes: the release commit must contain
# exactly the stamped four files.
dirty=$(git status --porcelain --untracked-files=no | awk '
  { path = substr($0, 4) }
  path != "pyproject.toml" && path != "src/aneup/__init__.py" && path != "uv.lock" && path != "CHANGELOG.md" { print path }
')
if [[ -n "$dirty" ]]; then
  printf 'Refusing to cut a release with unrelated tracked changes:\n%s\n\nCommit or stash them first, then rerun.\n' "$dirty" >&2
  exit 1
fi

# Snapshot the stamped files so a post-bump failure restores the tree.
snap=$(mktemp -d)
cleanup() { rm -rf "$snap"; }
trap cleanup EXIT
cp pyproject.toml src/aneup/__init__.py uv.lock CHANGELOG.md "$snap"/ 2>/dev/null || cp pyproject.toml src/aneup/__init__.py uv.lock "$snap"/

restore() {
  cp "$snap"/pyproject.toml pyproject.toml
  cp "$snap"/__init__.py src/aneup/__init__.py
  cp "$snap"/uv.lock uv.lock
  [[ -f "$snap/CHANGELOG.md" ]] && cp "$snap/CHANGELOG.md" CHANGELOG.md
  printf 'Restored stamped files; nothing was committed or tagged.\n' >&2
}

bash scripts/bump-version.sh "$bump" "$exact"

version=$(sed -n 's/^[ \t]*version[ \t]*= *"\([0-9][0-9.]*\)".*/\1/p' pyproject.toml | head -1)
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  printf 'Could not read a stable x.y.z version from pyproject.toml.\n' >&2
  restore
  exit 1
fi
mirrored=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/aneup/__init__.py | head -1)
if [[ "$mirrored" != "$version" ]]; then
  printf 'pyproject version %s does not match __version__ %s.\n' "$version" "$mirrored" >&2
  restore
  exit 1
fi
tag="v$version"

if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
  printf 'Tag %s already exists.\n' "$tag" >&2
  restore
  exit 1
fi

# Local gate: the same suite CI runs. Env override for the virtualenv is
# honoured (see Makefile); uv run creates a project env when missing.
if [[ "${SKIP_TESTS:-0}" != "1" ]]; then
  if ! uv run --group test pytest -q; then
    printf 'Tests failed.\n' >&2
    restore
    exit 1
  fi
fi

branch=$(git branch --show-current)

printf 'Release stamp:\n'
git diff --stat -- pyproject.toml src/aneup/__init__.py uv.lock CHANGELOG.md

git add pyproject.toml src/aneup/__init__.py uv.lock CHANGELOG.md
if ! git commit -m "chore(release): release $tag"; then
  printf 'Commit failed (hook rejection?). ' >&2
  restore
  exit 1
fi

if ! git tag -a "$tag" -m "aneup $tag"; then
  printf 'Tag %s was not created; the release commit exists. To start over:\n  git reset --soft HEAD~1\nthen rerun this script after removing any partial tag.\n' "$tag" >&2
  exit 1
fi

printf '\nReleased %s on %s (commit + annotated tag created; nothing pushed).\n\nNext steps:\n  git push origin %s %s   # tag push triggers the release workflow (test gates -> PyPI publish)\n\nUndo before pushing:\n  git reset --soft HEAD~1 && git tag -d %s\n' \
  "$tag" "${branch:-detached-head}" "${branch:-HEAD}" "$tag" "$tag"
