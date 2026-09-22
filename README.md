# sensors-gui

A GUI sensor monitor for one specific PC: `dst-gova-pc` (AMD Ryzen 9 9900X,
MSI PRO X870-P WIFI, NVIDIA RTX 4090).

The goal is complete coverage of every sensor on this machine and every
connected component, with correct labels and correct units for this exact
hardware.

It reads **158 channels** from this machine and shows 134 of them. It only
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

| Key | Action |
|---|---|
| `q` | quit |
| `p` | pause and start the refresh |
| `r` | scan for sensors again |
| `+` / `-` | change the refresh rate, 0.25 Hz to 10 Hz |

The application **only reads**. It never writes to hardware. See ADR 0007 and
`data/evidence/2026-09-22-thermal-shutdown/` for why that rule exists.

## Author

Govarthenan Rajadurai
