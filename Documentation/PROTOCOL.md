# RS-Deck Bluetooth SPP protocol v1

Transport: Bluetooth Classic Serial Port Profile (SPP) over the Windows outgoing
Bluetooth COM port. Each frame is UTF-8 text terminated by LF (`\n`). CR is
ignored. The ESP32 discards frames longer than its fixed receive buffer limit.

All commands use protocol version `1`. Fields are separated by `|`.

## PC → ESP32

| Frame | Meaning |
|---|---|
| `HELLO_PC|1` | PC identifies protocol version. |
| `PING|1` | Heartbeat request. |
| `TIME|<unix_seconds>` | Set ESP32 system clock from the PC's Unix epoch time. |
| `PROFILE|<url_encoded_name>` | Set the OLED profile label. Profile names are percent-encoded UTF-8. |

## ESP32 → PC

| Frame | Meaning |
|---|---|
| `HELLO|1|RS-Deck` | Device identification and protocol version. |
| `PONG|1|<millis>` | Heartbeat response; proves the serial application link is alive. |
| `BTN|<1..8>|<0_or_1>` | Physical action button press and the active layer (0=normal, 1=shift). |
| `SHIFT|<0_or_1>` | Current layer state. |
| `PROFILE_NEXT` | Three-click Shift sequence; PC should advance profile and reset to normal layer. |
| `PROFILE_ACK|1|<url_encoded_name>` | Device accepted its display profile label. |

## Connection semantics

Windows pairing is not considered a live app connection. The Python application
opens a configured outgoing COM port and sends `PING|1`. It only shows Connected
after it receives `PONG|1|...` from the ESP32. If no heartbeat arrives for six
seconds, the app closes the port and retries. The firmware checks
`BluetoothSerial.hasClient()` for an active SPP client before sending data.

## Shift multi-click behavior

The Shift button is debounced in firmware. One click toggles the layer after the
430 ms multi-click window. If an action button is pressed during that window, a
single pending click is committed immediately before the action event is sent.
Three or more clicks inside the window request one profile advance and reset the
layer to Normal. Two clicks do nothing. Normal action buttons are reported only
on their debounced press edge.

## Time handling

The PC sends Unix epoch seconds. The firmware configures Bangladesh UTC+6 (POSIX `BDT-6`) as its local
time zone, so the OLED home screen shows the Bangladesh local clock. The ESP32
keeps counting after the PC disconnects; a fresh sync occurs on reconnection.
