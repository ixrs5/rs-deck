"""RS-Deck Windows desktop interface."""
from __future__ import annotations

import ctypes
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QFileDialog, QScrollArea, QFrame,
    QCheckBox, QMessageBox, QInputDialog, QSystemTrayIcon, QMenu, QStyle,
    QSizePolicy, QSpacerItem,
)

from .config import save_config
from .runner import execute_action
from .transport import SerialWorker


STYLE = r"""
QWidget { background: #0b0d12; color: #e9edf5; font-family: "Segoe UI"; font-size: 10pt; }
QMainWindow { background: #0b0d12; }
QFrame#topCard, QFrame#panel, QFrame#assignmentCard { background: #121722; border: 1px solid #242d3c; border-radius: 14px; }
QFrame#assignmentCard { background: #111722; }
QLabel#muted { color: #8995a8; }
QLabel#brand { font-size: 22pt; font-weight: 700; letter-spacing: 1px; color: #f5f7fb; }
QLabel#eyebrow { color: #7f8da5; font-size: 8pt; font-weight: 700; letter-spacing: 1.5px; }
QLabel#connectionStatus { color: #f0b95b; font-weight: 700; padding: 7px 12px; border-radius: 10px; background: #2b2416; }
QLabel#connectionStatus[connected="true"] { color: #67e5a4; background: #142b23; }
QLabel#layerStatus { color: #aeb9ca; padding: 5px 10px; border-radius: 9px; background: #1c2533; }
QPushButton { background: #202a39; border: 1px solid #344258; color: #eff3f9; padding: 9px 13px; border-radius: 9px; font-weight: 600; }
QPushButton:hover { background: #2a374a; border-color: #526581; }
QPushButton:pressed { background: #18202c; }
QPushButton#primary { background: #d5e4ff; color: #111827; border: 0; }
QPushButton#primary:hover { background: #edf4ff; }
QPushButton#danger { color: #ff9c9c; border-color: #5b3038; background: #27191e; }
QLineEdit, QComboBox { background: #0d121b; border: 1px solid #303b4d; border-radius: 8px; padding: 8px 10px; color: #e9edf5; selection-background-color: #456b9d; min-height: 20px; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #8fb6ed; }
QComboBox::drop-down { border: 0; width: 23px; }
QComboBox QAbstractItemView { background: #151d2a; color: #f0f3f8; selection-background-color: #30445f; border: 1px solid #35445a; }
QCheckBox { spacing: 8px; color: #c7d0df; }
QCheckBox::indicator { width: 17px; height: 17px; }
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: #111722; width: 12px; margin: 2px 2px 2px 2px; border-radius: 6px; }
QScrollBar::handle:vertical { background: #46556b; min-height: 34px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #7187a5; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QGroupBox { border: 1px solid #242d3c; border-radius: 12px; margin-top: 10px; padding-top: 12px; font-weight: 700; color: #bdc9da; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
"""

ACTION_OPTIONS = [
    ("None", "none"),
    ("Open app / file", "open"),
    ("Open URL in Chrome", "url"),
    ("Send hotkey", "hotkey"),
    ("Type text", "text"),
]


def active_window_executable() -> str:
    """Return the executable owning the foreground window (Windows only)."""
    if os.name != "nt":
        return ""
    try:
        import psutil
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return psutil.Process(pid.value).name().lower()
    except Exception:
        return ""


