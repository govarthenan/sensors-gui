# ADR 0002 — Identify hwmon devices by name and device path, not by index

- Date: 2026-09-16
- Status: accepted

## Context

Sensors live at `/sys/class/hwmon/hwmonN`. The number `N` comes from the order
in which drivers register. That order changes with kernel version, module load
order, and hot-plug. On this machine `hwmon2` is `k10temp` today. It can be
`hwmon4` after the next kernel update.

The machine also has **two** devices with the same name: `spd5118` at `hwmon3`
and `hwmon4`, one for each DIMM.

## Decision

The application identifies a sensor source with a stable key made of:

1. the `name` file of the hwmon device, and
2. the real path of the `device` symlink (for example
   `/sys/devices/pci0000:00/0000:00:14.0/i2c-0/0-0051`), and
3. the channel name (`temp1`).

The key is `name@device_path:channel`. Two `spd5118` devices stay separate
because their i2c addresses differ (`0-0051` and `0-0053`).

The index `hwmonN` is used only to find the devices during a scan. It is never
stored in configuration, and never shown to the user.

## Consequences

- User settings (alarms, colours, hidden channels) survive a reboot and a
  kernel update.
- The application must re-scan and re-match if a device disappears.
- The device path is long. The user interface shows a friendly name instead,
  from a mapping table in the application.
