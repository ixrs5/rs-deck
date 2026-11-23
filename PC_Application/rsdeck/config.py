"""Persistent RS-Deck settings."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

APP_NAME = "RS-Deck"
CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"


def _empty_actions() -> list[dict[str, str]]:
    return [{"type": "none", "value": ""} for _ in range(16)]


def default_config() -> dict[str, Any]:
    profiles = [
        {"id": "default", "name": "Default", "exe": "", "actions": _empty_actions()},
        {"id": "premiere", "name": "Adobe Premiere Pro", "exe": "Adobe Premiere Pro.exe", "actions": _empty_actions()},
        {"id": "photoshop", "name": "Adobe Photoshop", "exe": "Photoshop.exe", "actions": _empty_actions()},
        {"id": "obs", "name": "OBS Studio", "exe": "obs64.exe", "actions": _empty_actions()},
    ]
    return {
        "version": 1,
        "serial_port": "",
        "chrome_path": "",
        "auto_detect": True,
        "start_with_windows": False,
        "minimize_to_tray": True,
        "selected_profile": "default",
        "profiles": profiles,
    }


def _normalize_action(action: Any) -> dict[str, str]:
    if not isinstance(action, dict):
        return {"type": "none", "value": ""}
    action_type = str(action.get("type", "none"))
    if action_type not in {"none", "open", "url", "hotkey", "text"}:
        action_type = "none"
    return {"type": action_type, "value": str(action.get("value", ""))}


def normalize_config(data: Any) -> dict[str, Any]:
    defaults = default_config()
    if not isinstance(data, dict):
        return defaults
    result = defaults
    for key in ("serial_port", "chrome_path", "selected_profile"):
        if isinstance(data.get(key), str):
            result[key] = data[key]
    for key in ("auto_detect", "start_with_windows", "minimize_to_tray"):
        if isinstance(data.get(key), bool):
            result[key] = data[key]

    raw_profiles = data.get("profiles")
    if isinstance(raw_profiles, list) and raw_profiles:
        profiles: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_profiles:
            if not isinstance(raw, dict):
                continue
            profile_id = str(raw.get("id", "")).strip()
            name = str(raw.get("name", "")).strip()
            if not profile_id or not name or profile_id in seen:
                continue
            seen.add(profile_id)
            actions = raw.get("actions", [])
            if not isinstance(actions, list):
                actions = []
            normalized = [_normalize_action(a) for a in actions[:16]]
            normalized.extend(_empty_actions()[:16 - len(normalized)])
            profiles.append({
                "id": profile_id,
                "name": name,
                "exe": str(raw.get("exe", "")).strip(),
                "actions": normalized,
            })
        if profiles:
            if not any(p["id"] == "default" for p in profiles):
                profiles.insert(0, defaults["profiles"][0])
            result["profiles"] = profiles

    valid_ids = {p["id"] for p in result["profiles"]}
    if result["selected_profile"] not in valid_ids:
        result["selected_profile"] = "default"
    result["version"] = 1
    return result


def load_config() -> dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        data = default_config()
        save_config(data)
        return data
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return normalize_config(json.load(handle))
    except (OSError, json.JSONDecodeError, ValueError):
        # Keep a damaged file for recovery rather than silently overwriting it.
        damaged = CONFIG_PATH.with_suffix(".invalid.json")
        try:
            if not damaged.exists():
                CONFIG_PATH.replace(damaged)
        except OSError:
            pass
        data = default_config()
        save_config(data)
        return data


def save_config(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    normalized = normalize_config(data)
    fd, temporary_name = tempfile.mkstemp(prefix="config-", suffix=".tmp", dir=CONFIG_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, CONFIG_PATH)
    finally:
        try:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        except OSError:
            pass
