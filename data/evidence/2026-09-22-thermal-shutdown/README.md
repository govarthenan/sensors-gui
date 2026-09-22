# Incident — thermal shutdown, 2026-09-22

## Summary

`scripts/map-fans.sh`, written by Claude, stopped the CPU radiator fans of
Gova's machine and could not start them again. `Tctl` reached at least 98 °C and
the board shut the machine down to protect itself.

**No hardware was damaged.** The machine rebooted normally with every fan back
under BIOS control.

## Timeline

| Time (+0530) | Event |
|---|---|
| 2026-09-21 16:40:30 | `nct6687` driver loads. `Found NCT6687D or compatible chip at 0x004e:0x0a20`. |
| 2026-09-21 16:55:10 | **First** `The device rejected new configuration as invalid`. The first fan test run. |
| 2026-09-22 (morning) | Gova runs the second version of `map-fans.sh`, with the step time raised to 60 s. No fan is seen to slow, because the speed writes are being rejected. |
| 2026-09-22 09:06:53 | **The last message the kernel ever wrote in that boot** is another write rejection. |
| 2026-09-22 ~09:10 | The board shuts the machine down. The journal has a gap from 09:06:53, which is what a hard power cut looks like. |
| 2026-09-22 09:21 | Gova boots into the BIOS and photographs it. |
| 2026-09-22 09:26 | Linux boots. Claude observes `pwm1 = 0, enable = 1`, `CPU Fan 0 RPM`, `Tctl 97 °C`, still climbing. |
| 2026-09-22 09:50 | Gova runs `scripts/restore-fans.sh` and reboots. |
| 2026-09-22 09:54 | Machine healthy. `Tctl 54 °C`, all headers `enable = 2`. |

## Cause

`map-fans.sh` set `CPU_FAN1` to manual mode and then to zero, to find which
physical fan was on which header. The chip **rejected the write that put the
speed back**, but had **accepted** the write that put the header into manual
mode. The header was left under manual control at zero.

## Why the safety rules did not catch it

ADR 0007 had six rules and every one of them ran. Four faults defeated them:

1. **The restore was never verified.** The code wrote the original value and
   moved on, and never read it back. On this board the driver's writes fail
   often, so an unchecked restore was a coin toss.
2. **The watchdog's only action was the failing action.** It sampled the
   temperature every second and would have restored through the same rejected
   write path.
3. **Mode and speed were separate writes.** A partial success left the worst
   possible state: manual control, at zero.
4. **The radiator fan header was in scope.** Rule 2 protected the pump alone.
   On a liquid-cooled machine the radiator fan is just as critical.

## Outcome

- `scripts/map-fans.sh` is **deleted**, not repaired.
- ADR 0007 is reverted: **this project writes nothing to hardware**, with no
  exceptions and no conditions.
- The question the script was chasing — which fan is on which header — was
  answered for free a few hours later by a photograph of the BIOS. See
  `lab/exp-0009-bios-ground-truth/`.

## A contributing factor on the machine

The BIOS setting `CPU Fan Fail Warning Control` is **OFF**
(`docs/photos/bios/04-board-and-bios-version.jpg`). With it on, the board warns
at power-on when the CPU fan does not turn. Recommended to Gova: switch it on.

## Files

| File | Contents |
|---|---|
| `kernel-nct6687-messages.txt` | every `nct6687` line from the boot that died |
| `kernel-final-messages.txt` | the last 60 kernel messages before the power cut |
| `observed-state.txt` | the sysfs state and temperatures Claude read afterwards |
