#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
if [ -n "${THAI_VOICE_PYTHON:-}" ]; then
  LAUNCHER_PYTHON="$THAI_VOICE_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  LAUNCHER_PYTHON="$(command -v python3)"
elif [ -x "$HOME/miniforge3/bin/python3" ]; then
  LAUNCHER_PYTHON="$HOME/miniforge3/bin/python3"
else
  printf 'Install Python 3.11–3.13 first. See README.md.\n' >&2
  exit 1
fi
exec "$LAUNCHER_PYTHON" scripts/start_server.py
