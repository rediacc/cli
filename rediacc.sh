#!/usr/bin/env bash
# Rediacc CLI Linux wrapper
# Executes the consolidated Python CLI with the same arguments.

set -euo pipefail

# Resolve the directory of this script, following symlinks if possible
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"

# Pick python interpreter
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Error: Python not found. Install Python 3 and re-run: ./rediacc.py setup" >&2
  exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/rediacc.py" "$@"
