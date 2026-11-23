# RS-Deck validation report

## Source checks completed in this build session

- Firmware pin table matches the requested map: OLED SDA 21 / SCL 22; buttons
  13, 14, 18, 19, 23, 25, 26, 27; Shift 32.
- Firmware uses INPUT_PULLUP and interprets active-low switches.
- Startup logo is `RS`, drawn and faded by the ESP32 SSD1306 firmware. Its timing
  is 600 ms fade-in + 400 ms hold + 650 ms fade-out (1.65 seconds nominal).
- Startup animation is not called from Bluetooth connect/reconnect handling.
- Button scanning, Bluetooth servicing and animation updates all run from the
  non-blocking loop; the animation does not use `delay()`.
- Firmware and PC application agree on newline-delimited protocol v1 frame names.
- PC app gates its Connected state on a received `PONG|1|...` heartbeat.
- PC app stores profiles and actions under `%APPDATA%\RS-Deck\config.json`.
- Python files passed `compileall` syntax checks.
- Five automated unit tests passed for default profiles, 16-action normalization, and hotkey token parsing.

## Not physically verified here

- Arduino firmware compilation against the exact ESP32 board package version.
- Actual Bluetooth pairing and SPP COM-port creation in Windows.
- Actual PC ↔ ESP32 reconnect behavior on the user's adapter and board.
- OLED contrast fade appearance on the physical 128×64 panel.
- Real push-button debounce and triple-click feel on the enclosure.
- Windows hotkey/text injection into Premiere Pro, Photoshop and OBS.
- Tray/startup behavior and screen scrolling on the user's Windows laptop.

The Qt desktop UI could not be launched in this build container because PySide6
and pyserial are not installed here; the launcher installs them on Windows. These
checks require the target hardware and Windows environment. Use the installation
checklist and keep the first tests harmless (for example, open Notepad or a text
file before assigning editing shortcuts).
