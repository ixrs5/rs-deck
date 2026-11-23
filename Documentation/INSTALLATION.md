# RS-Deck installation guide

## 1. Confirm the ESP32 chip before using Bluetooth Classic

The firmware uses Bluetooth Classic Serial Port Profile (SPP). This is supported
by the **original ESP32**. The Arduino IDE label `ESP32 Dev Module` is not enough
to identify the silicon. Read the marking on the metal RF shield of your module.
The common ESP32-WROOM-32 module is the intended target. ESP32-S2, ESP32-S3,
ESP32-C3, ESP32-C6 and other newer variants do not provide the same Classic SPP
support in the standard Arduino `BluetoothSerial` library.

If your board is not an original ESP32, stop before uploading; this project would
need a different transport and cannot use the supplied Classic SPP firmware as-is.

## 2. Wiring — keep the existing connections

### OLED (SSD1306, 128×64, I2C)

| OLED | ESP32 |
|---|---|
| GND | GND |
| VCC | 3.3V |
| SDA | GPIO 21 |
| SCL | GPIO 22 |

The firmware checks I2C address `0x3C`. If your display uses a different address,
change `OLED_ADDRESS` near the top of `RS_Deck.ino` only after verifying it.

### Buttons

Each switch is wired between its GPIO and common GND. Firmware uses
`INPUT_PULLUP`, so pressed is LOW and released is HIGH.

| Physical button | Firmware role | GPIO |
|---|---|---:|
| 1 | Normal action 1 | 13 |
| 2 | Normal action 2 | 14 |
| 3 | Normal action 3 | 18 |
| 4 | Normal action 4 | 19 |
| 5 | Normal action 5 | 23 |
| 6 | Normal action 6 | 25 |
| 7 | Normal action 7 | 26 |
| 8 | Normal action 8 | 27 |
| 9 | Shift / profile control | 32 |

The two legs on each internally connected side of a four-leg tactile switch are
the same electrical terminal. Connect one terminal to the GPIO and the opposite
terminal to GND.

### Battery / boost module check

The supplied project brief describes battery positive to `B+`, battery negative
to `B-`, regulated 5V positive to ESP32 `VIN/5V`, and regulated negative to GND.
Before connecting the ESP32:

1. Read the exact labels and polarity printed on your charging/boost board.
2. Confirm the battery chemistry and module are compatible with one another.
3. With the module powered, measure its output with a multimeter.
4. Only connect to VIN/5V after confirming the measured output is the expected
   regulated voltage and the polarity is correct. Never infer the voltage from
   the presence of a boost converter alone.
5. Avoid powering the ESP32 from the battery boost output and USB at the same
   time unless the exact development board documentation confirms that this
   is safe. Disconnect the battery power path while programming if unsure.

## 3. Install ESP32 firmware

1. Install Arduino IDE 2.x from the official Arduino website.
2. In Arduino IDE, install the Espressif `esp32` board package using Boards
   Manager. Use a current stable 3.x release where `BluetoothSerial` is enabled.
3. Open Library Manager and install:
   - `Adafruit GFX Library`
   - `Adafruit SSD1306`
   - Dependencies requested by Library Manager, including Adafruit BusIO.
4. Open `ESP32_Firmware/RS_Deck.ino`.
5. Select **Tools → Board → esp32 → ESP32 Dev Module**.
6. Select the correct USB COM port under **Tools → Port**.
7. Click Upload. The compile-time checks intentionally stop the build if
   Bluetooth Classic SPP is not available for the selected chip/build.
8. Open Serial Monitor at 115200 baud for diagnostic messages if needed.

At power-up, the OLED should display centered `RS`, fading in, holding briefly,
and fading out in about 1.65 seconds. The ESP32 firmware then shows the home
screen. The startup effect runs once from `setup()`; reconnecting Bluetooth does
not replay it. The loop continues scanning buttons and servicing Bluetooth while
the display effect runs.

