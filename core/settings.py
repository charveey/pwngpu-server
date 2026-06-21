import os
import secrets
from PyQt6.QtCore import QSettings

ORG = "PwnGPU"
APP = "CrackServer"

DEFAULTS = {
    "api_key": "",
    "port": 6881,
    "hashcat_path": r"C:\hashcat\hashcat.exe",
    "wordlist_path": "",
    "rules_path": "",
    "work_dir": os.path.join(os.path.expanduser("~"), "PwnGPU"),
    "gpu_device": "",          # empty = let hashcat pick all devices
    "auto_start_server": True,
    "start_minimized": False,
    "launch_at_login": False,
    "static_ip": "10.0.0.1",
    "subnet_mask": "255.255.255.0",
}


class Settings:
    """Thin typed wrapper around QSettings. Values persist between runs
    in the standard Windows location (registry, under HKCU\\Software\\PwnGPU)."""

    def __init__(self):
        self._qs = QSettings(ORG, APP)
        if not self.api_key:
            # Generate a random key on first run so there's never a default
            # "changeme" credential sitting in the config.
            self.api_key = secrets.token_hex(16)
        if not os.path.isdir(self.work_dir):
            os.makedirs(self.work_dir, exist_ok=True)

    def _get(self, key, cast=str):
        val = self._qs.value(key, DEFAULTS[key])
        if cast is bool:
            if isinstance(val, bool):
                return val
            return str(val).lower() in ("1", "true", "yes")
        if cast is int:
            return int(val)
        return val

    def _set(self, key, value):
        self._qs.setValue(key, value)

    # -- properties -----------------------------------------------------
    @property
    def api_key(self):
        return self._get("api_key")

    @api_key.setter
    def api_key(self, v):
        self._set("api_key", v)

    @property
    def port(self):
        return self._get("port", int)

    @port.setter
    def port(self, v):
        self._set("port", int(v))

    @property
    def hashcat_path(self):
        return self._get("hashcat_path")

    @hashcat_path.setter
    def hashcat_path(self, v):
        self._set("hashcat_path", v)

    @property
    def wordlist_path(self):
        return self._get("wordlist_path")

    @wordlist_path.setter
    def wordlist_path(self, v):
        self._set("wordlist_path", v)

    @property
    def rules_path(self):
        return self._get("rules_path")

    @rules_path.setter
    def rules_path(self, v):
        self._set("rules_path", v)

    @property
    def work_dir(self):
        return self._get("work_dir")

    @work_dir.setter
    def work_dir(self, v):
        self._set("work_dir", v)

    @property
    def gpu_device(self):
        return self._get("gpu_device")

    @gpu_device.setter
    def gpu_device(self, v):
        self._set("gpu_device", v)

    @property
    def auto_start_server(self):
        return self._get("auto_start_server", bool)

    @auto_start_server.setter
    def auto_start_server(self, v):
        self._set("auto_start_server", bool(v))

    @property
    def start_minimized(self):
        return self._get("start_minimized", bool)

    @start_minimized.setter
    def start_minimized(self, v):
        self._set("start_minimized", bool(v))

    @property
    def launch_at_login(self):
        return self._get("launch_at_login", bool)

    @launch_at_login.setter
    def launch_at_login(self, v):
        self._set("launch_at_login", bool(v))

    @property
    def static_ip(self):
        return self._get("static_ip")

    @static_ip.setter
    def static_ip(self, v):
        self._set("static_ip", v)

    @property
    def subnet_mask(self):
        return self._get("subnet_mask")

    @subnet_mask.setter
    def subnet_mask(self, v):
        self._set("subnet_mask", v)

    # -- derived paths ----------------------------------------------------
    @property
    def incoming_dir(self):
        p = os.path.join(self.work_dir, "incoming")
        os.makedirs(p, exist_ok=True)
        return p

    @property
    def potfile_path(self):
        return os.path.join(self.work_dir, "hashcat.potfile")

    @property
    def results_path(self):
        return os.path.join(self.work_dir, "cracked_results.json")
