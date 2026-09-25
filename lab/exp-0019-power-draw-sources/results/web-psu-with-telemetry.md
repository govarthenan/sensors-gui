# A power supply that reports its own power (only if the PSU were changed)

- Date accessed: 2026-09-25
- Command: `curl -sfL -o corsair-psu.rst https://raw.githubusercontent.com/torvalds/linux/v7.0/Documentation/hwmon/corsair-psu.rst`
- Source: Linux kernel v7.0, Documentation/hwmon/corsair-psu.rst. Verbatim lines below.

```
Description
-----------

This driver implements the sysfs interface for the Corsair PSUs with a HID protocol
interface of the HXi and RMi series.
These power supplies provide access to a micro-controller with 2 attached
temperature sensors, 1 fan rpm sensor, 4 sensors for volt levels, 4 sensors for
power usage and 4 sensors for current levels and additional non-sensor information
like uptimes.

Sysfs entries
-------------

=======================	========================================================
curr1_input		Total current usage
curr2_input		Current on the 12v psu rail
curr2_crit		Current max critical value on the 12v psu rail
curr3_input		Current on the 5v psu rail
curr3_crit		Current max critical value on the 5v psu rail
curr4_input		Current on the 3.3v psu rail
curr4_crit		Current max critical value on the 3.3v psu rail
fan1_input		RPM of psu fan
in0_input		Voltage of the psu ac input
in1_input		Voltage of the 12v psu rail
in1_crit		Voltage max critical value on the 12v psu rail
in1_lcrit		Voltage min critical value on the 12v psu rail
in2_input		Voltage of the 5v psu rail
in2_crit		Voltage max critical value on the 5v psu rail
in2_lcrit		Voltage min critical value on the 5v psu rail
in3_input		Voltage of the 3.3v psu rail
in3_crit		Voltage max critical value on the 3.3v psu rail
in3_lcrit		Voltage min critical value on the 3.3v psu rail
power1_input		Total power usage
power2_input		Power usage of the 12v psu rail
power3_input		Power usage of the 5v psu rail
power4_input		Power usage of the 3.3v psu rail
pwm1			PWM value, read only
...
Usage Notes
-----------

It is an USB HID device, so it is auto-detected, supports hot-swapping and
several devices at once.

Flickering values in the rail voltage levels can be an indicator for a failing
PSU. Accordingly to the default automatic fan speed plan the fan starts at about
30% of the wattage rating. If this does not happen, a fan failure is likely. The
driver also provides some additional useful values via debugfs, which do not fit
into the hwmon class.
```

## What this means

1. A Corsair HXi or RMi supply is read by an **in-kernel** hwmon driver. The application's hwmon collector would find `power1_input` ("Total power usage") with no change to the code.
2. The values are the supply's **DC output** side, measured by its own micro-controller. Whether `power1_input` includes the supply's own loss (AC input) is not stated in these lines: **not established**. Accuracy is not stated: **not established**.
3. The driver sends HID requests to the supply's micro-controller to get each value. The **kernel driver** does this, as `spd5118` does for the DIMMs (ADR 0011 section 2).
4. This route needs a **new power supply**. The NZXT C1200 on this machine has no such link (see `web-nzxt-c1200.md`). It is listed for completeness, not as a recommendation.
