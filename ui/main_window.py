import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QSystemTrayIcon, QMenu, QMessageBox, QHeaderView, QStyle, QApplication
)

from core.server import ServerThread
from core.network_monitor import NetworkMonitor, set_static_ip
from core.win_integration import is_admin
from ui.settings_dialog import SettingsDialog

logger = logging.getLogger("pwngpu.ui")


class MainWindow(QMainWindow):
    def __init__(self, settings, runner):
        super().__init__()
        self.settings = settings
        self.runner = runner
        self.server_thread = None
        self.monitor = NetworkMonitor()
        self.usb_adapter = None
        self.usb_ip = ""

        self.setWindowTitle("Pwnagotchi GPU Crack Server")
        self.resize(840, 580)

        self._build_ui()
        self._build_tray()
        self._wire_signals()

        self.monitor.start()

    # ------------------------------------------------------------- UI ---
    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        status_box = QGroupBox("Status")
        sl = QHBoxLayout(status_box)
        self.server_status_label = QLabel("Server: stopped")
        self.usb_status_label = QLabel("USB link: not detected")
        self.api_key_label = QLabel(f"API key: {self.settings.api_key}")
        self.api_key_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        sl.addWidget(self.server_status_label)
        sl.addWidget(self.usb_status_label)
        sl.addStretch()
        sl.addWidget(self.api_key_label)
        layout.addWidget(status_box)

        controls = QHBoxLayout()
        self.start_btn = QPushButton("Start Server")
        self.stop_btn = QPushButton("Stop Server")
        self.stop_btn.setEnabled(False)
        self.settings_btn = QPushButton("Settings…")
        self.configure_ip_btn = QPushButton("Configure USB Adapter IP")
        self.configure_ip_btn.setEnabled(False)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.configure_ip_btn)
        controls.addStretch()
        controls.addWidget(self.settings_btn)
        layout.addLayout(controls)

        results_box = QGroupBox("Cracked passwords")
        rl = QVBoxLayout(results_box)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["SSID", "BSSID", "Password"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        rl.addWidget(self.table)
        layout.addWidget(results_box, stretch=1)

        log_box = QGroupBox("Log")
        ll = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        ll.addWidget(self.log_view)
        layout.addWidget(log_box, stretch=1)

        self.setCentralWidget(central)
        self._refresh_results_table()

    def _build_tray(self):
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Pwnagotchi GPU Crack Server")
        menu = QMenu()
        self.show_action = QAction("Show window", self)
        self.show_action.triggered.connect(self._show_window)
        self.toggle_server_action = QAction("Start server", self)
        self.toggle_server_action.triggered.connect(self._toggle_server)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(self.show_action)
        menu.addAction(self.toggle_server_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _wire_signals(self):
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.settings_btn.clicked.connect(self._open_settings)
        self.configure_ip_btn.clicked.connect(self._configure_ip)

        self.runner.log.connect(self._append_log)
        self.runner.job_started.connect(lambda name: self._append_log(f"[job] processing {name}"))
        self.runner.job_finished.connect(
            lambda name, n: self._append_log(f"[job] finished {name} ({n} new cracked)")
        )
        self.runner.cracked_found.connect(self._on_cracked_found)

        self.monitor.adapter_connected.connect(self._on_usb_connected)
        self.monitor.adapter_disconnected.connect(self._on_usb_disconnected)

    # -------------------------------------------------------- behaviour ---
    def start_server(self, silent=False):
        if self.server_thread and self.server_thread.isRunning():
            return
        self.server_thread = ServerThread(self.settings, self.runner)
        self.server_thread.started_ok.connect(
            lambda ok, err: self._on_server_started(ok, err, silent)
        )
        self.server_thread.start()

    def stop_server(self):
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread.wait(3000)
        self.server_status_label.setText("Server: stopped")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.toggle_server_action.setText("Start server")

    def _on_server_started(self, ok, err, silent=False):
        if ok:
            self.server_status_label.setText(f"Server: running on port {self.settings.port}")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.toggle_server_action.setText("Stop server")
            self._append_log(f"Server listening on 0.0.0.0:{self.settings.port}")
        else:
            self.server_status_label.setText("Server: failed to start")
            self._append_log(f"[error] could not start server: {err}")
            if not silent:
                QMessageBox.critical(self, "Server error", f"Could not start server:\n{err}")

    def _toggle_server(self):
        if self.server_thread and self.server_thread.isRunning():
            self.stop_server()
        else:
            self.start_server()

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self.api_key_label.setText(f"API key: {self.settings.api_key}")
            if self.server_thread and self.server_thread.isRunning():
                self._append_log("Settings changed — restarting server…")
                self.stop_server()
                self.start_server()

    def _configure_ip(self):
        if not self.usb_adapter:
            return
        if not is_admin():
            QMessageBox.warning(
                self, "Administrator required",
                "Configuring the network adapter requires running this app "
                "as Administrator. Right-click the app and choose "
                "'Run as administrator', or set the IP manually in "
                "Windows Network Settings."
            )
            return
        ok, msg = set_static_ip(self.usb_adapter, self.settings.static_ip, self.settings.subnet_mask)
        if ok:
            self._append_log(f"Configured {self.usb_adapter} -> {self.settings.static_ip}")
        else:
            QMessageBox.critical(self, "Failed to set IP", msg)

    def _on_usb_connected(self, name, ip):
        self.usb_adapter = name
        self.usb_ip = ip
        self.configure_ip_btn.setEnabled(True)
        if ip:
            self.usb_status_label.setText(f"USB link: {name} ({ip})")
        else:
            self.usb_status_label.setText(f"USB link: {name} (no IP yet)")
            if is_admin():
                self._configure_ip()
        self._append_log(f"USB adapter detected: {name} ({ip or 'no IP'})")
        if ip == self.settings.static_ip and self.settings.auto_start_server:
            if not (self.server_thread and self.server_thread.isRunning()):
                self._append_log("USB IP ready — starting server.")
                self.start_server(silent=True)

    def _on_usb_disconnected(self, name):
        if self.usb_adapter == name:
            self.usb_adapter = None
            self.configure_ip_btn.setEnabled(False)
        self.usb_status_label.setText("USB link: not detected")
        self._append_log(f"USB adapter disconnected: {name}")

    def _on_cracked_found(self, entry):
        self._add_result_row(entry)
        self.tray.showMessage(
            "Password cracked!",
            f"{entry['ssid']}: {entry['password']}",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def _refresh_results_table(self):
        self.table.setRowCount(0)
        for entry in self.runner.all_results():
            self._add_result_row(entry)

    def _add_result_row(self, entry):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(entry["ssid"]))
        self.table.setItem(row, 1, QTableWidgetItem(entry["bssid"]))
        self.table.setItem(row, 2, QTableWidgetItem(entry["password"]))

    def _append_log(self, text):
        self.log_view.appendPlainText(text)

    # ------------------------------------------------------------ tray ---
    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()

    def _show_window(self):
        self.showNormal()
        self.activateWindow()

    def closeEvent(self, event):
        # Close button minimizes to tray instead of quitting, so the
        # server keeps running in the background.
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Still running",
            "Pwnagotchi GPU Crack Server is running in the background.",
            QSystemTrayIcon.MessageIcon.Information, 3000
        )

    def _quit(self):
        self.monitor.stop()
        if self.server_thread and self.server_thread.isRunning():
            self.server_thread.stop()
            self.server_thread.wait(2000)
        self.runner.stop()
        QApplication.quit()
