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

from pathlib import Path

from lerobot.scripts.lerobot_find_port import is_motor_bus_port, parse_args as parse_find_port_args
from lerobot.scripts.lerobot_setup_container import (
    CPU_IMAGE,
    GPU_IMAGE,
    UsbDevice,
    classify_usb_device,
    container_serial_guess,
    parse_args as parse_setup_args,
    parse_usbipd_state,
    parse_vid_pid,
    pick_image,
    running_in_container,
    update_env_port,
    write_env_file,
)


def test_is_motor_bus_port_filters_dummy_ttys():
    assert is_motor_bus_port("/dev/ttyACM0")
    assert is_motor_bus_port("/dev/ttyUSB1")
    assert is_motor_bus_port("COM4")
    assert not is_motor_bus_port("/dev/ttyS0")
    assert not is_motor_bus_port("/dev/tty0")
    assert not is_motor_bus_port("/dev/tty")


def test_parse_vid_pid():
    assert parse_vid_pid(r"USB\VID_1A86&PID_7523\123") == "1a86:7523"
    assert parse_vid_pid("not-a-usb-id") == ""


def test_classify_ch343_serial():
    device = UsbDevice(
        busid="2-1",
        vid_pid="1a86:55d3",
        description="USB-Enhanced-SERIAL CH343 (COM3)",
        instance_id=r"USB\VID_1A86&PID_55D3\6&1",
        attached=True,
    )
    assert classify_usb_device(device) == "serial"


def test_classify_ch340_serial():
    device = UsbDevice(
        busid="3-1",
        vid_pid="1a86:7523",
        description="USB-SERIAL CH340",
        instance_id=r"USB\VID_1A86&PID_7523\6&1",
        attached=False,
    )
    assert classify_usb_device(device) == "serial"


def test_classify_mouse_as_noise_or_unknown():
    device = UsbDevice(
        busid="3-1",
        vid_pid="093a:822a",
        description="USB Input Device",
        instance_id=r"USB\VID_093A&PID_822A\6&1",
        attached=False,
    )
    assert classify_usb_device(device) == "unknown"


def test_classify_bluetooth_noise():
    device = UsbDevice(
        busid="2-5",
        vid_pid="0e8d:0717",
        description="RZ717 Bluetooth(R) Adapter",
        instance_id=r"USB\VID_0E8D&PID_0717\000",
        attached=False,
    )
    assert classify_usb_device(device) == "noise"


def test_parse_usbipd_state_skips_devices_without_busid():
    payload = """
    {
      "Devices": [
        {"BusId": null, "Description": "Persisted only", "InstanceId": "USB\\\\VID_1A86&PID_7523\\\\X"},
        {
          "BusId": "3-1",
          "Description": "USB-SERIAL CH340",
          "InstanceId": "USB\\\\VID_1A86&PID_7523\\\\ABC",
          "ClientIPAddress": "172.18.0.2"
        }
      ]
    }
    """
    devices = parse_usbipd_state(payload)
    assert len(devices) == 1
    assert devices[0].busid == "3-1"
    assert devices[0].vid_pid == "1a86:7523"
    assert devices[0].attached is True


def test_pick_image_force_flags():
    assert pick_image(force_cpu=True, force_gpu=False) == CPU_IMAGE
    assert pick_image(force_cpu=False, force_gpu=True) == GPU_IMAGE


def test_container_serial_guess_linux_paths(monkeypatch):
    monkeypatch.setattr("lerobot.scripts.lerobot_setup_container.is_windows", lambda: False)
    monkeypatch.setattr("lerobot.scripts.lerobot_setup_container.running_in_wsl", lambda: False)
    follower, leader = container_serial_guess(["/dev/ttyUSB0", "/dev/ttyACM0"])
    assert follower == "/dev/ttyUSB0"
    assert leader == "/dev/ttyACM0"


def test_write_env_file_preserves_unrelated_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("lerobot.scripts.lerobot_setup_container.repo_root", lambda: tmp_path)
    env = tmp_path / ".env"
    env.write_text("HF_TOKEN=keep-me\nLEROBOT_FOLLOWER_PORT=old\n", encoding="utf-8")
    write_env_file(tmp_path, image=CPU_IMAGE, follower="/dev/ttyACM0", leader="/dev/ttyACM1")
    text = env.read_text(encoding="utf-8")
    assert "LEROBOT_FOLLOWER_PORT=/dev/ttyACM0" in text
    assert "LEROBOT_LEADER_PORT=/dev/ttyACM1" in text
    assert "LEROBOT_IMAGE=" in text
    assert "HF_TOKEN=keep-me" in text
    docker_env = (tmp_path / "docker" / ".env").read_text(encoding="utf-8")
    assert "LEROBOT_FOLLOWER_PORT=/dev/ttyACM0" in docker_env
    assert "HF_TOKEN=keep-me" in docker_env


def test_update_env_port_writes_follower_and_leader(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("lerobot.scripts.lerobot_setup_container.repo_root", lambda: tmp_path)
    write_env_file(tmp_path, image=CPU_IMAGE, follower="/dev/ttyACM0", leader="/dev/ttyACM1")
    update_env_port(tmp_path, "leader", "/dev/ttyACM9")
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "LEROBOT_FOLLOWER_PORT=/dev/ttyACM0" in text
    assert "LEROBOT_LEADER_PORT=/dev/ttyACM9" in text
    assert (tmp_path / "docker" / ".env").read_text(encoding="utf-8") == text


def test_find_port_save_arg():
    assert parse_find_port_args(["--save", "follower"]).save == "follower"
    assert parse_find_port_args([]).save is None


def test_setup_print_commands_flag():
    args = parse_setup_args(["--print-commands"])
    assert args.print_commands is True


def test_running_in_container_false_without_markers(monkeypatch):
    monkeypatch.setattr("lerobot.scripts.lerobot_setup_container.Path.exists", lambda self: False)
    monkeypatch.delenv("REMOTE_CONTAINERS", raising=False)
    monkeypatch.delenv("CODESPACES", raising=False)
    assert running_in_container() is False


def test_running_in_container_true_with_dockerenv(monkeypatch):
    monkeypatch.setattr("lerobot.scripts.lerobot_setup_container.Path.exists", lambda self: True)
    assert running_in_container() is True
