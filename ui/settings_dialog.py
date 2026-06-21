import secrets
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QSpinBox, QPushButton, QHBoxLayout,
    QVBoxLayout, QFileDialog, QCheckBox, QDialogButtonBox
)

from core.win_integration import set_launch_at_login


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)

        form = QFormLayout()

        self.api_key_edit = QLineEdit(settings.api_key)
        gen_btn = QPushButton("Generate")
        gen_btn.clicked.connect(self._regen_key)
        key_row = QHBoxLayout()
        key_row.addWidget(self.api_key_edit)
        key_row.addWidget(gen_btn)
        form.addRow("API key", key_row)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(settings.port)
        form.addRow("Listen port", self.port_spin)

        self.hashcat_edit, hc_row = self._path_row(settings.hashcat_path, "hashcat.exe")
        form.addRow("hashcat.exe", hc_row)

        self.wordlist_edit, wl_row = self._path_row(settings.wordlist_path, "wordlist")
        form.addRow("Wordlist", wl_row)

        self.rules_edit, rules_row = self._path_row(settings.rules_path, "rules file (optional)")
        form.addRow("Rules file", rules_row)

        self.gpu_edit = QLineEdit(settings.gpu_device)
        self.gpu_edit.setPlaceholderText("e.g. 1  (blank = all devices)")
        form.addRow("GPU device (-d)", self.gpu_edit)

        self.static_ip_edit = QLineEdit(settings.static_ip)
        form.addRow("USB adapter static IP", self.static_ip_edit)

        self.mask_edit = QLineEdit(settings.subnet_mask)
        form.addRow("Subnet mask", self.mask_edit)

        self.auto_start_chk = QCheckBox("Start server automatically when app opens")
        self.auto_start_chk.setChecked(settings.auto_start_server)
        form.addRow(self.auto_start_chk)

        self.start_min_chk = QCheckBox("Start minimized to tray")
        self.start_min_chk.setChecked(settings.start_minimized)
        form.addRow(self.start_min_chk)

        self.login_chk = QCheckBox("Launch automatically when Windows starts")
        self.login_chk.setChecked(settings.launch_at_login)
        form.addRow(self.login_chk)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _path_row(self, value, label):
        edit = QLineEdit(value)
        browse = QPushButton("Browse…")

        def pick():
            path, _ = QFileDialog.getOpenFileName(self, f"Select {label}")
            if path:
                edit.setText(path)

        browse.clicked.connect(pick)
        row = QHBoxLayout()
        row.addWidget(edit)
        row.addWidget(browse)
        return edit, row

    def _regen_key(self):
        self.api_key_edit.setText(secrets.token_hex(16))

    def _save(self):
        s = self.settings
        s.api_key = self.api_key_edit.text().strip()
        s.port = self.port_spin.value()
        s.hashcat_path = self.hashcat_edit.text().strip()
        s.wordlist_path = self.wordlist_edit.text().strip()
        s.rules_path = self.rules_edit.text().strip()
        s.gpu_device = self.gpu_edit.text().strip()
        s.static_ip = self.static_ip_edit.text().strip()
        s.subnet_mask = self.mask_edit.text().strip()
        s.auto_start_server = self.auto_start_chk.isChecked()
        s.start_minimized = self.start_min_chk.isChecked()

        if self.login_chk.isChecked() != s.launch_at_login:
            s.launch_at_login = self.login_chk.isChecked()
            try:
                set_launch_at_login(s.launch_at_login)
            except Exception:
                pass

        self.accept()
