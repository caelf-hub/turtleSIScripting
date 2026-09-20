#!/usr/bin/env bash
# One command: check Docker + USB, then start LeRobot.
#   bash docker/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/src/lerobot/scripts/lerobot_setup_container.py"

echo "LeRobot setup"
echo "This script checks Docker and your robot USB cables."
echo

if [[ ! -f "$SCRIPT" ]]; then
  echo "Could not find $SCRIPT"
  echo "Run this from the lerobot repo (the folder that contains src/ and docker/)."
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT" "$@"
fi
if command -v python >/dev/null 2>&1; then
  exec python "$SCRIPT" "$@"
fi

cat <<'EOF'
Python 3 is not installed (or not on PATH).

Linux (Debian/Ubuntu):  sudo apt install python3
macOS (Homebrew):       brew install python
Then run:               bash docker/setup.sh
EOF
exit 1
