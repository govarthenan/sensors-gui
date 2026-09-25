# Inline DC meters: ElmorLabs PMD2X and BENCHLAB

- Date accessed: 2026-09-25
- Tools: WebFetch (summarising; quotes may be paraphrased) and `curl -sfL` of the ElmorLabs sample code (verbatim).

## 1. ElmorLabs PMD2X — product page

- URL: https://www.elmorlabs.com/product/elmorlabs-pmd2x-power-measurement-device-2x/
- Returned: "Price: $109.00". "The ElmorLabs PMD2X lets you measure the voltage, current and power flowing through your CPU, GPU and motherboard power cables."
- Connectors: "2x EPS 8-pin (CPU) connectors max 28 A continuous load each"; "3x PCIE 8-pin (GPU) connectors max 27 A continuous load each"; "1x ATX 24-pin connector (12V 14 A, 5V 25 A, 5VSB 5 A, 3V3 25 A)"; "1x 12VHPWR PCIe 5.0 / ATX 3.0 connector (12V-2×6 version) max 51 A continuous load".
- Accuracy: "Voltage max error +/- 0.1 V (@ 12 V)"; "Current max error +/- 0.5 A (@ 10 A)".
- PC link: "USB Type-C connector for extended readings, logging and oscilloscope functionality". The page names "PMD2 Python example @ Github".
- The earlier PMD2 is marked "*discontinued*": https://elmorlabs.com/product/elmorlabs-pmd2/

## 2. ElmorLabs PMD2 serial protocol — verbatim from the maker's sample code

- Command: `curl -sfL -o pmd2-msm.py https://raw.githubusercontent.com/ElmorLabs/PMD2-Python/main/pmd2-msm.py`, then `sed -n` of the lines shown
- Source: https://github.com/ElmorLabs/PMD2-Python (main branch)

```python
class UART_CMD(IntEnum):
    CMD_WELCOME = 0
    CMD_READ_VENDOR_DATA = 1
    CMD_READ_UID = 2
    CMD_READ_DEVICE_DATA = 3
    CMD_READ_SENSOR_VALUES = 4
    CMD_WRITE_CONT_TX = 5
    CMD_READ_CALIBRATION = 6
    CMD_WRITE_CALIBRATION = 7
    CMD_LOAD_CALIBRATION = 8
    CMD_STORE_CALIBRATION = 9
    CMD_RESET = 0xF0
    CMD_BOOTLOADER = 0xF1
    CMD_NVM_CONFIG = 0xF2
    CMD_NOP = 0xFF
...
    ser = serial.Serial(ports[device_port], 115200, timeout=1, rtscts=False, dsrdtr=False)
...
    ser.write(UART_CMD.CMD_READ_VENDOR_DATA.toByte())
    buffer = ser.read(3)
...
                    ser.write(UART_CMD.CMD_READ_SENSOR_VALUES.toByte())
                    if vendor_data.ProductId == PRODUCT_ID_PMD2X:
                        buffer = ser.read(sizeof(SensorStruct_PMD2X))
                        if len(buffer) == sizeof(SensorStruct_PMD2X):
                            success = True
                    else:
                        buffer = ser.read(sizeof(SensorStruct))
```

What this shows: the device is a USB serial port at 115200 baud. To get readings, the host **sends one command byte**, `CMD_READ_SENSOR_VALUES = 4`, and reads a fixed structure back. The same protocol has `CMD_WRITE_CALIBRATION`, `CMD_STORE_CALIBRATION`, `CMD_RESET`, `CMD_BOOTLOADER` and `CMD_NVM_CONFIG`, which change the meter. A reader for this project must send byte 4 only (and perhaps 0, 1, 3 to identify the device). The meter is an external instrument, not this machine's hardware, but it sits **in the power cables** of the CPU and the GPU.

## 3. BENCHLAB

- URL: https://benchlab.io/products/benchlab
- Returned: "Price: $199.00 USD". Measures "1x 24-pin ATX (12V, 5V, 3.3V, 5VSB)", "2x 8-pin EPS (12V)", "3x 6+2-pin PCIE (12V)", "2x 12+4-pin 12VHPWR (12V)"; "32A on each channel, 64A for EPS1 and EPS2"; "USB Type-C for hub & MCU connection"; also "9x 4-pin (PWM)" fan headers with control, 4 thermistors, RGB. Accuracy: not stated on the page. Linux support and protocol: not stated.
- It also **controls fans**. For this project that part must never be used.
- PCIe slot adapter: "BENCHLAB PCI-E Slot Power Measurement Adapter ... available now at US$40" (WebSearch summary, https://benchlab.io/blogs/news/introducing-benchlab-pci-e-slot-power-measurement-adapter).

## Points that matter for this project

1. These meters measure **DC on the cables**, after the power supply. They do not see the supply's own loss, and they do not see the PCIe slot power unless a slot adapter is used.
2. The RTX 4090 already reports its **whole board** input power through NVML, "accurate to within +/- 5 watts" (`results/nvidia-smi-power-help.txt`). An inline meter on the 12V-2x6 cable would mostly repeat that number.
3. What an inline meter adds that nothing else gives: the **ATX 24-pin** (board, chipset, RAM through the board, fans, USB, SSD) and the **EPS 12 V** (the CPU **before** its voltage regulators, so the regulator loss is included).
4. Physical risk: every watt of the CPU and GPU passes through the meter's connectors and board. The 12V-2x6 connector of an RTX 4090 is known to be sensitive to seating. An extra connector pair in that path adds a place to fail. This is a question for Gova, not a software question.
5. Linux: a serial port (`/dev/ttyACM*` or `/dev/ttyUSB*`). The user must be in group `dialout` (`sudo usermod -aG dialout gova`: **needs root, not run**).
