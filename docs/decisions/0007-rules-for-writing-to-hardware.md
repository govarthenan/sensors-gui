# ADR 0007 — Rules for any write to hardware

- Date: 2026-09-21
- Status: **reverted 2026-09-22.** Read the amendment of 2026-09-22 at the
  bottom of this file first. The rules below permitted a write; they do not
  apply any more. **This project writes nothing to hardware.**

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

---

## Amendment, 2026-09-21: when a fan may be stopped

Rule 3 said a cooling device may never be commanded to stop. The first version
of `map-fans.sh` kept that rule and set a floor of 30 percent, so the operator
had to pick a louder fan out of nine running ones. **It did not work.** Gova
tried it and could not tell them apart.

Gova proposed the method that does work: stop every fan, then run one at a
time, so that only one turns and it can be **seen** rather than heard. Gova
asked for this after the concern was raised, and the machine is idle.

So rule 3 is narrowed. A fan that is not a pump may be stopped, but only when
**all** of these hold:

1. **The pump keeps running.** This is not relaxed. Coolant must keep moving.
2. **A watchdog samples every second** and restores everything the moment any
   watched sensor passes a limit. The limits here are Tctl 80 °C, VRM 70 °C and
   the drive 70 °C.
3. **The machine must be cool to start.** The script refuses to run if Tctl is
   already over 65 °C.
4. **Each step is bounded in seconds**, and the whole run has its own hard
   limit as well. Both are checked by the same loop as the watchdog, so a
   sleeping script cannot outlive them.
5. **The restore runs on every exit path**: normal end, error, Ctrl-C, kill,
   and watchdog abort. It is guarded so that it cannot run twice.
6. This is for a **diagnostic run that a person is watching**. The application
   itself still writes nothing, ever.

The physics support this. The loop holds a large mass of coolant, the CPU is at
idle, and the graphics card runs its own fans, which the board does not control.
Fifteen seconds with the case fans stopped moves an idle CPU by a few degrees.
The watchdog exists for the case where that reasoning is wrong.

### Why this is written down

The first version of the rule was too strict to do the job it existed for, and
a rule that blocks the work gets worked around in a hurry, without a watchdog.
Narrowing it in the open, with the conditions in code, is safer than leaving it
absolute.


---

## Amendment, 2026-09-22: the whole decision is reverted

**This file described how to write to hardware safely. That approach failed on
the machine on the same day, and the rule is now absolute: this project writes
nothing to hardware. No exceptions and no conditions.**

### What happened

`scripts/map-fans.sh`, written under the rules above, put the CPU fan header
into manual mode at zero to find which fan was on which header. The chip
**rejected the write that put it back**. The radiator fans stopped, `Tctl`
reached 98 °C, and the board shut the machine down. The script is deleted. The
full record is `data/evidence/2026-09-22-thermal-shutdown/`.

Four faults let it happen, and each one looked reasonable on its own:

1. The restore wrote the old value and never **verified** it.
2. The watchdog's only action was the write path that was already failing.
3. Mode and speed were separate writes, so a partial success left the worst
   state: manual control, at zero.
4. The radiator fan header was in scope at all. Rule 2 protected the pump
   alone; on a liquid-cooled machine the radiator fan is as critical.

So the six rules were not too weak in detail. They were the wrong shape: every
one of them depends on a write succeeding later, and that is the thing that
failed.

### The rule now

> **This project writes nothing to hardware. If a question can only be answered
> by writing, drop the question.**

Fan control, fan mapping and a fan curve are out of scope. They do not need a
better watchdog; they need a different project. The answer `map-fans.sh` was
chasing arrived a few hours later from a **photograph of the BIOS**, for free.

### Why the old text stays

The project keeps what disproves a claim. The six rules read as careful and
complete, and they are what the machine shut itself down under. Deleting them
would hide the most useful fact in this file: **a write can be planned well and
still take the machine down, because the safety of a write depends on a later
write.**

### What this changes in the rest of the repository

- ADR 0009 and ADR 0010 cite this decision as the absolute no-write rule. That
  citation is correct from this amendment onward, and it was **not** correct
  against the text above it, which is why this amendment was written.
- Old rule 1 said "never write to I2C addresses 0x48 to 0x4F". Read against the
  rules above, that permits an I2C write to any other address. It does not any
  more: no I2C write to any address, for any reason.
- ADR 0010 gives the test to apply to a new route: is the machine **asked** or
  **told**? A register read is a question. A command word, an index register or
  a bus address pointer written before the read is a statement.
