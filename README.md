# turtleSIScripting (LeRobot fork)

**This is not original work from scratch.** Almost all of the code was written by the [Hugging Face LeRobot](https://github.com/huggingface/lerobot) team. Credit for the library, robots, and docs belongs to them.

This copy adds a **one-command Docker + USB path** so two SO-101 arms (leader + follower) show up inside VS Code / Cursor on Windows. If the robot learns, thank Hugging Face. If the cables show up in Docker, that part is this overlay.

- Upstream: [huggingface/lerobot](https://github.com/huggingface/lerobot)
- License: [Apache 2.0](./LICENSE)
- Robot docs: [SO-101](https://huggingface.co/docs/lerobot/so101)

---

## What you install once

Do these on the **Windows PC** (not inside Docker):

1. [Docker Desktop](https://docs.docker.com/get-docker/) — start it and wait until it says **Running**
2. [Python 3.12+](https://www.python.org/downloads/windows/) — check **Add python.exe to PATH**
3. [usbipd-win](https://github.com/dorssel/usbipd-win/releases) — `winget install usbipd`
4. [VS Code](https://code.visualstudio.com/) or [Cursor](https://cursor.com/), then install the **Dev Containers** extension when the editor asks

Plug in **both** motor-bus USB cables. Power **both** arms. Use data cables, not charge-only.

---

## Start here (read this once)

There are two different “setup” things in this repo. Use the **first**. Ignore the **second**.

| | What it is | Do you run it? |
| --- | --- | --- |
| **Ctrl+Shift+B** | VS Code’s default **Build** task. In this folder that task **is** **Setup LeRobot (Docker + USB)**. It runs `docker/setup.ps1` on Windows: start Docker, share the two robot USB cables, write `.env`. | **Yes. This is step 1.** Same as **Terminal → Run Task → Setup LeRobot (Docker + USB)**. |
| **`setup.py`** | Hugging Face’s old Python *package* installer (`pip install .`). It does **not** talk to Docker or USB. | **No.** Do not run `python setup.py` for the arms. |

**Order:** Ctrl+Shift+B (while still on Windows) → **Dev Containers: Reopen in Container** → Find port / Calibrate / Teleoperate **inside** the green container.

You are on Windows until the bottom-left corner says `Dev Container: LeRobot`. Find-port and teleop will fail if you skip Reopen in Container.

---

## Path A — VS Code / Cursor (do this)

Open **this folder** (the one that contains `src/` and `docker/`). When the editor offers **Install Recommended Extensions**, click Install.

### On the Windows PC (folder is local, not in Docker yet)

1. Press **Ctrl+Shift+B** (or **Terminal → Run Task… → Setup LeRobot (Docker + USB)** — same command).  
   Click **Yes** if Windows asks to share USB. Wait until you see `/dev/ttyACM0` and `/dev/ttyACM1`. That is not a freeze.
2. **Command Palette** (`Ctrl+Shift+P`) → **Dev Containers: Reopen in Container**  
   Wait until the bottom-left corner says `Dev Container: LeRobot`. A welcome message lists serial devices.

If it says **none yet**, stay calm: **Command Palette → Dev Containers: Reopen Folder Locally**, run **Reattach robot USB to Docker**, then **Reopen in Container** again.

### Inside the container (green / Dev Container window)

Run these **in order**. Unplug a cable **only** when the task tells you to. Plug it back in before the next step.

| Order | Terminal → Run Task… | What you do |
| --- | --- | --- |
| 3 | **Find port and save as follower** | Unplug the **follower** USB, Enter, plug it back in |
| 4 | **Find port and save as leader** | Unplug the **leader** USB, Enter, plug it back in |
| 5 | **Calibrate follower** | Center the arm, Enter, sweep joints |
| 6 | **Calibrate leader** | Same for the leader |
| 7 | **Teleoperate** | Move the leader. The follower should copy it. **Ctrl+C** stops |

You can also press **F5** and pick `LeRobot: Teleoperate` (same thing, with a debugger).

Docker has **no robot window**. Do not add `--display_data=true` unless you have a real display.

---

## Path B — terminal only (no VS Code)

On Windows PowerShell, from the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File docker/setup.ps1
```

Inside the container:

```bash
ls -l /dev/ttyACM*
lerobot-find-port --save follower
lerobot-find-port --save leader
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=my_follower
lerobot-calibrate --teleop.type=so101_leader  --teleop.port=/dev/ttyACM1 --teleop.id=my_leader
lerobot-teleoperate \
  --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=my_follower \
  --teleop.type=so101_leader  --teleop.port=/dev/ttyACM1 --teleop.id=my_leader
```

If find-port saved different paths, **Show robot commands** (VS Code task) or:

```bash
python src/lerobot/scripts/lerobot_setup_container.py --print-commands
```

Linux / macOS host:

```bash
bash docker/setup.sh
```

On **macOS**, Docker cannot reliably see USB robot cables. Use Docker for training; run LeRobot on the Mac itself for the real arms.

---

## If something breaks

### VS Code / Cursor popups

| What you see | What to do |
| --- | --- |
| **An environment file is configured but terminal environment injection is disabled** | Click **Enable** on the toast, or set `python.terminal.useEnvFile` to true (this repo already does). Then **close the terminal and open a new one**. That loads `.env` so `LEROBOT_FOLLOWER_PORT` / `LEROBOT_LEADER_PORT` exist in the terminal. Ignore the toast if you only use **Terminal → Run Task** (those tasks read `.env` themselves). |
| **This workspace has extension recommendations** | Click **Install**. You need **Dev Containers**, Python, and Docker. |
| **Do you trust the authors of the files in this folder?** | Click **Yes, I trust the authors**. Tasks and the Dev Container will not run until you do. |
| **Restricted Mode** | Click **Manage** → trust the folder. Same as above. |
| Offered **Reopen in WSL** | Skip it. For this repo use **Dev Containers: Reopen in Container**, not WSL. |
| Bottom-left does **not** say `Dev Container: LeRobot` | You are still on Windows. Command Palette → **Dev Containers: Reopen in Container** before Find port / Calibrate / Teleoperate. |
| Asking to **select a Python interpreter** | In the Dev Container pick `/lerobot/.venv/bin/python`. On Windows host, Setup only needs any Python 3.12+ on PATH. |
| Unsure whether to run **`setup.py`** or **Ctrl+Shift+B** | **Ctrl+Shift+B**. `setup.py` only installs the Python library; it will not share USB into Docker. |

### Docker, USB, and the arms

| What you see | What to do |
| --- | --- |
| Docker is not running | Open Docker Desktop, wait until it is Running, run Setup again |
| Python not found | Install Python 3.12 and tick **Add to PATH**, then open a **new** terminal |
| `usbipd` missing | `winget install usbipd` |
| Permission popup | Click **Yes**. Needed once per USB adapter |
| Setup looks frozen | Wait. The first USB share and image download take minutes |
| `ls` has no `ttyACM` | HOST: **Reattach robot USB to Docker**, then reopen the container |
| find-port: no difference after unplug | You unplugged while the share dropped. Reattach, plug **both** cables in, try again |
| `FileNotFoundError: /dev/ttyACM0` | Same as missing ttyACM. Reattach on the host |
| Rerun / `DISPLAY is not set` | Expected in Docker. Run teleop **without** `--display_data=true` |
| `Failed to write 'Lock' on id_=2` | Look at the **follower** motor LEDs. All steady red = retry teleop. Motor 2 dark = reseat that 3-pin cable. Blinking = overload or wrong PSU (5 V / 7.4 V vs 12 V are not interchangeable) |
| Calibrate / teleop on Windows COM3 | Those names only work **outside** Docker. Use the Dev Container so ports are `/dev/ttyACM*` |
| Ran Setup **inside** the container | USB setup is host-only. Reopen folder locally, run Setup, then Reopen in Container |

Always plug each arm into the **same physical USB port** so names stay stable.

---

## What this fork adds

Upstream LeRobot already runs in Docker. On Windows, COM ports do **not** appear inside Docker Desktop by themselves. The overlay:

1. Checks Docker and starts it if needed
2. Finds motor-bus USB adapters (CH340 / CH343 / CP210 / FTDI) and ignores mice/keyboards
3. Shares them into Docker with `usbipd` (and binds QinHeng chips to `cdc_acm` so `/dev/ttyACM*` exists)
4. Writes `.env` / `docker/.env` with `LEROBOT_FOLLOWER_PORT` and `LEROBOT_LEADER_PORT`
5. Opens a container that mounts `/dev` and uses this repo as `/workspaces/lerobot`

VS Code / Cursor pieces (committed):

- [`.vscode/tasks.json`](./.vscode/tasks.json) — Setup, Reattach, Find port, Calibrate, Teleoperate
- [`.vscode/launch.json`](./.vscode/launch.json) — F5 debug the same commands
- [`.vscode/extensions.json`](./.vscode/extensions.json) — Dev Containers, Docker, Python, Serial Monitor
- [`.devcontainer/devcontainer.json`](./.devcontainer/devcontainer.json) + [`docker/compose.yaml`](./docker/compose.yaml)

More Docker detail: [`docker/README.md`](./docker/README.md).

---

## Using the rest of LeRobot

Everything else is upstream:

```bash
uv sync --locked --extra feetech
```

[Installation](https://huggingface.co/docs/lerobot/installation) · [GitHub](https://github.com/huggingface/lerobot) · [Discord](https://discord.gg/s3KuuzsPFb)

Send robotics-ML features to **huggingface/lerobot**, not this overlay repo.
