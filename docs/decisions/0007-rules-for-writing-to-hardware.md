# ADR 0007 — Rules for any write to hardware

- Date: 2026-09-21
- Status: accepted

## Context

Every part of this project so far only **reads**. ADR 0005 says the privileged
helper reads and never writes, and that fan control, if it comes, needs its own
decision.

`scripts/map-fans.sh` is the first thing that writes. It changes the fan control
outputs of the board, because that is the only way to find out which fan sits on
which header without opening the case.

A write to hardware can do harm that a read cannot:

- A stopped pump lets a CPU overheat in seconds.
- A fan left at zero after a crashed script leaves the machine with no cooling,
  quietly, until something fails.
- A wrong write to a power management chip can put a wrong voltage on a part.

## Decision

Any code in this project that writes to hardware keeps all six rules.

1. **Never write to a bus address that controls power.** In particular, never
   write to I2C addresses 0x48 to 0x4F. Those are the DDR5 power management
   chips, and they set the voltage of the memory modules.
2. **Never write to a pump.** The pump channel is found by its label, not by
   its number, and the code refuses to write to it. A number can move; a label
   is what the board itself reports.
3. **Never command a cooling device to stop.** The floor is 30 percent of the
   control range. The project has no need to stop a fan, so it may not.
4. **Save first, restore always.** The original value of every channel written
   is read and kept before the first write. The restore runs on a normal exit,
   on an error, on Ctrl-C and on a kill signal.
5. **Bound the time.** A write that changes a safety-relevant setting is held
   for seconds, not minutes, and the code returns the machine to its own
   automatic control by itself.
6. **The rules live in the code, not in the instructions.** An operator who
   skips the README must still be safe.

A write that cannot keep all six rules is not written.

## Consequences

- `scripts/map-fans.sh` is allowed, because it keeps all six.
- The privileged helper of ADR 0005 stays read-only. This ADR does not open it
  up.
- A fan **curve** feature, which holds a setting for hours rather than seconds,
  breaks rule 5. It needs its own decision, its own watchdog, and Gova's
  explicit agreement. It is not in scope now.
- The application itself still writes nothing. Only this one script does, and
  only when Gova runs it by hand.
