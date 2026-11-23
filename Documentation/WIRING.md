# RS-Deck wiring reference

Keep the existing wiring. GPIO assignments are fixed in the firmware.

## OLED

```text
SSD1306 OLED              ESP32 Dev Module
-------------             ----------------
GND  -------------------- GND
VCC  -------------------- 3V3
SDA  -------------------- GPIO 21
SCL  -------------------- GPIO 22

I2C address: 0x3C (firmware default)
Display: 128 x 64, SSD1306
```

## Nine push buttons

Each tactile switch has two electrical terminals. With a four-leg switch, the
two legs on one internal side are the same terminal; the opposite pair is the
other terminal. Connect one terminal to its GPIO and the other to the shared GND.

```text
GPIO 13  ----[ Button 1 ]----+
GPIO 14  ----[ Button 2 ]----+
GPIO 18  ----[ Button 3 ]----+
GPIO 19  ----[ Button 4 ]----+
GPIO 23  ----[ Button 5 ]----+
GPIO 25  ----[ Button 6 ]----+---- COMMON GND BUS ---- ESP32 GND
GPIO 26  ----[ Button 7 ]----+
GPIO 27  ----[ Button 8 ]----+
GPIO 32  ----[ Shift    ]----+
```

| Button | GPIO | Firmware role |
|---:|---:|---|
| 1 | 13 | Normal layer action 1 / Shift layer action 1 |
| 2 | 14 | Normal layer action 2 / Shift layer action 2 |
| 3 | 18 | Normal layer action 3 / Shift layer action 3 |
| 4 | 19 | Normal layer action 4 / Shift layer action 4 |
| 5 | 23 | Normal layer action 5 / Shift layer action 5 |
| 6 | 25 | Normal layer action 6 / Shift layer action 6 |
| 7 | 26 | Normal layer action 7 / Shift layer action 7 |
| 8 | 27 | Normal layer action 8 / Shift layer action 8 |
| 9 | 32 | Shift layer toggle / triple-click profile next |

The firmware sets all nine GPIOs to `INPUT_PULLUP`. No external pull-up resistors
are required. A pressed button reads LOW; a released button reads HIGH.

## Battery and regulated supply

```text
Rechargeable cell (+)  -------- B+ on charging / boost module
Rechargeable cell (-)  -------- B- on charging / boost module

Verified regulated 5V (+) ----- ESP32 VIN / 5V
Verified regulated (-) -------- ESP32 GND
```

This is the requested topology, not a substitute for checking the exact module.
Confirm its printed labels, battery compatibility, output polarity and measured
voltage with a multimeter before connecting it to the ESP32. Do not assume an
output is 5V without measuring it.
