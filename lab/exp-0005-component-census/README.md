# exp-0005 — the component census and the coverage matrix

Started 2026-09-17. Proposed by Gova.

## Question

Gova's question, in five steps:

1. List every component connected to this PC.
2. For each one, find what sensors the component **holds**, from its
   documentation.
3. Try to reach each of those sensors, and check that the value is not null and
   is realistic.
4. List which sensors we can reach and which we cannot, with the reason.
5. Ask Gova to look inside the case only where software cannot answer.

In one sentence: **find the denominator.** Today the project knows it reads 14
hwmon channels. It does not know whether that is 14 out of 20 or 14 out of 120.

## Change to step 2: there are no blueprints

MSI does not publish a schematic for the PRO X870-P WIFI, and no consumer board
maker does. Four sources replace it, and each is free and exact:

| Source | What it gives | Example |
|---|---|---|
| **Linux driver source** | the exact register map a driver reads | `drivers/hwmon/nct6683.c` lists every fan and voltage the chip reports |
| **Chip datasheet** | what the silicon holds | Nuvoton NCT6687D, Realtek RTL8126 |
| **Industry specification** | what a class of device must report | JEDEC JESD300 (DDR5 SPD hub), the NVMe specification log page 0x02 |
| **Board manual** | the block diagram and the header count | MSI publishes this |

## Safety rules for step 3

1. **Read only.** No probe in this experiment writes to any bus.
2. **Never write to I2C addresses 0x48 to 0x4F.** Those are the DDR5 power
   management chips. They set the voltage of the memory modules.
3. No blind I2C scan of a bus that carries a display. A DDC bus can be upset by
   a write, and `ddcutil` already gives the data safely.
4. Any new kernel module is installed through DKMS, so that it is signed and
   so that it can be removed.

## Step 1 result: the census

`census.py` walks every bus the kernel can enumerate and writes one row for
each component, with the sensor sources already known for it.

```bash
uv run python lab/exp-0005-component-census/census.py
```

**111 components. 18 have a known sensor source.**

| Bus | Components | With a known source |
|---|---|---|
| pci | 57 | 8 |
| i2c adapter | 15 | 0 (they are buses, not devices) |
| usb | 14 | 0 |
| drm connector | 9 | 2 |
| hid | 8 | 1 |
| i2c client | 2 | 2 |
| dmi (memory) | 2 | 2 |
| net | 2 | 2 |
| cpu | 1 | 1 |
| block | 1 | 1 |

Of the 93 with no source, 51 are PCI bridges, host bridges, I2C adapters and
USB root hubs. Those hold no sensor, and they are not a gap.

## Step 2 and 3 list: what to chase, in order

| # | Component | What it should hold | How to reach it | State |
|---|---|---|---|---|
| ~~1~~ | Super-I/O chip | 8 fans, 8 PWM, VRM and chipset temperature, 14 voltages | `nct6687d` DKMS module | **DONE 2026-09-21.** It is a Nuvoton NCT6687D at ISA 0x0a20. 29 channels. 4 voltages are wrong; see `exp-0007`. |
| ~~2~~ | Ryzen 9 9900X SMU | per-core power, SoC power, the real VID, per-CCD limits | ~~`ryzen_smu` or `zenpower3` DKMS module~~ | **CLOSED 2026-09-22, ADR 0010.** Both modules **write** a command word into the SMU mailbox. Per-core power arrived anyway, from MSR `0xc001029a`, which only reads. `exp-0012`. |
| ~~3~~ | RTX 4090 board | hotspot temperature, per-fan RPM, VRM temperature | ~~the card's own I2C bus (`i2c-3` to `i2c-7`), from the board controller~~ | **PART DONE, PART CLOSED 2026-09-22.** **Per-fan RPM is done**, and not over I2C: `nvmlDeviceGetFanSpeedRPM` gives both fans, and they differ (1205 and 1520 RPM). 4 channels. The hotspot and the VRM are **closed**: an I2C read writes the register pointer first, so ADR 0011 forbids the route. `exp-0013`. |
| ~~4~~ | DDR5 PMIC ×2 (`0x49`, `0x4b`) | module VIN, the 1.1 V and 1.8 V rails | ~~I2C read, per JESD301~~ | **CLOSED 2026-09-22, ADR 0011.** These are the chips that set memory voltage, and the first version of ADR 0007 named this address range as the one place never to write. The DIMM **temperatures** are read as before, through the `spd5118` kernel driver. |
| ~~5~~ | I2C client at `0x4f` | unknown | ~~identify it first~~ | **CLOSED 2026-09-22, ADR 0011.** Identifying it means probing it, and a probe writes. It stays unknown. |
| 6 | Qualcomm WCN7850 Wi-Fi | chip temperature | the `ath12k` driver, if it reports one | TODO |
| 7 | MSI MYSTIC LIGHT (`0DB0:0076`) | it is an RGB controller, but the MSI MCU can also carry fan and temperature data | the HID protocol, as OpenRGB uses it | TODO |
| ~~8~~ | ~~USB device `1-11`~~ | — | — | **ANSWERED: Foxconn Bluetooth, `0489:e10a`, driver `btusb`. No sensor.** |
| 9 | Logitech G515 TKL keyboard | it may report nothing; it is wired | HID++ | TODO |
| 10 | 2 × MSI MD272QXP monitors | brightness, contrast, input source, power state | `ddcutil` (works) | **reachable** |

## Step 5: the questions only Gova can answer

Gova answered on 2026-09-21. Photographs of the machine are expected.

1. **Fans.** 2 on the graphics card, mounted separately. 3 intake fans in the
   case. 3 fans on the top of the case. 1 fan at the rear. **9 in total**, of
   which 7 are case fans.
2. **CPU cooler.** A liquid cooler (AIO), so the board should also show a pump
   header. Whether the 3 top fans are the radiator fans is not yet known.
3. **Displays.** Into the RTX 4090.

The photographs arrived on 2026-09-21. See `docs/physical-build.md`. They
settled two of the three points:

- The 3 top fans are **not** the radiator fans. The radiator is at the
  **bottom** of the case, with its own 2 fans. The "2 fans from the GPU" that
  Gova named are those radiator fans, which sit below the card.
- The pump **does** report: 1470 RPM on the `PUMP_FAN` header.
- Still open: which headers the 9 fans are wired to. Only 3 of 8 headers give a
  signal. It is not a USB controller, because every USB device is accounted
  for. It is a splitter or a hub, and only a look at the cable side can say.

A `0 RPM` reading stays ambiguous, because it means "no fan fitted" as well as
"fan stopped". The count above gives the expected number, which is what makes a
`0` readable.
3. ~~Are the monitors plugged into the graphics card or into the
   motherboard?~~ **ANSWERED 2026-09-21: into the RTX 4090.** The claim that
   they ran from the integrated graphics was a mistake by Claude, which guessed
   the DRM card order instead of reading the PCI address behind each card.

## A finding from the census itself

The Logitech battery was `hidpp_battery_2` yesterday. After the reboot it is
`hidpp_battery_3`. The number changed with no change to the hardware. That is
ADR 0002 proved on the machine: **never key a sensor by its index.**
