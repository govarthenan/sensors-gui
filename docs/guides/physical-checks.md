# Physical checks — what to look for, and what to search

A short guide for Gova, for the questions that software cannot answer.

---

## 0. The board layout (added 2026-09-21)

`docs/reference/mobo-board-layout.png` is page 27 of the MSI manual. It shows
where every connector sits.

The 8 fan headers are in **four separate places**:

| Header | Where | Reports a speed? |
|---|---|---|
| `CPU_FAN1`, `PUMP_SYS1`, `SYS_FAN1` | **top edge**, right of the CPU socket, above the memory | **yes, all three** |
| `SYS_FAN5`, `SYS_FAN6` | **right edge**, just above the 24-pin power plug | no |
| `SYS_FAN2` | **left edge**, below `JTPM1`, near the rear sockets | no |
| `SYS_FAN3`, `SYS_FAN4` | **bottom edge**, right of centre | no |

Header ratings, from page 44 of the manual:

| Header | Mode | Max current | Max power |
|---|---|---|---|
| `CPU_FAN1` | automatic (it detects PWM or DC) | 2 A | 24 W |
| `PUMP_SYS1` | PWM | 3 A | 36 W |
| `SYS_FAN1` to `SYS_FAN6` | automatic | 1 A | 12 W |

### `JAF_1`, the EZ Conn header — the likely answer

There is a **ninth** connector that is not a fan header and that no sensor
driver reads: `JAF_1`, "EZ Conn-Header V1", on the **bottom edge** of the board
between `JDASH1` and `PCIE_PWR1`. See
`docs/reference/mobo-ez-conn-header.png`.

Its 8 pins are:

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | Ground | 2 | 5 V |
| 3 | 12 V | 4 | ARGB DATA |
| 5 | **Sense** | 6 | Ground |
| 7 | **Speed Control** | 8 | no pin |

One plug carries fan power, fan speed control, the fan tachometer **and** the
ARGB lighting. MSI ships a "1 to 2 EZ Conn-Cable" with this board.

Your case fans are lit. If they are chained on `JAF_1`, that explains
everything: there is no hub **box** to find, because it is only a cable.

**What to look for:** a single cable plugged into the **bottom edge** of the
board, roughly below the second graphics card slot. Follow it and see how many
fans it feeds.

## 1. The fan hub

### What it is

A fan hub is a small circuit board that lets **one** motherboard header drive
**many** fans. It takes power straight from the power supply, so it can feed
more fans than a header can.

The cost: only the **first** fan on a hub returns a speed signal to the board.
The rest are invisible. That is the likely reason the machine has 9 fans and
the board reports 3.

### What it looks like

- A flat black rectangle, about the size of a **pack of playing cards** or a
  little smaller.
- It has **many 4-pin sockets** in a row, often 6 to 10 of them.
- **One thick cable** leaves it and ends in a wide, flat **SATA power plug**
  (the same plug a hard disk uses), or in a 4-pin Molex plug.
- **One thin cable** leaves it and ends in a **4-pin fan plug** that goes to a
  motherboard header.
- It is usually stuck to the metal with **velcro** or double-sided tape, or
  screwed to a stand-off.

### Where it hides

Behind the **back panel** — the solid metal side, opposite the glass. Look:

- on the metal tray behind the motherboard, near the top;
- near the bottom, next to the power supply shroud;
- on the back of the front fan bracket.

### What to search for, to see pictures

- `PWM fan hub SATA powered`
- `10 port fan hub PC`
- `ARGB and PWM fan controller case`
- If your case is an NZXT: `NZXT RGB and fan controller`

### How to open the back panel

Most cases: two thumb screws at the **back edge** of that panel. Undo them by
hand, slide the panel **backwards** about one centimetre, then lift it away.
Some cases have a latch instead and the panel hinges open.

### What I need, if you do this

Two photographs:
1. The whole back side, with the panel off.
2. Any small board you find, close enough to read its sockets.

---

## 2. The liquid cooler model

**This is low priority. You may skip it.**

We already know the cooler has **no USB link**, because every USB device on the
machine is accounted for. So the model tells us nothing new about sensors. The
pump already reports 1470 RPM through the `PUMP_FAN` header, and that is all
the cooler will ever give us.

If you want it anyway, the easiest ways, in order of effort:

1. **Your order history or the receipt.** Search for "MSI" plus "liquid" or
   "CORELIQUID".
2. **The box**, if you kept it.
3. **The label on the radiator.** In your photograph
   `docs/photos/02-aio-radiator-bottom.jpg` there is a small white sticker on
   the right-hand end of the radiator. A close photograph of that sticker would
   have the model and the serial number.

From your photographs, the pump block is round, black, with a thin lit ring and
the MSI logo in the middle, and the radiator takes two fans. That fits the
**MSI MAG CORELIQUID** range in a 240 mm or 280 mm size. That is a guess from a
picture, not a fact, so it is not written into the inventory.

---

## 3. The easier path: let the software find the fans

You do **not** have to open the case to map the fans.

```bash
sudo ./scripts/map-fans.sh
```

It sets every fan except the pump to 30 percent, then raises **one header at a
time** to full speed for 8 seconds and tells you which header it is. You watch
and listen, and note which fan got loud. That gives the same answer as tracing
cables, with no tools.

Safety, enforced in the code and not left to you:

- The **pump header is never written to**. The script finds it by its label and
  refuses.
- No fan goes below 30 percent.
- Every original value is saved first and put back when the script ends,
  **including** when you press Ctrl-C or close the terminal.

See ADR 0007 for the rules that any write to hardware must follow.

---

## 4. What I do not need

- You do not have to remove the graphics card.
- You do not have to unplug anything.
- You do not have to power the machine down for the software test.