class MainWindow(QMainWindow):
    def __init__(self, config: dict, transport: SerialWorker, app):
        super().__init__()
        self.config = config
        self.transport = transport
        self.qt_app = app
        self.allow_close = False
        self._loading_profile = False
        self._actions_editors: list[tuple[QComboBox, QLineEdit, QPushButton]] = []

        self.setWindowTitle("RS-Deck")
        self.setMinimumSize(720, 520)
        screen = app.primaryScreen()
        available = screen.availableGeometry() if screen else None
        if available:
            self.resize(min(1040, max(720, available.width() - 80)),
                        min(820, max(520, available.height() - 80)))
        else:
            self.resize(980, 760)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._build_tray()
        self._connect_transport()
        self._load_selected_profile()
        self._setup_timers()
        self._apply_startup_setting(bool(self.config.get("start_with_windows", False)))

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        brand = QLabel("RS-DECK")
        brand.setObjectName("brand")
        eyebrow = QLabel("WIRELESS CONTROL SURFACE")
        eyebrow.setObjectName("eyebrow")
        title_col.addWidget(brand)
        title_col.addWidget(eyebrow)
        header.addLayout(title_col)
        header.addStretch(1)
        self.connection_label = QLabel("●  Searching for device")
        self.connection_label.setObjectName("connectionStatus")
        self.connection_label.setProperty("connected", False)
        header.addWidget(self.connection_label, 0, Qt.AlignVCenter)
        self.layer_label = QLabel("LAYER  NORMAL")
        self.layer_label.setObjectName("layerStatus")
        header.addWidget(self.layer_label, 0, Qt.AlignVCenter)
        root.addLayout(header)

        connection_card = QFrame()
        connection_card.setObjectName("topCard")
        connection_layout = QHBoxLayout(connection_card)
        connection_layout.setContentsMargins(16, 12, 16, 12)
        left = QVBoxLayout()
        label = QLabel("BLUETOOTH SERIAL LINK")
        label.setObjectName("eyebrow")
        note = QLabel("Choose the Windows outgoing Bluetooth COM port. RS-Deck verifies the live link with a heartbeat.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        left.addWidget(label)
        left.addWidget(note)
        connection_layout.addLayout(left, 1)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(250)
        self.port_combo.addItem("Auto-detect Bluetooth COM port", "")
        self.port_combo.currentIndexChanged.connect(self.on_port_changed)
        connection_layout.addWidget(self.port_combo)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_ports)
        connection_layout.addWidget(refresh_button)
        reconnect_button = QPushButton("Reconnect")
        reconnect_button.clicked.connect(self.force_reconnect)
        connection_layout.addWidget(reconnect_button)
        root.addWidget(connection_card)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 4, 10, 10)
        content_layout.setSpacing(15)

        profile_panel = QFrame()
        profile_panel.setObjectName("panel")
        profile_layout = QVBoxLayout(profile_panel)
        profile_layout.setContentsMargins(16, 14, 16, 14)
        profile_top = QHBoxLayout()
        profile_title = QLabel("ACTIVE PROFILE")
        profile_title.setObjectName("eyebrow")
        profile_top.addWidget(profile_title)
        profile_top.addStretch(1)
        self.auto_detect_check = QCheckBox("Auto-detect foreground app")
        self.auto_detect_check.setChecked(bool(self.config.get("auto_detect", True)))
        self.auto_detect_check.toggled.connect(self.on_auto_detect_toggled)
        profile_top.addWidget(self.auto_detect_check)
        profile_layout.addLayout(profile_top)

        profile_controls = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(230)
        self.profile_combo.currentIndexChanged.connect(self.on_profile_combo_changed)
        profile_controls.addWidget(self.profile_combo, 2)
        self.create_profile_button = QPushButton("＋  New profile")
        self.create_profile_button.clicked.connect(self.create_profile)
        profile_controls.addWidget(self.create_profile_button)
        self.rename_profile_button = QPushButton("Rename")
        self.rename_profile_button.clicked.connect(self.rename_profile)
        profile_controls.addWidget(self.rename_profile_button)
        self.delete_profile_button = QPushButton("Delete")
        self.delete_profile_button.setObjectName("danger")
        self.delete_profile_button.clicked.connect(self.delete_profile)
        profile_controls.addWidget(self.delete_profile_button)
        profile_layout.addLayout(profile_controls)

        exe_row = QHBoxLayout()
        exe_label = QLabel("Auto-detect executable")
        exe_label.setObjectName("muted")
        exe_row.addWidget(exe_label)
        self.exe_edit = QLineEdit()
        self.exe_edit.setPlaceholderText("e.g. Adobe Premiere Pro.exe")
        self.exe_edit.editingFinished.connect(self.save_profile_exe)
        exe_row.addWidget(self.exe_edit, 1)
        profile_layout.addLayout(exe_row)
        content_layout.addWidget(profile_panel)

        assignments_header = QHBoxLayout()
        assignments_label = QLabel("BUTTON ASSIGNMENTS")
        assignments_label.setObjectName("eyebrow")
        assignments_header.addWidget(assignments_label)
        assignments_header.addStretch(1)
        assignments_hint = QLabel("8 normal actions  +  8 Shift-layer actions")
        assignments_hint.setObjectName("muted")
        assignments_header.addWidget(assignments_hint)
        content_layout.addLayout(assignments_header)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        for index in range(16):
            card = QFrame()
            card.setObjectName("assignmentCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 11, 12, 12)
            card_layout.setSpacing(8)
            heading = QHBoxLayout()
            number = QLabel(f"{(index % 8) + 1:02d}")
            number.setStyleSheet("font-size: 13pt; font-weight: 800; color: #d7e5fb;")
            heading.addWidget(number)
            layer_text = "NORMAL" if index < 8 else "SHIFT LAYER"
            layer = QLabel(layer_text)
            layer.setObjectName("eyebrow")
            heading.addWidget(layer)
            heading.addStretch(1)
            card_layout.addLayout(heading)
            row = QHBoxLayout()
            action_type = QComboBox()
            for label_text, key in ACTION_OPTIONS:
                action_type.addItem(label_text, key)
            action_type.currentIndexChanged.connect(lambda _i, ix=index: self.on_action_type_changed(ix))
            row.addWidget(action_type, 1)
            browse = QPushButton("Browse")
            browse.setMaximumWidth(82)
            browse.clicked.connect(lambda _checked=False, ix=index: self.browse_for_action(ix))
            row.addWidget(browse)
            card_layout.addLayout(row)
            value = QLineEdit()
            value.setPlaceholderText("Choose an action type")
            value.editingFinished.connect(lambda ix=index: self.save_action_value(ix))
            card_layout.addWidget(value)
            self._actions_editors.append((action_type, value, browse))
            grid.addWidget(card, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        content_layout.addWidget(grid_host)

        settings = QFrame()
        settings.setObjectName("panel")
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(16, 14, 16, 14)
        settings_head = QLabel("APP SETTINGS")
        settings_head.setObjectName("eyebrow")
        settings_layout.addWidget(settings_head)
        chrome_row = QHBoxLayout()
        chrome_label = QLabel("Google Chrome path")
        chrome_label.setObjectName("muted")
        chrome_row.addWidget(chrome_label)
        self.chrome_edit = QLineEdit(self.config.get("chrome_path", ""))
        self.chrome_edit.setPlaceholderText("Auto-detected, or browse to chrome.exe")
        self.chrome_edit.editingFinished.connect(self.save_chrome_path)
        chrome_row.addWidget(self.chrome_edit, 1)
        chrome_browse = QPushButton("Browse")
        chrome_browse.clicked.connect(self.browse_chrome)
        chrome_row.addWidget(chrome_browse)
        settings_layout.addLayout(chrome_row)

        options_row = QHBoxLayout()
        self.startup_check = QCheckBox("Start RS-Deck with Windows")
        self.startup_check.setChecked(bool(self.config.get("start_with_windows", False)))
        self.startup_check.toggled.connect(self.on_startup_toggled)
        options_row.addWidget(self.startup_check)
        self.tray_check = QCheckBox("Minimize to system tray")
        self.tray_check.setChecked(bool(self.config.get("minimize_to_tray", True)))
        self.tray_check.toggled.connect(self.on_tray_toggled)
        options_row.addWidget(self.tray_check)
        options_row.addStretch(1)
        settings_layout.addLayout(options_row)

        backup_row = QHBoxLayout()
        backup_row.addWidget(QLabel("Settings backup"))
        backup_row.addStretch(1)
        backup_button = QPushButton("Export backup")
        backup_button.clicked.connect(self.export_backup)
        restore_button = QPushButton("Restore backup")
        restore_button.clicked.connect(self.restore_backup)
        backup_row.addWidget(backup_button)
        backup_row.addWidget(restore_button)
        settings_layout.addLayout(backup_row)
        content_layout.addWidget(settings)

        footer = QLabel("RS-Deck  •  Protocol v1  •  Changes are saved automatically on this PC")
        footer.setObjectName("muted")
        content_layout.addWidget(footer)
        content_layout.addItem(QSpacerItem(1, 12, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)
        self.setCentralWidget(central)

        self._populate_profile_combo()
        self._populate_port_combo([])
        self.chrome_edit.setText(self.config.get("chrome_path", ""))

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.style().standardIcon(QStyle.SP_ComputerIcon), self)
        self.tray.setToolTip("RS-Deck")
        menu = QMenu()
        show_action = QAction("Open RS-Deck", self)
        show_action.triggered.connect(self.show_from_tray)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _connect_transport(self) -> None:
        self.transport.connected.connect(self.on_connected)
        self.transport.disconnected.connect(self.on_disconnected)
        self.transport.frame_received.connect(self.on_frame_received)
        self.transport.port_list_changed.connect(self._populate_port_combo)
        self.transport.diagnostic.connect(self.set_status_message)
        self.transport.start()
        self.refresh_ports()

    def _setup_timers(self) -> None:
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.check_active_application)
        self.auto_timer.start(1200)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_ports)
        self.refresh_timer.start(6000)

    def _profile_by_id(self, profile_id: str) -> dict | None:
        return next((p for p in self.config["profiles"] if p["id"] == profile_id), None)

    def _current_profile(self) -> dict:
        return self._profile_by_id(self.config.get("selected_profile", "default")) or self.config["profiles"][0]

    def _populate_profile_combo(self) -> None:
        wanted = self.config.get("selected_profile", "default")
        self._loading_profile = True
        self.profile_combo.clear()
        for profile in self.config["profiles"]:
            self.profile_combo.addItem(profile["name"], profile["id"])
        index = self.profile_combo.findData(wanted)
        self.profile_combo.setCurrentIndex(max(index, 0))
        self._loading_profile = False
        self.delete_profile_button.setEnabled(wanted != "default")

    def _load_selected_profile(self) -> None:
        profile = self._current_profile()
        self._loading_profile = True
        index = self.profile_combo.findData(profile["id"])
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)
        self.exe_edit.setText(profile.get("exe", ""))
        for i, (combo, value_edit, browse) in enumerate(self._actions_editors):
            action = profile["actions"][i]
            action_index = combo.findData(action["type"])
            combo.setCurrentIndex(max(action_index, 0))
            value_edit.setText(action.get("value", ""))
            value_edit.setPlaceholderText(self._placeholder(action["type"]))
            browse.setVisible(action["type"] == "open")
        self._loading_profile = False
        self.delete_profile_button.setEnabled(profile["id"] != "default")
        self.config["selected_profile"] = profile["id"]
        save_config(self.config)

    @staticmethod
    def _placeholder(action_type: str) -> str:
        return {
            "none": "No action assigned",
            "open": "Select an application or file path",
            "url": "https://example.com",
            "hotkey": "CTRL+SHIFT+S  or  F5",
            "text": "Text to type on the active window",
        }.get(action_type, "Enter a value")

    def on_profile_combo_changed(self, _index: int) -> None:
        if self._loading_profile:
            return
        profile_id = self.profile_combo.currentData()
        if profile_id:
            self.auto_detect_check.setChecked(False)
            self.config["auto_detect"] = False
            self.config["selected_profile"] = profile_id
            self._load_selected_profile()
            self.sync_profile_to_device()

    def apply_profile(self, profile_id: str, manual: bool = False) -> None:
        if self._profile_by_id(profile_id) is None:
            return
        if manual and self.auto_detect_check.isChecked():
            self.auto_detect_check.setChecked(False)
        self.config["selected_profile"] = profile_id
        self._populate_profile_combo()
        self._load_selected_profile()
        self.sync_profile_to_device()

    def create_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "New profile", "Profile name:")
        name = name.strip()
        if not ok or not name:
            return
        if any(p["name"].casefold() == name.casefold() for p in self.config["profiles"]):
            QMessageBox.warning(self, "Profile exists", "A profile with that name already exists.")
            return
        base = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "profile"
        profile_id = base
        while self._profile_by_id(profile_id):
            profile_id = f"{base}-{uuid.uuid4().hex[:4]}"
        self.config["profiles"].append({"id": profile_id, "name": name, "exe": "", "actions": [{"type": "none", "value": ""} for _ in range(16)]})
        self.config["selected_profile"] = profile_id
        self._populate_profile_combo()
        self._load_selected_profile()
        self.sync_profile_to_device()

    def rename_profile(self) -> None:
        profile = self._current_profile()
        name, ok = QInputDialog.getText(self, "Rename profile", "New name:", text=profile["name"])
        name = name.strip()
        if not ok or not name:
            return
        if any(p["id"] != profile["id"] and p["name"].casefold() == name.casefold() for p in self.config["profiles"]):
            QMessageBox.warning(self, "Profile exists", "A profile with that name already exists.")
            return
        profile["name"] = name
        self._populate_profile_combo()
        self._load_selected_profile()
        self.sync_profile_to_device()

    def delete_profile(self) -> None:
        profile = self._current_profile()
        if profile["id"] == "default":
            return
        answer = QMessageBox.question(self, "Delete profile", f"Delete '{profile['name']}' and its 16 assignments?")
        if answer != QMessageBox.Yes:
            return
        self.config["profiles"] = [p for p in self.config["profiles"] if p["id"] != profile["id"]]
        self.config["selected_profile"] = "default"
        self._populate_profile_combo()
        self._load_selected_profile()
        self.sync_profile_to_device()

    def save_profile_exe(self) -> None:
        if self._loading_profile:
            return
        self._current_profile()["exe"] = self.exe_edit.text().strip()
        save_config(self.config)

    def on_action_type_changed(self, index: int) -> None:
        if self._loading_profile:
            return
        combo, value_edit, browse = self._actions_editors[index]
        action_type = combo.currentData()
        value_edit.setPlaceholderText(self._placeholder(action_type))
        browse.setVisible(action_type == "open")
        if action_type == "none":
            value_edit.clear()
        self.save_action_value(index)

    def save_action_value(self, index: int) -> None:
        if self._loading_profile:
            return
        combo, value_edit, _browse = self._actions_editors[index]
        self._current_profile()["actions"][index] = {
            "type": str(combo.currentData() or "none"),
            "value": value_edit.text(),
        }
        save_config(self.config)

    def browse_for_action(self, index: int) -> None:
        _combo, value_edit, _browse = self._actions_editors[index]
        path, _ = QFileDialog.getOpenFileName(self, "Choose application or file", value_edit.text())
        if path:
            value_edit.setText(path)
            self.save_action_value(index)

    def save_chrome_path(self) -> None:
        self.config["chrome_path"] = self.chrome_edit.text().strip()
        save_config(self.config)

    def browse_chrome(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Locate Google Chrome", "", "Applications (chrome.exe)")
        if path:
            self.chrome_edit.setText(path)
            self.save_chrome_path()

    def on_auto_detect_toggled(self, checked: bool) -> None:
        self.config["auto_detect"] = checked
        save_config(self.config)
        if checked:
            self.check_active_application()

    def check_active_application(self) -> None:
        if not self.auto_detect_check.isChecked():
            return
        executable = active_window_executable()
        if not executable or executable in {"python.exe", "pythonw.exe", "rs-deck.exe"}:
            return
        matching = next((p for p in self.config["profiles"]
                         if p.get("exe", "").strip().lower() == executable), None)
        target_id = matching["id"] if matching else "default"
        if target_id != self.config.get("selected_profile"):
            self.apply_profile(target_id, manual=False)

    def on_startup_toggled(self, checked: bool) -> None:
        self.config["start_with_windows"] = checked
        self._apply_startup_setting(checked)
        save_config(self.config)

    def _apply_startup_setting(self, enabled: bool) -> None:
        if os.name != "nt":
            return
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    if getattr(sys, "frozen", False):
                        command = f'"{sys.executable}" --tray'
                    else:
                        script = Path(__file__).resolve().parents[1] / "main.py"
                        pythonw = Path(sys.executable).with_name("pythonw.exe")
                        startup_python = str(pythonw if pythonw.exists() else Path(sys.executable))
                        command = f'"{startup_python}" "{script}" --tray'
                    winreg.SetValueEx(key, "RS-Deck", 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, "RS-Deck")
                    except FileNotFoundError:
                        pass
        except OSError as exc:
            self.set_status_message(f"Could not change Windows startup setting: {exc}")

    def on_tray_toggled(self, checked: bool) -> None:
        self.config["minimize_to_tray"] = checked
        save_config(self.config)

    def export_backup(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export RS-Deck settings", "RS-Deck-backup.json", "JSON files (*.json)")
        if not path:
            return
        try:
            import json
            Path(path).write_text(json.dumps(self.config, indent=2, ensure_ascii=False), encoding="utf-8")
            QMessageBox.information(self, "Backup exported", "Your profile and button settings were exported.")
        except OSError as exc:
            QMessageBox.critical(self, "Backup failed", str(exc))

    def restore_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Restore RS-Deck backup", "", "JSON files (*.json)")
        if not path:
            return
        try:
            import json
            from .config import normalize_config
            restored = normalize_config(json.loads(Path(path).read_text(encoding="utf-8")))
            self.config.clear()
            self.config.update(restored)
            save_config(self.config)
            self._populate_profile_combo()
            self._load_selected_profile()
            self.auto_detect_check.setChecked(bool(self.config.get("auto_detect", True)))
            self.startup_check.setChecked(bool(self.config.get("start_with_windows", False)))
            self.tray_check.setChecked(bool(self.config.get("minimize_to_tray", True)))
            self.chrome_edit.setText(self.config.get("chrome_path", ""))
            self._populate_port_combo(self.transport.available_ports())
            self.sync_profile_to_device()
            QMessageBox.information(self, "Backup restored", "RS-Deck settings were restored.")
        except Exception as exc:
            QMessageBox.critical(self, "Restore failed", str(exc))

    def refresh_ports(self) -> None:
        ports = self.transport.available_ports()
        self._populate_port_combo(ports)

    def _populate_port_combo(self, ports: list) -> None:
        current = self.config.get("serial_port", "")
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItem("Auto-detect Bluetooth COM port", "")
        for device, label in ports:
            self.port_combo.addItem(label, device)
        index = self.port_combo.findData(current)
        if current and index < 0:
            self.port_combo.addItem(f"{current} — saved COM port (not currently listed)", current)
            index = self.port_combo.findData(current)
        self.port_combo.setCurrentIndex(max(index, 0))
        self.port_combo.blockSignals(False)
        if hasattr(self, "transport"):
            self.transport.set_port(current)

    def on_port_changed(self, index: int) -> None:
        port = str(self.port_combo.itemData(index) or "")
        self.config["serial_port"] = port
        save_config(self.config)
        self.transport.set_port(port)

    def force_reconnect(self) -> None:
        self.transport.request_reconnect()
        self.set_status_message("Reconnecting to RS-Deck…")

    def on_connected(self, port: str) -> None:
        self.connection_label.setText(f"●  Connected  ·  {port}")
        self.connection_label.setProperty("connected", True)
        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)
        self.transport.send_line("HELLO_PC|1")
        self.sync_time_to_device()
        self.sync_profile_to_device()
        self.set_status_message(f"Live RS-Deck SPP session on {port}")

    def on_disconnected(self, reason: str) -> None:
        self.connection_label.setText("●  Disconnected / reconnecting")
        self.connection_label.setProperty("connected", False)
        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)
        self.set_status_message(reason)

    def set_status_message(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)

    def sync_time_to_device(self) -> None:
        import time
        self.transport.send_line(f"TIME|{int(time.time())}")

    def sync_profile_to_device(self) -> None:
        profile = self._current_profile()
        self.transport.send_line("PROFILE|" + quote(profile["name"], safe=""))

    def on_frame_received(self, frame: str) -> None:
        fields = frame.split("|")
        if not fields:
            return
        command = fields[0]
        if command == "SHIFT" and len(fields) >= 2:
            self.layer_label.setText("LAYER  " + ("SHIFT" if fields[1] == "1" else "NORMAL"))
        elif command == "BTN" and len(fields) >= 3:
            if not bool(self.connection_label.property("connected")):
                return
            try:
                button_number = int(fields[1])
                layer = int(fields[2])
                if 1 <= button_number <= 8 and layer in (0, 1):
                    self.execute_button(button_number, layer)
            except ValueError:
                self.set_status_message("Ignored malformed button event")
        elif command == "PROFILE_NEXT":
            profiles = self.config["profiles"]
            current_id = self.config.get("selected_profile", "default")
            ids = [p["id"] for p in profiles]
            try:
                next_id = ids[(ids.index(current_id) + 1) % len(ids)]
            except (ValueError, ZeroDivisionError):
                next_id = "default"
            self.apply_profile(next_id, manual=True)
            self.set_status_message(f"Profile changed to {self._current_profile()['name']}")

    def execute_button(self, button_number: int, layer: int) -> None:
        index = (button_number - 1) + (8 if layer else 0)
        action = self._current_profile()["actions"][index]
        if action["type"] == "none" or not action["value"]:
            self.set_status_message(f"Button {button_number} · {'Shift' if layer else 'Normal'} layer is not assigned")
            return
        execute_action(action, self.chrome_edit.text().strip(), self.show_action_error)

    def show_action_error(self, message: str) -> None:
        QMessageBox.warning(self, "RS-Deck action failed", message)

    def on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_from_tray()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def exit_app(self) -> None:
        self.allow_close = True
        self.transport.stop()
        self.qt_app.quit()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if (event.type() == QEvent.WindowStateChange and self.isMinimized()
                and self.config.get("minimize_to_tray", True)
                and QSystemTrayIcon.isSystemTrayAvailable()):
            self.hide()

    def closeEvent(self, event) -> None:
        if (not self.allow_close and self.config.get("minimize_to_tray", True)
                and QSystemTrayIcon.isSystemTrayAvailable()):
            self.hide()
            self.tray.showMessage("RS-Deck is running", "The device connection stays active in the system tray.", QSystemTrayIcon.Information, 2200)
            event.ignore()
            return
        self.allow_close = True
        self.transport.stop()
        self.qt_app.quit()
        event.accept()
