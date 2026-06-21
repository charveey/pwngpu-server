import logging
import subprocess
import time
import psutil
from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger("pwngpu.network")

# Windows names these adapters various things depending on driver/version.
# We cast a wide net and then filter out obviously-wrong adapters below.
USB_NAME_HINTS = (
    "rndis",
    "remote ndis",
    "usb ethernet",
    "gadget",
    "usb0",
    "linux usb",
    "linux device",       # some CDC-ECM driver installs show this
    "ecm",                # CDC-ECM fallback driver
    "ncm",                # CDC-NCM fallback driver
)

# Adapter names that should never be mistaken for a USB gadget link.
# Add more if needed (Wi-Fi, VPN, etc. are fine to leave off this list;
# only things that contain one of the hint strings above need to be here).
ADAPTER_EXCLUDE = (
    "virtual",
    "vmware",
    "virtualbox",
    "hyper-v",
    "loopback",
    "bluetooth",
)

# If the adapter name gives no clue, fall back to checking whether any
# IPv4 address on it falls inside the typical pwnagotchi USB subnet.
# The default is 10.0.0.x/24, but users may have changed it.
USB_SUBNET_HINTS = (
    "10.0.0.",    # default pwnagotchi USB gadget subnet
    "172.16.0.",  # some setups use this
)


def _looks_like_usb_gadget(name: str, snics: list) -> bool:
    """
    Return True if this adapter is likely the USB gadget link.
    Checks name hints first, then IP-subnet fallback.
    """
    lower = name.lower()

    # Hard exclude — virtual adapters that sometimes match name hints.
    if any(ex in lower for ex in ADAPTER_EXCLUDE):
        return False

    # Primary check: well-known name fragments.
    if any(h in lower for h in USB_NAME_HINTS):
        return True

    # Secondary check: the adapter has an IPv4 in a known USB gadget subnet.
    for snic in snics:
        if snic.family.name == "AF_INET" and any(
            snic.address.startswith(pfx) for pfx in USB_SUBNET_HINTS
        ):
            return True

    return False


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
            if not _looks_like_usb_gadget(name, snics):
                continue
            ip = ""
            for snic in snics:
                if snic.family.name == "AF_INET":
                    ip = snic.address
                    break
            current[name] = ip
            logger.debug(f"USB gadget candidate: '{name}' ip={ip or 'none'}")

        for name, ip in current.items():
            prev_ip = self._known.get(name)
            if name not in self._known:
                # Adapter just appeared (with or without an IP yet).
                logger.info(f"USB adapter appeared: '{name}' ip={ip or 'none'}")
                self.adapter_connected.emit(name, ip)
            elif prev_ip != ip:
                # Adapter was already known but its IP changed (e.g. "" -> "10.0.0.2"
                # after Windows finishes DHCP/static assignment, or IP was reassigned).
                logger.info(f"USB adapter IP updated: '{name}' {prev_ip!r} -> {ip!r}")
                self.adapter_connected.emit(name, ip)

        for name in list(self._known):
            if name not in current:
                logger.info(f"USB adapter removed: '{name}'")
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


# ---------------------------------------------------------------------------
# Diagnostic helper — run this file directly on the target machine to see
# every adapter and whether our heuristic would match it.
# Usage:  python network_monitor.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    addrs = psutil.net_if_addrs()
    print(f"{'Adapter':<45} {'IPv4':<18} {'Would match?'}")
    print("-" * 75)
    for name, snics in addrs.items():
        ip = next(
            (s.address for s in snics if s.family.name == "AF_INET"), ""
        )
        match = _looks_like_usb_gadget(name, snics)
        print(f"{name:<45} {ip:<18} {'YES ✓' if match else 'no'}")