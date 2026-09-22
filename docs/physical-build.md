# The physical build

From photographs that Gova took on 2026-09-21, in `docs/photos/`. Every entry
says whether it was **seen** in a photograph or **inferred**.

| Photograph | Shows |
|---|---|
| `01-psu-nzxt-c1200.jpg` | the power supply, through the shroud window |
| `02-aio-radiator-bottom.jpg` | the pump, the graphics card and the radiator at the bottom |
| `03-pump-and-top-fans.jpg` | the pump block, the VRM heatsink, the top fans and the rear fan |
| `04-full-interior.jpg` | the whole interior |
| `05-front-fans.jpg` | the front fans and the radiator |

## Components seen

| Item | Model | Source |
|---|---|---|
| Power supply | **NZXT C1200** | seen, photo 01 |
| CPU cooler | **MSI liquid cooler (AIO)**, MSI logo on the pump block | seen, photos 02–04 |
| Radiator | mounted at the **bottom** of the case, with **2 fans** | seen, photos 02, 04, 05 |
| Graphics card | **MSI GeForce RTX 4090 SUPRIM** | seen, photos 02–04 |
| Graphics power | a 600 W rated 12VHPWR cable | seen, photo 05 |
| Case | a mesh-front tower, side glass panel | seen, photo 04 |

## Fan layout

| Location | Count | Source |
|---|---|---|
| Front, intake | 3 | seen, photos 04 and 05, lit, in a vertical column at the front |
| Top | 3 | seen, photos 03 and 04 |
| Rear, exhaust | 1 | seen, photos 03 and 04, behind the mesh at the rear |
| **AIO radiator, at the bottom** | **2** | seen, photos 02, 04, 05 |
| Pump | 1 | seen, photos 02–04 |
| Graphics card | on the card itself, not visible | the MSI SUPRIM has its own fans in its shroud |

**Total: 9 case fans and one pump.**

Gova's count on 2026-09-21 was "2 fans from the GPU, mounted separate, 3 intake,
3 top, 1 rear". The photographs show that the 2 fans below the graphics card are
the **AIO radiator fans**, not fans of the card. The card has its own fans
inside its shroud. The total is the same: 9.

## The fan wiring question

The board has 8 headers. Only **3** carry a tachometer signal:

| Header | RPM | PWM | Probably |
|---|---|---|---|
| `CPU Fan` (`fan1`) | 2247–2439 | 174 of 255 (68 %) | the radiator fans |
| `Pump Fan` (`fan2`) | 1470 | 255 of 255 (100 %) | the AIO pump |
| `System Fan #1` (`fan3`) | 1291 | 153 of 255 (60 %) | one case fan |
| `System Fan #2` to `#6` | **0** | 153 | nothing reports |

**ANSWERED on 2026-09-22 by a photograph of the BIOS.** The BIOS fan list has
a **ninth** entry that Linux does not show:

```
EZ Conn Fan        1612 RPM   (963 RPM at another moment)
```

The case fans are on the **`JAF_1` EZ Conn header** on the bottom edge of the
board. There was never a hub to find, because an EZ Conn connection is a
**cable**, not a box. That is why Gova, looking from every angle the case
allowed, saw nothing.

The five empty `SYS_FAN` headers are genuinely empty: the BIOS prints `N/A`
where Linux prints `0`. The two sources agree.

Linux is missing that channel because the driver gives this board 8 channels.
It supports 9, but enables the ninth only for the MEG Z890 GODLIKE. See
`exp-0009`.

**It is not a USB controller.** Every USB device is accounted for:

| USB | Device |
|---|---|
| `046d:c358` | Logitech G515 TKL keyboard |
| `046d:c53f` | Logitech USB receiver, for the G305 mouse |
| `0db0:0076` | MSI MYSTIC LIGHT, the board's own RGB controller |
| `0489:e10a` | Foxconn Bluetooth, `btusb`, `hci0` — it is the Bluetooth half of the Wi-Fi card |
| `05e3:0608` | Genesys Logic USB 2.0 hub |

There is no NZXT controller, no Corsair Commander and no USB link to the AIO.
The pump reports through the `PUMP_FAN` header only.

## Consequences for the application

1. **Do not hide a fan header that reads 0 RPM.** Five headers read zero. If
   the application hides them, a fan that has **stopped** disappears instead of
   raising an alarm. Show them, and mark them "no signal".
2. **The fan count on the screen will be 3, not 9.** That is the truth of what
   the board can see. The screen must say so, rather than imply the machine has
   3 fans.
3. **The power supply gives no telemetry.** The NZXT C1200 has no USB
   monitoring link, and nothing on the USB bus belongs to it. Total system
   power cannot be measured. It can only be estimated from the CPU package
   power and the GPU power.

## Open questions for Gova

1. At the back of the case, on the cable side: is there a **fan hub**, and
   which headers have cables in them? This is the only way to map the 9 fans to
   the 3 signals.
2. What is the exact model of the MSI liquid cooler? It is printed on the
   radiator or on the box. The MAG CORELIQUID range and the MPG range differ in
   what they report.