## 4. Pair RS-Deck with Windows

1. Turn on the RS-Deck device.
2. On Windows 10/11, open **Settings → Bluetooth & devices → Add device → Bluetooth**.
3. Choose `RS-Deck` and complete pairing if Windows asks.
4. Pairing alone is not the live application connection. The PC application must
   open the Bluetooth Serial Port Profile COM port to create an SPP session.
5. Open the classic Control Panel Bluetooth / Devices and Printers interface,
   open the paired RS-Deck device properties, and inspect the **Services** or
   **COM Ports** tab. Windows wording and exact location can vary by driver.
6. Find the **outgoing** Bluetooth Serial Port / Standard Serial over Bluetooth
   link. Note its COM number (for example, COM7). Do not select an incoming port.
7. If Windows does not expose an SPP serial service or outgoing COM port, check
   that the module is an original ESP32, remove and pair the device again, and
   inspect Device Manager for Bluetooth serial ports.

Windows may show a paired device as paired even when no SPP application session
is active. The RS-Deck app's `Connected` status is based on a successful serial
heartbeat reply from the ESP32, not merely on the Windows pairing record.

## 5. Install and launch the Windows application

Requirements: Windows 10/11 and Python 3.11 or newer.

1. Install Python from the official Python website. During setup, enable
   **Add Python to PATH**.
2. Open the `PC_Application` folder.
3. Double-click `run_rs_deck.bat`. It installs packages listed in
   `requirements.txt` and starts the desktop app.
4. In the Bluetooth Serial Link selector, choose the outgoing COM port noted
   above. You can also leave Auto-detect selected if Windows labels the port as
   Bluetooth.
5. Wait for the status at the top to change to `Connected`. This only happens
   after the device answers the app's heartbeat.
6. Minimize the window to the system tray. The connection worker remains active.
   Right-click the tray icon and choose Open RS-Deck to restore it.
7. Enable **Start RS-Deck with Windows** in App Settings if desired. This adds a
   per-user Windows startup entry. You can turn it off from the same checkbox.

To build a standalone folder containing `RS-Deck.exe`, run
`build_windows.bat`. PyInstaller output is placed under `PC_Application/dist/`.
The standalone build has not been physically tested on this system; run the
source launcher first and validate it before building.

## 6. Configure the 16 actions

The app has four starter profiles: Default, Adobe Premiere Pro, Adobe Photoshop
and OBS Studio. Each profile has 16 assignments. Scroll the main content area to
reach all 16 cards and App Settings at the bottom. The vertical scrollbar is
always visible; the mouse wheel scrolls the page and the scrollbar thumb can be
draggable.

For each action card, choose one of:

- **Open app / file** — Browse to an EXE or file. The selected file must exist.
- **Open URL in Chrome** — Enter a website, with or without `https://`. This
  explicitly launches Google Chrome; it does not use the Windows default browser.
  If Chrome is not auto-detected, browse to `chrome.exe` in App Settings.
- **Send hotkey** — Use forms such as `CTRL+S`, `CTRL+SHIFT+S`, `ALT+F4`,
  `CTRL+ALT+F1`, or `F5`.
- **Type text** — Enter text to type into the currently focused application.
  Unicode is sent through Windows keyboard input and the clipboard is not replaced.

Changes save automatically to `%APPDATA%\RS-Deck\config.json`. Use Export backup
and Restore backup at the bottom to move your profiles to another Windows account
or computer.

### Profiles and automatic detection

- Create, rename and delete profiles using the profile controls.
- The Default profile cannot be deleted.
- Enter the target executable name for each app profile, e.g. `obs64.exe`.
- With Auto-detect enabled, the foreground Windows application selects the
  matching profile. If no configured executable is active, Default is selected.
- Choosing a profile manually turns Auto-detect off so that your selection does
  not immediately get overwritten. Enable Auto-detect again when you want it back.
