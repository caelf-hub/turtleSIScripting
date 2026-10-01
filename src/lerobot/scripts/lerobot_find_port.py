# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Helper to find the USB port associated with your MotorsBus.

Example:

```shell
lerobot-find-port
lerobot-find-port --save follower
lerobot-find-port --save leader
```
"""

from __future__ import annotations

import argparse
import re
import sys
import time

from lerobot.scripts.lerobot_setup_container import repo_root, running_in_container, update_env_port

_ROBOT_PORT_RE = re.compile(r"(ttyACM|ttyUSB|cu\.usb|tty\.usb|COM\d+)", re.I)


def is_motor_bus_port(path: str) -> bool:
    """True for USB-serial adapters, false for dummy /dev/ttyS* and /dev/tty0-63."""
    return bool(_ROBOT_PORT_RE.search(path))


def find_available_ports():
    from lerobot.utils.import_utils import require_package

    require_package("pyserial", extra="hardware", import_name="serial")
    from serial.tools import list_ports

    ports = [port.device for port in list_ports.comports()]
    return [path for path in ports if is_motor_bus_port(path)]


def _warn_if_windows_host() -> None:
    if sys.platform != "win32" or running_in_container():
        return
    print(
        "You are on Windows. This will print COM3-style names, which Docker cannot use.\n"
        "For this repo: Command Palette → Dev Containers: Reopen in Container,\n"
        "then run lerobot-find-port --save follower (and --save leader) in that terminal."
    )


def find_port(*, save_as: str | None = None) -> str:
    print("Finding USB serial ports for the MotorsBus.")
    _warn_if_windows_host()
    ports_before = find_available_ports()
    print("Ports before disconnecting:", ports_before)
    if len(ports_before) < 1:
        raise OSError(
            "No USB serial ports found (expected /dev/ttyACM* or COM*). "
            "On Windows Docker, run this on the host: "
            "powershell -ExecutionPolicy Bypass -File docker/setup.ps1 --reattach "
            "(VS Code: Terminal → Run Task → Reattach robot USB to Docker)"
        )

    role = save_as or "this arm"
    print(f"Unplug the USB cable for the {role} arm only, then press Enter.")
    input()

    time.sleep(0.5)
    ports_after = find_available_ports()
    ports_diff = list(set(ports_before) - set(ports_after))

    if len(ports_diff) == 1:
        port = ports_diff[0]
        print(f"The port of this MotorsBus is '{port}'")
        if save_as:
            if port.upper().startswith("COM"):
                print(
                    "Not saved: that is a Windows COM name. Run this command inside the Dev Container "
                    "so the path is /dev/ttyACM0 (or similar)."
                )
            else:
                path = update_env_port(repo_root(), save_as, port)
                print(f"Saved as LEROBOT_{save_as.upper()}_PORT={port} in {path} and docker/.env")
        print("Plug that USB cable back in and wait 2 seconds.")
        print("Do not run calibrate until `ls -l /dev/ttyACM*` shows both ports again.")
        print("If a port is missing on Windows, run on the HOST (not in Docker):")
        print("  powershell -ExecutionPolicy Bypass -File docker/setup.ps1 --reattach")
        print("  VS Code: Terminal → Run Task → Reattach robot USB to Docker")
        return port
    if len(ports_diff) == 0:
        raise OSError(f"Could not detect the port. No difference was found ({ports_diff}).")
    raise OSError(f"Could not detect the port. More than one port was found ({ports_diff}).")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find which USB serial port belongs to a robot arm.")
    parser.add_argument(
        "--save",
        choices=("follower", "leader"),
        help="Write the detected port into .env as follower or leader (then VS Code tasks can use it).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    find_port(save_as=args.save)


if __name__ == "__main__":
    main()
