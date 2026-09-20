# turtleSIScripting (LeRobot fork)

**This repository is not original work from scratch.** Almost all of the code here was written by the [Hugging Face LeRobot](https://github.com/huggingface/lerobot) developers and contributors. Credit for the library, policies, datasets, robot drivers, and documentation belongs to them.

This GitHub copy exists so I can keep a small set of **setup edits** on top of that project: a one-command path to build/start a Docker container and get **two robot USB serial ports** into that container (leader + follower). If something works because of LeRobot, thank the original authors. If the auto-setup helps you plug arms into Docker, that part is the local overlay.

- Original project: [huggingface/lerobot](https://github.com/huggingface/lerobot)
- License: [Apache 2.0](./LICENSE) (same as upstream)
- Docs from the original team: [huggingface.co/docs/lerobot](https://huggingface.co/docs/lerobot)

---

## What this fork adds

Upstream LeRobot already runs in Docker. On Windows, USB motor-bus adapters (COM ports) do **not** automatically appear inside Docker Desktop’s Linux VM. These edits walk you through that:

1. Check that Docker is installed and running (start Docker Desktop if needed).
2. Look for robot serial adapters (CH340 / CP210 / FTDI, etc.) and ignore mice, keyboards, webcams.
3. On Windows, share those USB devices into Docker with `usbipd`.
4. Write `.env` with `LEROBOT_FOLLOWER_PORT` and `LEROBOT_LEADER_PORT`.
5. Pull the LeRobot image and start a container that mounts `/dev` so both ports are visible.

You do **not** need to memorize docker flags. Run the one command below. If something is missing (Python, Docker, cables, admin permission), the script prints what to do next instead of failing silently.

---

## One command: Docker + robot ports

From the **repo root** (the folder that contains `src/` and `docker/`).

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File docker/setup.ps1
```

The first USB share may show a Windows permission popup. Click **Yes**. After that, re-runs do not need Administrator.

### Linux / macOS

```bash
bash docker/setup.sh
```

On **macOS**, Docker Desktop cannot reliably see USB robot cables. Use Docker for training; run LeRobot on the Mac itself when you need the real arms.

### After LeRobot is installed

```bash
lerobot-setup-container
```

Useful flags:

```bash
lerobot-setup-container --host-prep   # Docker + USB only; do not open a shell
lerobot-setup-container --cpu         # force CPU image
lerobot-setup-container --gpu         # force NVIDIA GPU image
lerobot-setup-container -y            # no questions; keep going
```

No robot plugged in yet? Run it anyway. It will say the cables are missing and can still pull/start Docker for training. When the leader and follower motor-bus USB cables are plugged in, run the **same command again**.

---

## After the container is up

Inside the container:

```bash
ls -l /dev/ttyACM* /dev/ttyUSB* /dev/serial/by-id
lerobot-find-port
```

Unplug **one** arm when asked so you know which path is the follower and which is the leader. Then use those paths with the normal upstream commands (`lerobot-calibrate`, `lerobot-teleoperate`, `lerobot-record`, …). See the original [SO-101 guide](https://huggingface.co/docs/lerobot/so101) and [`docker/README.md`](./docker/README.md).

### VS Code / Cursor

1. Run `docker/setup.ps1` or `docker/setup.sh` once on the host.
2. Command Palette → **Dev Containers: Reopen in Container**.

That uses [`.devcontainer/devcontainer.json`](./.devcontainer/devcontainer.json) and [`docker/compose.yaml`](./docker/compose.yaml) so `/dev` (both serial ports) is mounted into the container.

You can also use **Terminal → Run Task → Setup LeRobot (Docker + USB)**.

---

## What you need

- [Docker Desktop](https://docs.docker.com/get-docker/) (Windows/macOS) or Docker Engine (Linux)
- [Python 3.12+](https://www.python.org/downloads/) on the host (the Windows script tells you if PATH is missing)
- On Windows, [usbipd-win](https://github.com/dorssel/usbipd-win/releases) (`winget install usbipd`) so USB devices can enter the Docker VM
- Two **data** USB cables to the motor-bus boards (not a mouse, not a charge-only cable)

Always plug each arm into the **same physical USB port** so the names stay stable.

---

## Using the rest of LeRobot

Everything else is upstream. Install and train the way the original project documents:

```bash
pip install lerobot
# or from this repo:
uv sync --locked --extra feetech
```

[Installation](https://huggingface.co/docs/lerobot/installation) · [GitHub](https://github.com/huggingface/lerobot) · [Discord](https://discord.gg/s3KuuzsPFb)

If you are contributing features back to robotics ML, send them to **huggingface/lerobot**, not this overlay repo.
