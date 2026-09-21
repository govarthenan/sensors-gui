# Physical checks — what to look for, and what to search

A short guide for Gova, for the questions that software cannot answer.

---

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
