#!/usr/bin/env python

# Copyright 2026 The HuggingFace Inc. team. All rights reserved.
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

"""One-command Docker + USB setup for real robots.

Works without LeRobot installed (stdlib only):

    python src/lerobot/scripts/lerobot_setup_container.py

After install:

    lerobot-setup-container

Windows / Linux / macOS launchers:

    powershell -ExecutionPolicy Bypass -File docker/setup.ps1
    bash docker/setup.sh
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

CPU_IMAGE = "huggingface/lerobot-cpu:latest"
GPU_IMAGE = "huggingface/lerobot-gpu:latest"
WSL_DISTRO = "docker-desktop"
USB_CACHE_NAME = ".usb-ports.json"

# Common USB-UART chips used on motor-bus adapters (Feetech, Dynamixel, etc.).
SERIAL_VIDS = {
    "1a86",  # QinHeng CH340 / CH341
    "10c4",  # Silicon Labs CP210x
    "0403",  # FTDI
    "067b",  # Prolific
    "2341",  # Arduino
    "2e8a",  # Raspberry Pi RP2040
    "0483",  # STMicroelectronics CDC
    "239a",  # Adafruit
    "303a",  # Espressif
    "1b4f",  # SparkFun
    "16c0",  # Teensy
    "03eb",  # Atmel
    "04d8",  # Microchip
    "0d28",  # ARM mbed
}

NOISE_RE = re.compile(
    r"bluetooth|webcam|camera|fingerprint|keyboard|mouse|"
    r"wi-?fi|hdmi expansion|touch pad|touch screen|hub$|"
    r"root hub|host controller|npu |display",
    re.I,
)
SERIAL_RE = re.compile(
    r"serial|uart|ch340|ch341|ch343|cp210|ftdi|cdc|acm|usb-serial|usb serial|\bcom\d+\b",
    re.I,
)


@dataclass(frozen=True)
class UsbDevice:
    busid: str
    vid_pid: str
    description: str
    instance_id: str
    attached: bool


def repo_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [Path.cwd(), *here.parents]
    for path in candidates:
        if (path / "docker").is_dir() and (path / "src" / "lerobot").is_dir():
            return path
    return Path.cwd()


def say(message: str) -> None:
    print(message, flush=True)


def step(title: str) -> None:
    say("")
    say(f"==> {title}")


def ask(prompt: str, *, assume_yes: bool, default_yes: bool = True) -> bool:
    if assume_yes:
        say(f"{prompt} [{'Y' if default_yes else 'N'}] (auto)")
        return default_yes
    suffix = " [Y/n] " if default_yes else " [y/N] "
    reply = input(prompt + suffix).strip().lower()
    if not reply:
        return default_yes
    return reply in {"y", "yes"}


def pause(message: str, *, assume_yes: bool) -> None:
    if assume_yes:
        say(message)
        return
    input(f"{message}  This is not frozen. Press Enter to continue...")


def which(name: str) -> str | None:
    return shutil.which(name)


def run(
    args: list[str],
    *,
    check: bool = False,
    capture: bool = True,
    timeout: int | None = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603
        args,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_macos() -> bool:
    return platform.system() == "Darwin"


def is_linux() -> bool:
    return platform.system() == "Linux"


def running_in_wsl() -> bool:
    if not is_linux():
        return False
    try:
        text = Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    return "microsoft" in text or "wsl" in text


def running_in_container() -> bool:
    """True inside Docker / Dev Containers (USB setup must run on the host)."""
    if Path("/.dockerenv").exists():
        return True
    return os.environ.get("REMOTE_CONTAINERS") == "true" or os.environ.get("CODESPACES") == "true"


def parse_vid_pid(instance_id: str) -> str:
    match = re.search(r"VID_([0-9A-Fa-f]{4}).*PID_([0-9A-Fa-f]{4})", instance_id or "")
    if not match:
        return ""
    return f"{match.group(1).lower()}:{match.group(2).lower()}"


def parse_usbipd_state(payload: str) -> list[UsbDevice]:
    if not payload.strip():
        return []
    data = json.loads(payload)
    devices: list[UsbDevice] = []
    for raw in data.get("Devices") or []:
        busid = (raw.get("BusId") or "").strip()
        if not busid:
            continue
        instance_id = raw.get("InstanceId") or ""
        devices.append(
            UsbDevice(
                busid=busid,
                vid_pid=parse_vid_pid(instance_id),
                description=raw.get("Description") or "",
                instance_id=instance_id,
                attached=bool(raw.get("ClientIPAddress")),
            )
        )
    return devices


def classify_usb_device(device: UsbDevice) -> str:
    """Return 'serial', 'noise', or 'unknown'."""
    vid = device.vid_pid.split(":")[0] if device.vid_pid else ""
    description = device.description or ""
    if vid in SERIAL_VIDS or SERIAL_RE.search(description):
        return "serial"
    if NOISE_RE.search(description):
        return "noise"
    return "unknown"


def pick_image(*, force_cpu: bool, force_gpu: bool) -> str:
    if force_cpu and force_gpu:
        raise ValueError("Choose only one of --cpu or --gpu.")
    if force_cpu:
        return CPU_IMAGE
    if force_gpu:
        return GPU_IMAGE
    if which("nvidia-smi") is None:
        return CPU_IMAGE
    try:
        result = run(["nvidia-smi", "-L"], check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return CPU_IMAGE
    if result.returncode == 0 and "GPU" in (result.stdout or ""):
        return GPU_IMAGE
    return CPU_IMAGE


def docker_bin() -> str | None:
    return which("docker")


def docker_is_running() -> bool:
    binary = docker_bin()
    if binary is None:
        return False
    try:
        result = run([binary, "info"], check=False, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def start_docker_desktop() -> bool:
    candidates: list[Path] = []
    if is_windows():
        program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        candidates.append(Path(program_files) / "Docker" / "Docker" / "Docker Desktop.exe")
    elif is_macos():
        candidates.append(Path("/Applications/Docker.app/Contents/MacOS/Docker"))
    for path in candidates:
        if path.is_file():
            say(f"Starting Docker Desktop ({path})...")
            try:
                subprocess.Popen([str(path)])  # nosec B603
            except OSError as exc:
                say(f"Could not start Docker Desktop: {exc}")
                return False
            return True
    return False


def wait_for_docker(*, seconds: int = 120) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if docker_is_running():
            return True
        time.sleep(3)
        say("  still waiting for Docker...")
    return False


def ensure_docker(*, assume_yes: bool) -> bool:
    step("Checking Docker")
    if docker_is_running():
        say("Docker is running.")
        return True
    if docker_bin() is None:
        say("Docker is not installed.")
        say("Install Docker Desktop (Windows/macOS) or Docker Engine (Linux):")
        say("  https://docs.docker.com/get-docker/")
        say("Then run this command again.")
        return False
    say("Docker is installed but not running.")
    if is_linux() and not running_in_wsl():
        say("Start it with:  sudo systemctl start docker")
        return False
    if not ask("Start Docker Desktop now?", assume_yes=assume_yes, default_yes=True):
        return False
    if not start_docker_desktop():
        say("Open Docker Desktop yourself, wait until it says 'Running', then re-run this.")
        return False
    if wait_for_docker():
        say("Docker is ready.")
        return True
    say("Docker did not become ready in time. Open Docker Desktop, wait, then re-run this.")
    return False


def list_host_serial_ports() -> list[str]:
    if is_windows():
        try:
            result = run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    '[System.IO.Ports.SerialPort]::GetPortNames() -join "`n"',
                ],
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]

    ports: list[str] = []
    dev = Path("/dev")
    if not dev.is_dir():
        return []
    prefixes = (
        "ttyACM",
        "ttyUSB",
        "tty.usbmodem",
        "tty.usbserial",
        "cu.usbmodem",
        "cu.usbserial",
    )
    for path in dev.iterdir():
        if path.name.startswith(prefixes):
            ports.append(str(path))
    return sorted(set(ports))


def usbipd_bin() -> str | None:
    found = which("usbipd")
    if found:
        return found
    if running_in_wsl():
        windows = Path("/mnt/c/Program Files/usbipd-win/usbipd.exe")
        if windows.is_file():
            return str(windows)
    return None


def list_usbipd_devices() -> list[UsbDevice]:
    binary = usbipd_bin()
    if binary is None:
        return []
    try:
        result = run([binary, "state"], check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    try:
        return parse_usbipd_state(result.stdout or "")
    except json.JSONDecodeError:
        return []


def print_usb_table(devices: list[UsbDevice]) -> None:
    if not devices:
        say("  (none)")
        return
    say(f"  {'BUSID':<8} {'VID:PID':<12} {'KIND':<8} {'ATTACHED':<8} DEVICE")
    for device in devices:
        say(
            f"  {device.busid:<8} {device.vid_pid or '-':<12} {classify_usb_device(device):<8} "
            f"{'yes' if device.attached else 'no':<8} {device.description}"
        )


def usbipd_bind_and_attach(device: UsbDevice) -> bool:
    binary = usbipd_bin()
    if binary is None:
        return False
    bind = run([binary, "bind", "--busid", device.busid], check=False)
    if bind.returncode != 0:
        say("Need Administrator once so Windows will share this USB device.")
        say("A permission popup may appear — click Yes.")
        elevated = run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    f"Start-Process -FilePath '{binary}' "
                    f"-ArgumentList 'bind --busid {device.busid}' "
                    "-Verb RunAs -Wait"
                ),
            ],
            check=False,
            capture=True,
        )
        if elevated.returncode != 0:
            say(bind.stderr.strip() if bind.stderr else "usbipd bind failed.")
            return False
    start_usbipd_auto_attach(binary, device.busid)
    if not wait_until_usb_attached(device.busid, timeout_s=25):
        say(f"Timed out waiting for {device.busid} to attach to Docker.")
        return False
    say(f"Shared {device.busid} ({device.description}) into Docker.")
    return True


def start_usbipd_auto_attach(binary: str, busid: str) -> None:
    """Watch for unplug/replug without blocking this script.

    `usbipd attach --auto-attach` stays running. Waiting on it looks like a freeze.
    """
    flags = 0
    if is_windows():
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    try:
        subprocess.Popen(  # nosec B603
            [binary, "attach", "--wsl", WSL_DISTRO, "--busid", busid, "--auto-attach"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            start_new_session=not is_windows(),
        )
    except OSError as exc:
        say(f"Could not start usbipd auto-attach for {busid}: {exc}")


def wait_until_usb_attached(busid: str, *, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for device in list_usbipd_devices():
            if device.busid == busid and device.attached:
                return True
        time.sleep(0.5)
    return False


def bind_wsl_ch343_serial() -> None:
    """Docker Desktop often attaches CH343 (1a86:55d3) as USB but not as ttyACM.

    Bind cdc_acm and make the nodes world-accessible so the container can open them.
    """
    wsl = which("wsl")
    if wsl is None:
        return
    run(
        [
            wsl,
            "-d",
            WSL_DISTRO,
            "-e",
            "sh",
            "-c",
            "modprobe cdc-acm 2>/dev/null; "
            "echo '1a86 55d3' > /sys/bus/usb/drivers/cdc_acm/new_id 2>/dev/null; "
            "echo '1a86 7523' > /sys/bus/usb/drivers/cdc_acm/new_id 2>/dev/null; "
            "sleep 1; chmod 666 /dev/ttyACM* /dev/ttyUSB* 2>/dev/null; true",
        ],
        check=False,
    )


def list_wsl_tty_nodes() -> list[str]:
    wsl = which("wsl")
    if wsl is None:
        return []
    result = run(
        [
            wsl,
            "-d",
            WSL_DISTRO,
            "-e",
            "sh",
            "-c",
            "ls -1 /dev/ttyACM* /dev/ttyUSB* 2>/dev/null",
        ],
        check=False,
    )
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def wait_for_wsl_serial_nodes(*, minimum: int = 2, timeout_s: float = 20) -> list[str]:
    deadline = time.time() + timeout_s
    nodes: list[str] = []
    while time.time() < deadline:
        bind_wsl_ch343_serial()
        nodes = list_wsl_tty_nodes()
        if len(nodes) >= minimum:
            return nodes
        time.sleep(1)
    return nodes


def list_docker_vm_serial_ports() -> None:
    nodes = wait_for_wsl_serial_nodes(minimum=1, timeout_s=12)
    if nodes:
        say("Serial devices inside Docker's Linux VM:")
        for node in nodes:
            say(f"  {node}")
    else:
        say("No /dev/ttyACM* yet in Docker's VM. Plug both cables in and re-run:")
        say("  powershell -ExecutionPolicy Bypass -File docker/setup.ps1 --reattach")


def save_usb_cache(root: Path, devices: list[UsbDevice]) -> None:
    path = root / "docker" / USB_CACHE_NAME
    payload = {
        "ports": [
            {
                "busid": device.busid,
                "vidPid": device.vid_pid,
                "instanceId": device.instance_id,
                "description": device.description,
            }
            for device in devices
        ]
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_usb_cache(root: Path) -> list[dict[str, str]]:
    path = root / "docker" / USB_CACHE_NAME
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return list(data.get("ports") or [])


def match_cached_devices(cached: list[dict[str, str]], connected: list[UsbDevice]) -> list[UsbDevice]:
    matched: list[UsbDevice] = []
    for item in cached:
        for device in connected:
            if item.get("instanceId") and device.instance_id == item["instanceId"]:
                matched.append(device)
                break
            if item.get("busid") and device.busid == item["busid"]:
                matched.append(device)
                break
    return matched


def choose_robot_usb_devices(connected: list[UsbDevice], *, assume_yes: bool) -> list[UsbDevice]:
    serial = [d for d in connected if classify_usb_device(d) == "serial"]
    unknown = [d for d in connected if classify_usb_device(d) == "unknown"]
    if len(serial) >= 2:
        chosen = serial[:2]
        if len(serial) > 2:
            say(f"Found {len(serial)} serial adapters; using the first two.")
            print_usb_table(chosen)
        return chosen
    if len(serial) == 1 and assume_yes:
        say("Found only 1 serial adapter. Plug in the second robot USB cable and re-run.")
        return serial
    if not assume_yes and unknown:
        say("These extra USB devices are plugged in, but I am not sure which are the robots:")
        print_usb_table(unknown)
        say("Type two bus IDs (example: 3-1 4-2), or press Enter to skip.")
        reply = input("bus IDs> ").strip()
        if reply:
            wanted = set(reply.split())
            return [d for d in connected if d.busid in wanted]
    return serial


def setup_windows_usb(*, root: Path, assume_yes: bool) -> list[UsbDevice]:
    step("USB cables (Windows → Docker)")
    if usbipd_bin() is None:
        say("usbipd is missing. It shares USB devices with Docker on Windows.")
        say("Install it, then re-run this command:")
        say("  winget install usbipd")
        say("  https://github.com/dorssel/usbipd-win/releases")
        return []

    attempts = 1 if assume_yes else 4
    for attempt in range(attempts):
        connected = list_usbipd_devices()
        say("USB devices Windows can see:")
        print_usb_table(connected)

        cached = match_cached_devices(load_usb_cache(root), connected)
        chosen = cached if len(cached) >= 1 else choose_robot_usb_devices(connected, assume_yes=assume_yes)

        if len(chosen) >= 1:
            ok = True
            for device in chosen[:2]:
                ok = usbipd_bind_and_attach(device) and ok
            if ok:
                save_usb_cache(root, chosen[:2])
                list_docker_vm_serial_ports()
            return chosen[:2]

        if attempt < attempts - 1:
            pause(
                "Plug in BOTH robot USB cables (motor-bus adapters, not a mouse/keyboard), then",
                assume_yes=assume_yes,
            )
    say("No robot serial adapters yet. That's OK — Docker will still work for training.")
    say("When the arms are here, plug both USB cables in and run this command again.")
    return []


def setup_linux_usb(*, assume_yes: bool) -> list[str]:
    step("USB serial ports (Linux)")
    ports = list_host_serial_ports()
    if ports:
        say("Found serial ports:")
        for port in ports:
            say(f"  {port}")
    else:
        say("No /dev/ttyACM* or /dev/ttyUSB* yet. Plug in the robot USB cables if you have them.")

    try:
        groups = run(["id", "-nG"], check=False)
        in_dialout = "dialout" in (groups.stdout or "").split()
    except (OSError, subprocess.SubprocessError):
        in_dialout = False
    if not in_dialout:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or "your-user"
        say("Your Linux user cannot open serial ports until it is in the 'dialout' group.")
        say(f"  sudo usermod -aG dialout {user}")
        say("Then log out and back in (or reboot) and run this command again.")
        if not assume_yes and ask("Run that sudo command now?", assume_yes=False, default_yes=True):
            run(["sudo", "usermod", "-aG", "dialout", user], check=False, capture=False)
            say("Log out and back in before talking to the robot.")
    return ports


def setup_macos_usb() -> None:
    step("USB on macOS")
    say("Docker Desktop on macOS cannot reliably see USB robot cables.")
    say("Use Docker for training. For a real robot, run LeRobot on the Mac (not in Docker):")
    say("  uv sync --extra feetech")
    say("  lerobot-find-port")
    ports = list_host_serial_ports()
    if ports:
        say("Serial ports on this Mac right now:")
        for port in ports:
            say(f"  {port}")


def read_env_file(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in (root / ".env", root / "docker" / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def dump_env_files(root: Path, values: dict[str, str]) -> Path:
    """Write repo-root `.env` and `docker/.env` (Compose interpolates the latter)."""
    lines = ["# Written by lerobot-setup-container. Safe to edit."]
    for key, value in values.items():
        lines.append(f"{key}={value}")
    text = "\n".join(lines) + "\n"
    path = root / ".env"
    path.write_text(text, encoding="utf-8")
    docker_dir = root / "docker"
    docker_dir.mkdir(parents=True, exist_ok=True)
    (docker_dir / ".env").write_text(text, encoding="utf-8")
    return path


def write_env_file(root: Path, *, image: str, follower: str, leader: str) -> Path:
    existing = read_env_file(root)
    existing["LEROBOT_IMAGE"] = image
    existing["LEROBOT_FOLLOWER_PORT"] = follower
    existing["LEROBOT_LEADER_PORT"] = leader
    return dump_env_files(root, existing)


def update_env_port(root: Path, role: str, port: str) -> Path:
    """Save a find-port result as follower or leader (used by calibrate/teleop tasks)."""
    if role not in {"follower", "leader"}:
        raise ValueError(f"role must be 'follower' or 'leader', got {role!r}")
    existing = read_env_file(root)
    key = "LEROBOT_FOLLOWER_PORT" if role == "follower" else "LEROBOT_LEADER_PORT"
    existing.setdefault("LEROBOT_IMAGE", CPU_IMAGE)
    existing.setdefault("LEROBOT_FOLLOWER_PORT", "/dev/ttyACM0")
    existing.setdefault("LEROBOT_LEADER_PORT", "/dev/ttyACM1")
    existing[key] = port
    return dump_env_files(root, existing)


def print_copy_paste_commands(root: Path) -> None:
    env = read_env_file(root)
    follower = env.get("LEROBOT_FOLLOWER_PORT", "/dev/ttyACM0")
    leader = env.get("LEROBOT_LEADER_PORT", "/dev/ttyACM1")
    say("")
    say("Copy-paste (ports come from .env after find-port --save):")
    say(
        "  lerobot-calibrate "
        f"--robot.type=so101_follower --robot.port={follower} --robot.id=my_follower"
    )
    say(
        "  lerobot-calibrate "
        f"--teleop.type=so101_leader --teleop.port={leader} --teleop.id=my_leader"
    )
    say(
        "  lerobot-teleoperate "
        f"--robot.type=so101_follower --robot.port={follower} --robot.id=my_follower "
        f"--teleop.type=so101_leader --teleop.port={leader} --teleop.id=my_leader"
    )


def container_serial_guess(host_ports: list[str]) -> tuple[str, str]:
    if is_windows() or running_in_wsl():
        return "/dev/ttyACM0", "/dev/ttyACM1"
    acm = [p for p in host_ports if "ttyACM" in p or "ttyUSB" in p]
    if len(acm) >= 2:
        return acm[0], acm[1]
    if len(acm) == 1:
        return acm[0], "/dev/ttyACM1"
    return "/dev/ttyACM0", "/dev/ttyACM1"


def pull_image(image: str) -> bool:
    binary = docker_bin()
    if binary is None:
        return False
    step(f"Downloading {image}")
    say("This can take several minutes the first time.")
    result = run([binary, "pull", image], check=False, capture=False, timeout=None)
    return result.returncode == 0


def start_container(root: Path, image: str, *, gpu: bool) -> int:
    binary = docker_bin()
    if binary is None:
        return 1
    step("Starting LeRobot")
    args = [
        binary,
        "run",
        "-it",
        "--rm",
        "--privileged",
        "--group-add",
        "dialout",
        "-v",
        "/dev:/dev",
        "-v",
        f"{root}:/workspaces/lerobot",
        "-w",
        "/workspaces/lerobot",
        "-e",
        "PYTHONPATH=/workspaces/lerobot/src",
        "--env-file",
        str(root / ".env"),
    ]
    if gpu:
        args.extend(["--gpus", "all", "--shm-size", "16gb"])
    args.append(image)
    say(" ".join(args))
    return subprocess.run(args, check=False).returncode  # nosec B603


def print_next_steps(*, in_container: bool) -> None:
    say("")
    say("Keep BOTH USB cables plugged in unless find-port asks you to unplug one.")
    say("Inside the container (or VS Code / Cursor after Reopen in Container):")
    say("  ls -l /dev/ttyACM*")
    say("  lerobot-find-port --save follower    # unplug the FOLLOWER arm when asked")
    say("  lerobot-find-port --save leader      # unplug the LEADER arm when asked")
    say("Then: Terminal → Run Task → Calibrate follower / Calibrate leader / Teleoperate")
    say("If /dev/ttyACM* vanishes after unplug, on the Windows HOST (not in Docker) run:")
    say("  powershell -ExecutionPolicy Bypass -File docker/setup.ps1 --reattach")
    say("  Terminal → Run Task → Reattach robot USB to Docker")
    if not in_container:
        say("")
        say("VS Code / Cursor: Command Palette → Dev Containers: Reopen in Container")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Check Docker and USB, then start a LeRobot container that can see two robot ports."),
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Do not prompt. Keep going with safe defaults.",
    )
    parser.add_argument(
        "--host-prep",
        action="store_true",
        help="Only prepare Docker/USB. Do not start a container.",
    )
    parser.add_argument("--no-run", action="store_true", help="Same as --host-prep.")
    parser.add_argument("--cpu", action="store_true", help="Force the CPU image.")
    parser.add_argument("--gpu", action="store_true", help="Force the NVIDIA GPU image.")
    parser.add_argument("--skip-usb", action="store_true", help="Skip USB bind/detect.")
    parser.add_argument(
        "--reattach",
        action="store_true",
        help="Re-share USB serial adapters into Docker after unplug (does not start a container).",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker checks (USB only).",
    )
    parser.add_argument(
        "--print-commands",
        action="store_true",
        help="Print calibrate/teleoperate commands from .env and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    host_prep_only = bool(args.host_prep or args.no_run or args.reattach)
    assume_yes = bool(args.yes or host_prep_only)
    if args.reattach:
        args.skip_usb = False
    root = repo_root()

    if args.print_commands:
        print_copy_paste_commands(root)
        return 0

    if running_in_container():
        step("You are already inside the container")
        say("USB sharing happens on the HOST computer, not here.")
        say("VS Code / Cursor on Windows: Terminal → Run Task → Setup LeRobot (Docker + USB)")
        say("or on the host:  powershell -ExecutionPolicy Bypass -File docker/setup.ps1 --reattach")
        ports = list_host_serial_ports()
        if ports:
            say("Serial ports this container can see:")
            for port in ports:
                say(f"  {port}")
        else:
            say("No /dev/ttyACM* here. Reattach USB on the host, then reopen the container.")
        print_next_steps(in_container=True)
        print_copy_paste_commands(root)
        return 0

    say("LeRobot Docker + robot USB setup")
    say("I will check this computer and tell you if something is missing.")
    say(f"Folder: {root}")
    say(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    if running_in_wsl():
        say("Detected WSL. USB sharing still uses usbipd on Windows.")

    image = pick_image(force_cpu=args.cpu, force_gpu=args.gpu)
    say(f"Image: {image}")

    docker_ok = True
    if not args.skip_docker:
        docker_ok = ensure_docker(assume_yes=assume_yes)
        if not docker_ok and not host_prep_only:
            return 1

    host_ports: list[str] = []
    if not args.skip_usb:
        if is_windows() or running_in_wsl():
            setup_windows_usb(root=root, assume_yes=assume_yes)
            host_ports = list_host_serial_ports()
        elif is_macos():
            setup_macos_usb()
            host_ports = list_host_serial_ports()
        else:
            host_ports = setup_linux_usb(assume_yes=assume_yes)

    follower, leader = container_serial_guess(host_ports)
    env_path = write_env_file(root, image=image, follower=follower, leader=leader)
    say(f"Wrote {env_path} and {root / 'docker' / '.env'}")
    say(f"  LEROBOT_FOLLOWER_PORT={follower}")
    say(f"  LEROBOT_LEADER_PORT={leader}")
    say("These are guesses until you run lerobot-find-port --save follower/leader.")

    if host_prep_only or args.skip_docker:
        print_next_steps(in_container=False)
        print_copy_paste_commands(root)
        return 0

    if not docker_ok:
        return 1

    if not pull_image(image):
        say("Could not download the image. Check your internet connection and try again.")
        return 1

    if not assume_yes:
        say("")
        say("Start the LeRobot container in this terminal now?")
        say("  Y = start Docker (you will get a Linux shell)")
        say("  N = stop here; later use VS Code → Dev Containers: Reopen in Container")
        if not ask("Start the container now?", assume_yes=False, default_yes=True):
            print_next_steps(in_container=False)
            return 0

    print_next_steps(in_container=True)
    return start_container(root, image, gpu=image == GPU_IMAGE)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        say("\nStopped.")
        raise SystemExit(130) from None
