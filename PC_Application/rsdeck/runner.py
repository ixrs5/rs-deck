"""Windows action execution for RS-Deck."""
from __future__ import annotations

import ctypes
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable


def find_chrome(configured_path: str = "") -> str:
    candidates = []
    if configured_path:
        candidates.append(configured_path)
    try:
        import winreg
        for key_path in (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
        ):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    candidates.append(winreg.QueryValue(key, None))
            except OSError:
                pass
    except ImportError:
        pass
    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    candidates.extend([
        str(Path(local) / "Google/Chrome/Application/chrome.exe"),
        str(Path(program_files) / "Google/Chrome/Application/chrome.exe"),
        str(Path(program_files_x86) / "Google/Chrome/Application/chrome.exe"),
    ])
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


# Win32 virtual-key table used by the hotkey editor.
_VK = {
    "CTRL": 0x11, "CONTROL": 0x11, "SHIFT": 0x10, "ALT": 0x12, "WIN": 0x5B,
    "ENTER": 0x0D, "RETURN": 0x0D, "ESC": 0x1B, "ESCAPE": 0x1B,
    "TAB": 0x09, "SPACE": 0x20, "BACKSPACE": 0x08, "DELETE": 0x2E,
    "DEL": 0x2E, "INSERT": 0x2D, "HOME": 0x24, "END": 0x23,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22, "UP": 0x26, "DOWN": 0x28,
    "LEFT": 0x25, "RIGHT": 0x27, "CAPSLOCK": 0x14,
}
for _i in range(1, 25):
    _VK[f"F{_i}"] = 0x70 + _i - 1


def _virtual_key(token: str) -> int:
    token = token.strip().upper()
    if token in _VK:
        return _VK[token]
    if len(token) == 1:
        value = ord(token)
        if 48 <= value <= 57 or 65 <= value <= 90:
            return value
    raise ValueError(f"Unsupported key: {token}")


def send_hotkey(spec: str) -> None:
    if os.name != "nt":
        raise OSError("Hotkeys are supported on Windows only.")
    tokens = [part.strip() for part in spec.replace("+", ",").split(",") if part.strip()]
    if not tokens:
        raise ValueError("Enter a shortcut such as CTRL+SHIFT+S or F5.")
    keys = [_virtual_key(token) for token in tokens]
    user32 = ctypes.windll.user32
    # Press in listed order, release in reverse order.
    pressed: list[int] = []
    try:
        for vk in keys:
            user32.keybd_event(vk, 0, 0, 0)
            pressed.append(vk)
    finally:
        for vk in reversed(pressed):
            user32.keybd_event(vk, 0, 0x0002, 0)


def send_unicode_text(text: str) -> None:
    """Type Unicode via SendInput using UTF-16 code units (no clipboard changes)."""
    if os.name != "nt":
        raise OSError("Text injection is supported on Windows only.")

    ULONG_PTR = ctypes.c_size_t
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ULONG_PTR)]
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong), ("dwExtraInfo", ULONG_PTR)]
    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort),
                    ("wParamH", ctypes.c_ushort)]
    class INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]
    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", ctypes.c_ulong), ("u", INPUT_UNION)]

    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004
    user32 = ctypes.windll.user32
    encoded = text.encode("utf-16-le", errors="surrogatepass")
    for offset in range(0, len(encoded), 2):
        code_unit = encoded[offset] | (encoded[offset + 1] << 8)
        down = INPUT(type=1, ki=KEYBDINPUT(0, code_unit, KEYEVENTF_UNICODE, 0, 0))
        up = INPUT(type=1, ki=KEYBDINPUT(0, code_unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))
        if user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT)) != 1:
            raise OSError("Windows could not send the text input.")
        user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))


def execute_action(action: dict, chrome_path: str = "", error_callback: Callable[[str], None] | None = None) -> bool:
    action_type = str(action.get("type", "none"))
    value = str(action.get("value", ""))
    try:
        if action_type == "none" or not value:
            return False
        if action_type == "open":
            target = Path(value)
            if not target.exists():
                raise FileNotFoundError(f"The selected file or application does not exist:\n{value}")
            if os.name == "nt":
                os.startfile(str(target))  # type: ignore[attr-defined]
            else:
                subprocess.Popen([str(target)])
        elif action_type == "url":
            url = value.strip()
            if not url.lower().startswith(("http://", "https://")):
                url = "https://" + url
            chrome = find_chrome(chrome_path)
            if not chrome:
                raise FileNotFoundError("Google Chrome was not found. Set its path in RS-Deck Settings.")
            subprocess.Popen([chrome, url], close_fds=True)
        elif action_type == "hotkey":
            send_hotkey(value)
        elif action_type == "text":
            send_unicode_text(value)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
        return True
    except Exception as exc:
        if error_callback:
            error_callback(str(exc))
        return False
