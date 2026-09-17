# ADR 0005 — Read root-only sensors with a small privileged helper service

- Date: 2026-09-16
- Status: accepted
- Decided by: Gova

## Context

Some sensors need root:

| Sensor | Path | Mode |
|---|---|---|
| CPU package energy | `/sys/class/powercap/intel-rapl:0/energy_uj` | 0400 root |
| CPU core energy | `/sys/class/powercap/intel-rapl:0:0/energy_uj` | 0400 root |
| NVMe SMART / health log | NVMe admin command | root |

Three options were compared: a udev rule that relaxes the file mode, a
privileged helper service, and dropping these sensors.

## Decision

Build **`sensors-guid`**, a small helper that runs as root under systemd. It
reads only the root-only values and publishes them on a Unix domain socket.

```
sensors-guid.service  (User=root)
        |  reads RAPL energy counters, NVMe SMART
        v
/run/sensors-gui.sock  (group `gova`, mode 0660)
        ^
        |  newline-delimited JSON
sensors-gui TUI  (runs as user `gova`)
```

Rules for the helper:

1. It reads. It never writes to hardware in phase 2. Fan control, if it comes
   later, is a separate decision with its own ADR.
2. It has a fixed list of allowed paths and commands. The client cannot ask it
   to read an arbitrary file.
3. The client works without the helper. If the socket is absent, the affected
   channels show "needs the helper", and everything else still works.
4. The socket is `0660`, owner `root`, group `gova`. No network socket.
5. The helper is small and easy to read, because it runs as root.

## Consequences

- The user interface never needs root and never asks for a password.
- There is more code and a systemd unit to install and maintain.
- Installation needs one `sudo` step, one time.
- The protocol between the two parts must be defined and versioned.
