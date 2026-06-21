import logging
import subprocess
import time
import psutil
from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger("pwngpu.network")

# Windows names these adapters various things depending on driver:
# "Remote NDIS based Internet Sharing Device", "USB Ethernet/RNDIS Gadget",
# "Linux USB Ethernet/RNDIS Gadget", etc. We match loosely on substrings.
USB_NAME_HINTS = ("rndis", "remote ndis", "usb ethernet", "gadget", "usb0")


class _PollThread(QThread):
    def __init__(self, monitor):
        super().__init__()
        self.monitor = monitor

    def run(self):
        while not self.monitor._stop:
            try:
                self.monitor._scan()
            except Exception as e:
                logger.debug(f"network scan error: {e}")
            time.sleep(self.monitor.poll_interval)


class NetworkMonitor(QObject):
    adapter_connected = pyqtSignal(str, str)     # name, ip (ip may be "")
    adapter_disconnected = pyqtSignal(str)

    def __init__(self, poll_interval=3):
        super().__init__()
        self.poll_interval = poll_interval
        self._known = {}     # name -> ip
        self._stop = False
        self._thread = _PollThread(self)

    def start(self):
        self._stop = False
        self._thread.start()

    def stop(self):
        self._stop = True
        self._thread.wait(2000)

    def _scan(self):
        addrs = psutil.net_if_addrs()
        current = {}
        for name, snics in addrs.items():
            if not any(h in name.lower() for h in USB_NAME_HINTS):
                continue
            ip = ""
            for snic in snics:
                if snic.family.name == "AF_INET":
                    ip = snic.address
                    break
            current[name] = ip

        for name, ip in current.items():
            if name not in self._known or self._known[name] != ip:
                self.adapter_connected.emit(name, ip)
        for name in list(self._known):
            if name not in current:
                self.adapter_disconnected.emit(name)

        self._known = current


def set_static_ip(adapter_name: str, ip: str, mask: str):
    """
    Assign a static IPv4 address to a Windows network adapter via netsh.
    Requires the app to be running elevated (Administrator); otherwise
    netsh fails with an access-denied error, which is surfaced back to
    the caller as (False, message).
    """
    cmd = [
        "netsh", "interface", "ip", "set", "address",
        f"name={adapter_name}", "static", ip, mask,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True, "OK"
        return False, (result.stderr or result.stdout).strip()
    except Exception as e:
        return False, str(e)
