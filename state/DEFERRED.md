# DEFERRED

The one list of work that is put off until Gova has time. Gova, 2026-10-27:
"Record all deferred in a single file so we can pick up when we have time."

Rules for this file:
- One row per item. When an item is done, move it to "Done" with the date
  and the commit or file that closed it. Do not delete it.
- `state/STATUS.md` keeps the open questions (Q-numbers) and the current
  phase. This file says only what waits, who it waits on, and where the
  detail is.
- **No item here may be done by writing to hardware** (ADR 0007, ADR 0010,
  ADR 0011). A test that changes a fan is done by Gova in the BIOS, never by
  the project.

Last update: 2026-10-27, session 13.

## Waits on Gova at the machine

| # | Item | What to do | Detail |
|---|---|---|---|
| D1 | **Q20: which fans each board header drives** | In the BIOS: set one header to 100 % and the others to their BIOS minimum for about 15 s, and say which fans change; then set it back. Order: `SYS_FAN1`, `JAF_1` (EZ Conn), `CPU_FAN1`. **Never stop the pump**, and never set `CPU_FAN1` to 0: it may be the pump (H1). One header at a time, in conversation. | `lab/exp-0020-case-cooler-identity/README.md`; STATUS Q20 |
| D2 | **BIOS fan curves** | In the same BIOS visit as D1: photograph the Smart Fan page of each header (CPU, pump, SYS1, EZ Conn). This says which temperature each fan follows. | `docs/photos/bios/02-fan-curve.jpg` is the only one so far |
| D3 | **Model names** | Read and send: the case model; the model of the front, top and rear fans; confirm the CPU cooler is an MSI MAG CORELIQUID E360 (box, invoice or a label). | `lab/exp-0020-case-cooler-identity/README.md` |
| D4 | **Q14: which card fan channel drives which fans** | Watch the card's fans while the GUI shows the two channels. Read-only. | `lab/exp-0017-gpu-fan-channels/README.md`, procedure lines 114-140 |
| D5 | **Q18: more dots on the card wireframe** | A photograph of the card's fan side or the bare board. | STATUS Q18 |
| D6 | **Q7: `nvme0n1p4`** | Say what is on the 359.2 GB partition that is not mounted. | STATUS Q7 |
| D7 | **Q10: unsafe shutdowns** | About one in five power cycles is an unsafe shutdown. Does Gova know the cause of the ones that are not the thermal shutdown? | STATUS Q10 |
| D8 | **C1200 model number** | Read the model number from the power supply's label, for the power research. | `lab/exp-0019-power-draw-sources/` |

## Waits on a decision by Gova

| # | Item | The choice | Detail |
|---|---|---|---|
| D9 | **Q21: the iGPU "PPT" channel** | Keep, read less often, or drop. Each read makes the kernel driver send a message to the SMU, and the value does not follow the CPU. Claude recommends drop (option C). | STATUS Q21; JOURNAL 2026-09-25 |
| D10 | **Power draw of the whole system** (Gova's `TODO`) | Which route, if any: a smart plug with a local API (ranked first), or a "CPU + GPU (measured)" channel now. Needs D8, and approval before `avahi-browse` queries the network. | `lab/exp-0019-power-draw-sources/`; the `TODO` file |
| D11 | **`exp-0019/results/network-neighbours.txt`** | Commit, redact or delete. It holds the MAC addresses of hosts on the home network. It is not committed. | HANDOFF section 9 |
| D12 | **Session 11 test values** | Confirm or correct: pressure `some avg10=1.53` gives 1.53 %; `pgfault` 1000 then 1600 two seconds later gives 300/s; a counter that falls counts from 0; the bar of 20.0, 40.4 and 1.7 GiB gives 20.0, 38.7 and 1.7 GiB. | STATUS, session 11 |
| D13 | **Q4: mouse battery as a percent** | Is a percent from HID++ (Solaar) worth a dependency? HID may be a write; ask the ADR 0010 question first. | STATUS Q4 |
| D14 | **Upstream the driver patch** | Offer `driver/nct6687-ms7e47.patch` to `Fred78290/nct6687d`. It goes out under Gova's name. | STATUS next action 1 |

## Claude can do, at low priority

| # | Item | Detail |
|---|---|---|
| D15 | Chrome window stays open when the server gets SIGTERM; Ctrl+C not tested. | JOURNAL 2026-10-16 |
| D16 | `--page "/#cpu"` once showed the Motherboard view; cause not known. | JOURNAL 2026-10-16 |
| D17 | `README.md` gives old channel counts. | JOURNAL 2026-10-16 |
| D18 | The NVIDIA driver is now 595.99.02; `docs/hardware-inventory.md` says 595.91.07. | `data/probes/2026-10-27-gpu-fans-turning-when-cool.txt` |
| D19 | Q22: a webcam (Sonix `0c45:6366`) is not in the inventory. | STATUS Q22 |
| D20 | `exp-0005` targets 6 (Wi-Fi chip, `ath12k`) and 7 (MYSTIC LIGHT over HID). Ask the ADR 0010 question of each first; HID is likely a write. | `lab/exp-0005-component-census/README.md` |

## Done

| # | Item | Closed |
|---|---|---|
| — | — | — |
