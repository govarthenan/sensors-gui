# ADR 0011 — No I2C route to the graphics card, or to anything else

- Date: 2026-09-22
- Status: accepted
- Extends: ADR 0007 (this project writes nothing to hardware), ADR 0010 (read a
  register, never write to a mailbox)
- Evidence: `lab/exp-0013-rtx4090-board-sensors/`

## Context

Target 3 of `exp-0005` asks for three sensors of the RTX 4090 that NVML does
not report: the **hotspot temperature**, the **VRM temperature** and the speed
of **each** fan. The plan named one route, and marked it "TODO, and risky": the
card's own I2C buses, read from the board controller. This machine publishes
five of them, `i2c-3` to `i2c-7`, all on `0000:01:00.0`.

ADR 0010 requires one question before the route is planned: does it read, or
does it tell the hardware something? `exp-0013` answers it without touching a
bus.

## Decision

### 1. This project starts no I2C transaction, on any bus, at any address.

An I2C read is not a read at the bus level. To read a register the master must
**write** the register number first, then restart and read. The tools say so
themselves:

> I2C and SMBus are designed in such a way that an SMBus read transaction can
> be seen as a write transaction by certain chips. — `i2cget(8)`

> This program can confuse your I2C bus, cause data loss and worse!
> — `i2cdetect(8)`

Both of `i2cdetect`'s probing methods carry a known failure in the same manual
page: quick write corrupts a known EEPROM, and receive byte locks known
write-only chips.

This is the shape ADR 0010 already closed. It forbids writing an address into a
PCI configuration index register to read SMN, "because it is a write to a
shared register, and a second reader can be part-way through its own
transaction". An I2C register pointer is exactly such a register, and on a
graphics card there is certainly a second master: the card's own controller
reads these sensors continuously for its fan curve and its power limit.

### 2. Reading a sensor a kernel driver already publishes is not this.

The DIMM temperatures come from `spd5118` at `0x51` and `0x53`, and the
application reads them from `/sys/class/hwmon/`. That is allowed and it does
not change. The driver owns the bus, serialises the transaction and is the
kernel's business. What this decision forbids is **this project** opening
`/dev/i2c-N` and starting a transaction of its own.

### 3. Three targets are closed, not postponed

| Target | State |
|---|---|
| RTX 4090 hotspot temperature | **closed.** NVML gives one sensor; the rest is behind I2C |
| RTX 4090 memory and VRM temperature | **closed**, the same way |
| DDR5 PMIC rails at `0x49` and `0x4b` (`exp-0005` target 4) | **closed.** These are the memory power management chips. The original ADR 0007 named this address range as the one place never to write, on the day it still permitted writing. |
| The unknown I2C client at `0x4f` (`exp-0005` target 5) | **closed.** Identifying it means probing it. It stays unknown. |

They are written in `docs/sensor-sources.md` as unreachable with this reason,
never as "not tried yet".

As with ADR 0010, this can be reopened only by Gova, and only with a new ADR
that says what changed.

## Consequences

- `exp-0005` loses three more targets. What is left of its list is the Wi-Fi
  chip and MYSTIC LIGHT, and each one gets the ADR 0010 question first.
- The search that came out of this found something better: `exp-0013` shows
  NVML reports **the speed of each fan in RPM**, which was one of the three
  things target 3 wanted, through a plain library call with no bus, no root and
  no write. Four channels were added.
- The pattern from ADR 0010 holds a second time. Both times the forbidden route
  was the one written in the plan, and both times a route that only reads was
  already there, in the standard interface, unread.
- `i2c-tools` stays installed. It is useful for reading the manual pages and
  for listing adapters. No script in this project calls `i2cget`, `i2cset`,
  `i2cdump`, `i2ctransfer` or `i2cdetect`.
