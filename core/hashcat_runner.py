import os
import re
import json
import queue
import logging
import subprocess
import threading
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger("pwngpu.hashcat")


@dataclass
class CrackedEntry:
    ssid: str
    bssid: str
    password: str

    def key(self):
        return f"{self.bssid}:{self.password}"


@dataclass
class Job:
    hash_path: str
    original_name: str


class HashcatRunner(QObject):
    """
    Owns a background worker thread that processes queued .hc22000 files
    with hashcat one at a time, and keeps a running, persisted table of
    cracked SSID/BSSID/password results.

    The plugin's POST /crack has only a 60s timeout, far too short for a
    real wordlist attack, so /crack just hands work off to this queue and
    returns immediately. Results accumulate here and get picked up later
    when the plugin polls GET /results.
    """

    log = pyqtSignal(str)
    job_started = pyqtSignal(str)
    job_finished = pyqtSignal(str, int)       # filename, newly cracked count
    cracked_found = pyqtSignal(dict)          # {ssid, bssid, password}
    queue_size_changed = pyqtSignal(int)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._results = {}          # key -> CrackedEntry
        self._thread = None
        self._load_results()

    # -- persistence ------------------------------------------------------
    def _load_results(self):
        path = self.settings.results_path
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for entry in json.load(f):
                        e = CrackedEntry(**entry)
                        self._results[e.key()] = e
            except Exception as e:
                logger.warning(f"Could not load saved results: {e}")

    def _save_results(self):
        path = self.settings.results_path
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump([e.__dict__ for e in self._results.values()], f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save results: {e}")

    # -- public API ---------------------------------------------------------
    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def enqueue(self, hash_bytes: bytes, original_name: str):
        """Save the uploaded hash file to disk and queue it for cracking."""
        os.makedirs(self.settings.incoming_dir, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", original_name) or "upload.hc22000"
        path = os.path.join(self.settings.incoming_dir, safe_name)
        with open(path, "wb") as f:
            f.write(hash_bytes)
        self._queue.put(Job(hash_path=path, original_name=original_name))
        self.queue_size_changed.emit(self._queue.qsize())

    def all_results(self):
        with self._lock:
            return [e.__dict__ for e in self._results.values()]

    # -- worker ---------------------------------------------------------------
    def _worker_loop(self):
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            self.queue_size_changed.emit(self._queue.qsize())
            try:
                self._process(job)
            except Exception as e:
                logger.error(f"Job failed for {job.original_name}: {e}")
                self.log.emit(f"[error] {job.original_name}: {e}")

    def _process(self, job: Job):
        self.job_started.emit(job.original_name)
        self.log.emit(f"Starting hashcat on {job.original_name}")

        cmd = self._build_command(job.hash_path)
        if cmd is None:
            self.job_finished.emit(job.original_name, 0)
            return

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self.log.emit(line)
            proc.wait()
        except FileNotFoundError:
            self.log.emit(f"hashcat not found at: {self.settings.hashcat_path}")
            self.job_finished.emit(job.original_name, 0)
            return
        except Exception as e:
            self.log.emit(f"hashcat error: {e}")
            self.job_finished.emit(job.original_name, 0)
            return

        new_count = self._collect_cracked(job.hash_path)
        self.job_finished.emit(job.original_name, new_count)

    def _build_command(self, hash_path):
        hc = self.settings.hashcat_path
        if not hc or not os.path.isfile(hc):
            self.log.emit("hashcat.exe path is not configured (see Settings) - skipping job.")
            return None
        wordlist = self.settings.wordlist_path
        if not wordlist or not os.path.isfile(wordlist):
            self.log.emit("No wordlist configured (see Settings) - cannot crack.")
            return None
        cmd = [
            hc,
            "-m", "22000",
            "-a", "0",
            "--potfile-path", self.settings.potfile_path,
            "--quiet",
            hash_path,
            wordlist,
        ]
        rules = self.settings.rules_path
        if rules and os.path.isfile(rules):
            cmd.extend(["-r", rules])
        if self.settings.gpu_device:
            cmd.extend(["-d", self.settings.gpu_device])
        return cmd

    def _collect_cracked(self, hash_path):
        """Run --show against this hash file and merge any cracked
        results into the persisted table. Returns number of *new* entries."""
        hc = self.settings.hashcat_path
        cmd = [
            hc, "-m", "22000",
            "--potfile-path", self.settings.potfile_path,
            "--show", hash_path,
        ]
        try:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as e:
            self.log.emit(f"Could not read potfile results: {e}")
            return 0

        new_count = 0
        for line in out.stdout.splitlines():
            entry = self._parse_show_line(line)
            if not entry:
                continue
            with self._lock:
                if entry.key() not in self._results:
                    self._results[entry.key()] = entry
                    new_count += 1
                    self.cracked_found.emit(entry.__dict__)
        if new_count:
            self._save_results()
        return new_count

    @staticmethod
    def _parse_show_line(line: str):
        """
        `hashcat -m 22000 --show` prints cracked lines shaped like:
          WPA*02*MIC*BSSID_HEX*STA_HEX*ESSID_HEX*...*...:<password>
        Split off the trailing password, then pull the BSSID/ESSID back out
        of the hex-encoded hash fields.
        """
        if not line or ":" not in line:
            return None
        hash_part, password = line.rsplit(":", 1)
        fields = hash_part.split("*")
        if len(fields) < 6 or fields[0] != "WPA":
            return None
        bssid_hex = fields[3]
        essid_hex = fields[5]
        try:
            bssid = ":".join(bssid_hex[i:i + 2] for i in range(0, len(bssid_hex), 2)).upper()
        except Exception:
            bssid = bssid_hex
        try:
            ssid = bytes.fromhex(essid_hex).decode("utf-8", errors="replace")
        except Exception:
            ssid = essid_hex
        return CrackedEntry(ssid=ssid, bssid=bssid, password=password)
