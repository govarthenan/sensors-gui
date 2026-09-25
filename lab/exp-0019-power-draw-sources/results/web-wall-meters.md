# Wall (AC) meters that Linux can read over the network: smart plugs

- Date accessed: 2026-09-25
- Tool: WebFetch / WebSearch (summarising tools). Text in quotes is what the tool returned; check it at the URL before use.

## 1. Shelly Plus Plug UK (Type G / BS 1363)

- URL: https://kb.shelly.cloud/knowledge-base/shelly-plus-plug-uk
- Returned: "Max switching voltage AC: 260 V", "Max switching current AC: 13 A", "Power and energy meters: Yes", "Voltmeter: Yes", "Ammeter: Yes", "Wi-Fi protocol: 802.11 b/g/n", "Bluetooth Protocol: 4.2", "1 BS 1363 (Type-G) plug" and "1 BS 1363 (Type-G) socket"; "an embedded Web Interface which can be used to monitor and control the device"; supports "MQTT" and "Webhooks (URL actions)".
- Accuracy: the official page gave no figure. A WebSearch result (reseller and review pages, not the maker) said "±2%" and one test "400W load ... 397W compared to a Fluke ... 401W". Links: https://pluggedin.solar/blog/shelly-plus-plug-uk-review , https://www.amazon.co.uk/Shelly-Pus-Plug-UK-Bluetooth/dp/B0BV37M88W . **Accuracy not established from the maker.**
- Price: not checked.

## 2. Shelly Gen2 local API — Switch.GetStatus

- URL: https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch/
- Returned: apower — "Last measured instantaneous active power (in Watts)"; voltage — "Last measured voltage in Volts"; current — "Last measured current in Amperes"; freq — "Last measured network frequency in Hz"; pf — "Last measured power factor"; plus the energy counter `aenergy`.
- Call form returned: `http://192.168.33.1/rpc/Switch.GetStatus?id=0` (192.168.33.1 is the plug's own access-point address; on the home network it is the plug's LAN address).
- Authentication: not stated in the fetched section. **Not established.**

## 3. Tasmota plugs (flashed third-party plugs)

- URL: https://tasmota.github.io/docs/Power-Monitoring-Calibration/
- Returned: "You need to calibrate your power monitoring device as correct measurements are influenced by hardware and timing differences." Chips named: BL0937, HLW8012, CSE7766. "Power monitoring chips such as HLW8032 (Blitzwolf SHP5) and CSE7766 occasionally report invalid power measurements for load values below 5W." No accuracy figure.

## 4. TP-Link Tapo P110 (local KLAP protocol)

- Source: WebSearch "Tapo P110 local API python-kasa KLAP get_energy_usage current_power", 2026-09-25. Summary: python-kasa supports the P110, but there are open issues with the energy module on some firmware versions (https://github.com/python-kasa/python-kasa/issues/1243 , https://github.com/python-kasa/python-kasa/issues/1511). Local access uses the KLAP protocol with the TP-Link account credentials.

## Points that matter for this project

1. A smart plug measures **AC at the wall**: the whole PC including the power supply's own loss, plus anything else on the same plug.
2. Reading it is an **HTTP GET to another device on the network**. It sends nothing to this machine's hardware. But it is a request to a device that **holds this machine's power**: the same API has `Switch.Set`, which turns the socket off. The application must call only `Switch.GetStatus`, and the plug should be set so that it cannot switch the PC off by itself (power-on default ON, no schedules, no cloud control, a power limit well above the PC's peak). If it switched off under load, that is an unsafe shutdown of the kind already counted in Q10.
3. Rating: 13 A at 230 V is about 3 kW. The PC's supply is 1200 W. The rating is enough; the transient peaks of an RTX 4090 are short and are not the continuous rating.
4. No root is needed on this machine: an HTTP client in user space.
