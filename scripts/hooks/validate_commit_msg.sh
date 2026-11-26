#!/bin/sh
# Commit-message validator wrapper: uses the system Python so pyenv
# shims cannot interfere with the project interpreter.
HERE="$(cd "$(dirname "$0")" && pwd)"
exec /usr/bin/python3 "$HERE/validate_commit_msg.py" "$@"
