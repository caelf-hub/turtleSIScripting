#!/bin/sh
# Printed when the Dev Container starts. Safe to run by hand: sh docker/container-welcome.sh
echo
echo "======== LeRobot container ========"
echo "Serial devices this container can see:"
if ls /dev/ttyACM* /dev/ttyUSB* >/dev/null 2>&1; then
  ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
else
  echo "  none yet"
  echo
  echo "Fix (on the HOST, not in this terminal):"
  echo "  1. Terminal → Run Task → Reattach robot USB to Docker"
  echo "  2. Command Palette → Dev Containers: Rebuild Container"
fi
echo
echo "Do these in order (unplug only when the command asks):"
echo "  1. lerobot-find-port --save follower"
echo "  2. lerobot-find-port --save leader"
echo "  3. Terminal → Run Task → Calibrate follower"
echo "  4. Terminal → Run Task → Calibrate leader"
echo "  5. Terminal → Run Task → Teleoperate"
echo
echo "Docker has no robot GUI. Leave --display_data off."
echo "Host USB setup: Terminal → Run Task → Setup LeRobot (Docker + USB)"
echo "==================================="
echo
