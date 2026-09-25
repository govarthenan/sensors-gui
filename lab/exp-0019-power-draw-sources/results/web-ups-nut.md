# UPS power reporting through NUT

- Date accessed: 2026-09-25
- Tools: `curl -sfL` (raw file, verbatim) and WebFetch / WebSearch (a summarising tool; text from it is marked "summary", and may be paraphrased).

## 1. NUT variable definitions — verbatim

- Command: `curl -sfL -o cmdvartab https://raw.githubusercontent.com/networkupstools/nut/master/data/cmdvartab && grep -n -E '^VARDESC (ups\.load|ups\.realpower|...)' cmdvartab`
- Source: https://raw.githubusercontent.com/networkupstools/nut/master/data/cmdvartab (NUT master branch)

```
22:VARDESC ups.load "Load on UPS (percent of full)"
36:VARDESC ups.power "Current value of apparent power (VA)"
37:VARDESC ups.power.nominal "UPS power rating (VA)"
38:VARDESC ups.realpower "Current value of real power (W)"
39:VARDESC ups.realpower.nominal "UPS real power rating (W)"
47:VARDESC input.voltage "Input voltage (V)"
101:VARDESC input.realpower "Current sum value of all (ePDU) phases real power (W)"
110:VARDESC output.current "Output current (A)"
```

## 2. Not every UPS reports watts — summary

- Source: https://github.com/netdata/netdata/issues/16619 (opened 2023-12-15)
- Summary of the fetch: the Eaton Ellipse PRO 850 reports `ups.realpower` (43 W in the example) and does **not** report `ups.realpower.nominal`. The issue proposes to use `ups.realpower` first, and to fall back to `ups.load` × `ups.realpower.nominal` when a UPS gives only a load percent.

- Source: WebSearch "NUT usbhid-ups APC Back-UPS Pro ups.realpower ups.load", 2026-09-25. Summary: APC Back-UPS units on `usbhid-ups` show `ups.load` (for example 7 %, 53 %) and `ups.realpower.nominal` (for example 720 W). Links in the result: https://github.com/networkupstools/nut/issues/2222, https://github.com/networkupstools/nut/issues/547, https://github.com/networkupstools/nut/issues/3025.

## What this means for this project

1. A UPS that gives only `ups.load` in whole percent gives a **coarse** figure: with a 900 W rating, one step is 9 W. The accuracy of the load sensor is not published in these sources: **not established**.
2. A UPS that gives `ups.realpower` gives watts directly. Which models do is model by model; check the NUT hardware list before a purchase.
3. The UPS measures its **output**, which is the AC input of the PC power supply, plus anything else plugged into the UPS (the monitors, if they are on it).
4. Read path: `usbhid-ups` driver + `upsd` + `upsc <ups>`. NUT is **not installed** on this machine (`results/acpi-ipmi-upower.txt`); installing it needs root (`sudo apt install nut`) and a udev rule.
5. Does it write? The driver reads HID reports from the UPS (a GET_REPORT request asks for a value). NUT also has **instant commands** (`upscmd`: beeper, test, shutdown, load.off) that DO tell the UPS to act. For this project the NUT user must be configured with no command rights, and the application must only call `upsc` (read). The UPS is external hardware, not this machine's hardware, but it holds the machine's power.
