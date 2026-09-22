# sensors-gui

A GUI sensor monitor for one specific PC: `dst-gova-pc` (AMD Ryzen 9 9900X,
MSI PRO X870-P WIFI, NVIDIA RTX 4090).

The goal is complete coverage of every sensor on this machine and every
connected component, with correct labels and correct units for this exact
hardware.

It reads **177 channels** from this machine and shows 153 of them. It only
reads; it never writes to hardware.

Status: working. See `HANDOFF.md`, then `state/STATUS.md`.

## Documents

| File | Contents |
|---|---|
| `HANDOFF.md` | **The whole picture in one file. Start here.** |
| `CLAUDE.md` | How to work on this project. |
| `state/STATUS.md` | Current phase, next actions, open questions. |
| `JOURNAL.md` | Dated log of events, findings and decisions. |
| `docs/hardware-inventory.md` | The components of this PC. |
| `docs/sensor-sources.md` | Every sensor source, with path, unit and status. |
| `docs/decisions/` | Decision records. |
| `lab/` | Experiments. |

## Setup

```bash
uv sync
```

## Run

```bash
uv run python -m sensors_gui
```

Two sources need root: the CPU energy counters and the drive's SMART log. A
small read-only service reads them and publishes them on a Unix socket, so the
screen never needs root. Install it once:

```bash
sudo ./scripts/install-helper.sh
```

Without it everything else still works, and those 19 channels show
"needs the helper" instead of a number.

| Key | Action |
|---|---|
| `q` | quit |
| `p` | pause and start the refresh |
| `r` | scan for sensors again |
| `h` | show the channels that are hidden by default |
| `+` / `-` | change the refresh rate, 0.25 Hz to 10 Hz |

The application **only reads**. It never writes to hardware. See ADR 0007 and
`data/evidence/2026-09-22-thermal-shutdown/` for why that rule exists.

## Author

Govarthenan Rajadurai
