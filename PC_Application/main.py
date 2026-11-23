from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from rsdeck.config import load_config, CONFIG_DIR
from rsdeck.transport import SerialWorker
from rsdeck.ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("RS-Deck")
    app.setOrganizationName("RS-Deck")
    app.setQuitOnLastWindowClosed(False)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(CONFIG_DIR / "rsdeck-instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "RS-Deck already running", "RS-Deck is already open. Check the system tray.")
        return 0

    config = load_config()
    transport = SerialWorker(config.get("serial_port", ""))
    window = MainWindow(config, transport, app)
    if ("--tray" in sys.argv and config.get("minimize_to_tray", True)
            and QSystemTrayIcon.isSystemTrayAvailable()):
        window.hide()
    else:
        window.show()
    code = app.exec()
    transport.stop()
    lock.unlock()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