- Three quick clicks of the physical Shift button asks the PC app to move to the
  next profile in the profile list and resets the layer to Normal. A single click
  toggles the Shift layer. Two clicks have no action.

## 7. First test sequence

1. Power on RS-Deck. Confirm the OLED displays the `RS` fade animation once.
2. Wait for the OLED home screen. Before the PC syncs time it may show `--:--:--`
   and `Not synced`.
3. Launch the PC app and select the outgoing SPP COM port.
4. Confirm the app says `Connected` and the OLED reports BT on. The PC sends its
   Unix time; the ESP32 applies Bangladesh UTC+6 for the date/time screen.
5. Assign a harmless test action to Normal Button 1, such as opening a text file,
   then press Button 1. The configured action should run.
6. Press Shift once and wait for the click timing to settle (or press a normal
   button immediately after release); the app layer indicator and OLED should
   show SHIFT.
7. Press Button 2. The Shift-layer Button 2 assignment should run.
8. Press Shift three times quickly. The profile should advance once and the layer
   should return to Normal. The app profile selector and OLED profile name update.
9. With Auto-detect enabled, activate the configured Premiere, Photoshop or OBS
   window. The matching profile should load. Return to an unrelated app and
   Default should load.
10. Turn RS-Deck off and on or close/reopen the PC app to confirm automatic
    reconnection. The boot animation should run only on ESP32 startup.

## 8. Troubleshooting

**RS-Deck does not appear in Bluetooth discovery**
- Check that the module is an original ESP32 and the firmware uploaded cleanly.
- Check Serial Monitor for `Bluetooth SPP started: RS-Deck`.
- Power-cycle the ESP32 and refresh Windows Bluetooth discovery.

**Windows says Paired, but RS-Deck app is not Connected**
- Pairing is not an SPP connection. Choose the outgoing Bluetooth serial COM port.
- Make sure no other terminal or app has the COM port open.
- Confirm the port is not an incoming COM port.
- Try removing the paired device from Windows and pair it again.

**No COM port appears**
- Check the Bluetooth adapter and Windows Bluetooth driver.
- Open Device Manager and inspect Ports (COM & LPT) and Bluetooth categories.
- Confirm the device advertises the Serial Port Profile. Classic SPP is not available
  on ESP32-S2/S3/C3 modules through the standard Arduino library.

**OLED stays blank**
- Confirm GND, 3.3V, SDA=21 and SCL=22.
- Confirm the display is SSD1306 and check whether its I2C address is 0x3C.
- Open Serial Monitor and check for `OLED init failed`.

**Time does not appear**
- The clock is synchronized by the Windows app after the SPP heartbeat succeeds.
- Reconnect the app. The ESP32 keeps running its clock after the PC disconnects.

**Hotkey goes to the wrong window**
- Minimize RS-Deck to the tray and make the intended software the foreground window.
- Windows may restrict input injection into elevated applications. Run both apps
  at the same privilege level; do not run RS-Deck elevated unless necessary.

**Unicode or text is not accepted by a target application**
- Some programs use custom text input fields or ignore synthetic keyboard events.
  Test in Notepad first, then test the target program.

## 9. What has and has not been tested

The delivered source has been reviewed for matching GPIO definitions, protocol
agreement, and Python syntax. This environment does not have access to your
ESP32 board, Windows Bluetooth adapter, OLED, buttons or the Windows desktop, so
it cannot verify physical pairing, firmware upload/compilation on your exact
board, COM-port behavior, real key injection, system-tray operation or screen
layout on your laptop. Complete the first-test sequence above and report any
exact error text if something fails.

## 10. Optional software self-check

From a Command Prompt opened inside `PC_Application`, run:

```bat
py -3 -m unittest discover -s tests -v
```

This checks local configuration normalization and shortcut-key token handling.
It does not test the physical Bluetooth connection or Windows input injection.
