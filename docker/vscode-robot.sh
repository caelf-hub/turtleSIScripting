#!/bin/sh
# In-container helper for VS Code / Cursor tasks. Reads ports from .env.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
fi
FOLLOWER="${LEROBOT_FOLLOWER_PORT:-/dev/ttyACM0}"
LEADER="${LEROBOT_LEADER_PORT:-/dev/ttyACM1}"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

case "${1:-}" in
  find-follower)
    exec lerobot-find-port --save follower
    ;;
  find-leader)
    exec lerobot-find-port --save leader
    ;;
  calibrate-follower)
    exec lerobot-calibrate --robot.type=so101_follower --robot.port="$FOLLOWER" --robot.id=my_follower
    ;;
  calibrate-leader)
    exec lerobot-calibrate --teleop.type=so101_leader --teleop.port="$LEADER" --teleop.id=my_leader
    ;;
  teleoperate)
    exec lerobot-teleoperate \
      --robot.type=so101_follower --robot.port="$FOLLOWER" --robot.id=my_follower \
      --teleop.type=so101_leader --teleop.port="$LEADER" --teleop.id=my_leader
    ;;
  *)
    echo "Usage: $0 find-follower|find-leader|calibrate-follower|calibrate-leader|teleoperate"
    exit 2
    ;;
esac
