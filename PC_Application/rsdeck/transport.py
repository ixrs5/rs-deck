"""Bluetooth SPP serial transport with reconnect and heartbeat."""
from __future__ import annotations

import queue
import threading
import time
from typing import Optional

from PySide6.QtCore import QThread, Signal
import serial
from serial.tools import list_ports


class SerialWorker(QThread):
    connected = Signal(str)
    disconnected = Signal(str)
    frame_received = Signal(str)
    port_list_changed = Signal(list)
    diagnostic = Signal(str)

    def __init__(self, port_name: str = "", parent=None):
        super().__init__(parent)
        self._port_name = port_name
        self._port_lock = threading.Lock()
        self._outgoing: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._force_reconnect = threading.Event()
        self._serial: Optional[serial.Serial] = None
        self._is_connected = False
        self._last_pong = 0.0
        self._last_ping = 0.0
        self._last_hello = 0.0
        self._active_port = ""
        self._opened_at = 0.0

    def set_port(self, port_name: str) -> None:
        with self._port_lock:
            changed = port_name != self._port_name
            self._port_name = port_name
        if changed:
            self._force_reconnect.set()

    def send_line(self, line: str) -> None:
        if not line:
            return
        self._outgoing.put(line.rstrip("\r\n"))

    def request_reconnect(self) -> None:
        self._force_reconnect.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._force_reconnect.set()
        self.wait(2500)

    @staticmethod
    def available_ports() -> list[tuple[str, str]]:
        result = []
        for item in list_ports.comports():
            label = f"{item.device} — {item.description or item.hwid or 'Serial port'}"
            result.append((item.device, label))
        return result

    def _get_port_setting(self) -> str:
        with self._port_lock:
            return self._port_name

    def _candidate_ports(self) -> list[str]:
        selected = self._get_port_setting().strip()
        if selected:
            return [selected]
        # With no selected COM port, only probe ports Windows identifies as Bluetooth.
        return [p.device for p in list_ports.comports()
                if "bluetooth" in (p.description or "").lower()
                or "bluetooth" in (p.hwid or "").lower()]

    def _set_disconnected(self, reason: str) -> None:
        if self._is_connected:
            self._is_connected = False
            self.disconnected.emit(reason)

    def _close_serial(self, reason: str = "Connection closed") -> None:
        self._set_disconnected(reason)
        if self._serial is not None:
            try:
                self._serial.close()
            except (serial.SerialException, OSError):
                pass
        self._serial = None
        self._active_port = ""

    def _open_serial(self) -> bool:
        candidates = self._candidate_ports()
        if not candidates:
            return False
        for port in candidates:
            if self._stop_event.is_set() or self._force_reconnect.is_set():
                return False
            try:
                link = serial.Serial(port=port, baudrate=115200, timeout=0.12,
                                     write_timeout=0.4, exclusive=None)
                self._serial = link
                self._active_port = port
                self._opened_at = time.monotonic()
                self._last_pong = 0.0
                self._last_ping = 0.0
                self._last_hello = 0.0
                self.diagnostic.emit(f"Opened {port}; waiting for RS-Deck handshake")
                self._write_line("HELLO_PC|1")
                return True
            except (serial.SerialException, OSError) as exc:
                self.diagnostic.emit(f"Could not open {port}: {exc}")
        return False

    def _write_line(self, line: str) -> None:
        if self._serial is None or not self._serial.is_open:
            return
        try:
            self._serial.write((line + "\n").encode("utf-8"))
        except (serial.SerialException, OSError) as exc:
            self.diagnostic.emit(f"Serial write failed: {exc}")
            self._close_serial("Serial write failed")

    def run(self) -> None:
        rx_buffer = bytearray()
        last_scan_signal = 0.0
        while not self._stop_event.is_set():
            if self._force_reconnect.is_set():
                self._force_reconnect.clear()
                self._close_serial("Bluetooth port selection changed")
                rx_buffer.clear()

            if self._serial is None:
                now = time.monotonic()
                if now - last_scan_signal > 2.0:
                    self.port_list_changed.emit(self.available_ports())
                    last_scan_signal = now
                self._open_serial()
                if self._serial is None:
                    self._stop_event.wait(1.5)
                    continue

            try:
                chunk = self._serial.read(128)
                if chunk:
                    rx_buffer.extend(chunk)
                    if len(rx_buffer) > 2048:
                        rx_buffer.clear()
                        self.diagnostic.emit("Discarded oversized protocol input")
                    while b"\n" in rx_buffer:
                        raw, _, rest = rx_buffer.partition(b"\n")
                        rx_buffer = bytearray(rest)
                        frame = raw.decode("utf-8", errors="replace").strip("\r\x00 ")
                        if not frame:
                            continue
                        self.frame_received.emit(frame)
                        if frame.startswith("PONG|1|") or frame == "PONG|1":
                            self._last_pong = time.monotonic()
                            if not self._is_connected:
                                self._is_connected = True
                                self.connected.emit(self._active_port)
                        elif frame.startswith("HELLO|1|"):
                            self._last_hello = time.monotonic()

                now = time.monotonic()
                while True:
                    try:
                        outgoing = self._outgoing.get_nowait()
                    except queue.Empty:
                        break
                    self._write_line(outgoing)
                    if self._serial is None:
                        break

                if self._serial is not None and now - self._last_ping >= 1.4:
                    self._write_line("PING|1")
                    self._last_ping = now

                if self._serial is not None and not self._is_connected and now - self._opened_at > 6.0:
                    self._close_serial("RS-Deck did not answer the connection handshake")
                    rx_buffer.clear()
                elif self._is_connected and now - self._last_pong > 6.0:
                    self._close_serial("No heartbeat from RS-Deck")
                    rx_buffer.clear()
                elif self._serial is not None and not self._serial.is_open:
                    self._close_serial("Bluetooth serial port closed")
                    rx_buffer.clear()
            except (serial.SerialException, OSError) as exc:
                self.diagnostic.emit(f"Bluetooth serial error: {exc}")
                self._close_serial("Bluetooth connection lost")
                rx_buffer.clear()

        self._close_serial("Application is exiting")
