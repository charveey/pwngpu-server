import logging
import secrets as secrets_mod
from flask import Flask, request, jsonify
from waitress import create_server
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("pwngpu.server")


def create_app(settings, runner):
    app = Flask("pwngpu")
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    def _check_key():
        key = request.headers.get("X-API-Key", "")
        return bool(key) and secrets_mod.compare_digest(key, settings.api_key)

    @app.get("/health")
    def health():
        if not _check_key():
            return jsonify({"error": "unauthorized"}), 401
        return jsonify({"status": "ok"})

    @app.post("/crack")
    def crack():
        if not _check_key():
            return jsonify({"error": "unauthorized"}), 401
        if "file" not in request.files:
            return jsonify({"error": "missing file"}), 400
        f = request.files["file"]
        data = f.read()
        runner.enqueue(data, f.filename or "upload.hc22000")
        # Respond immediately - the plugin only waits 60s here. Actual
        # cracking happens asynchronously; results surface later via
        # GET /results, which the plugin polls periodically.
        return jsonify({"cracked": [], "total": 0, "queued": True})

    @app.get("/results")
    def results():
        if not _check_key():
            return jsonify({"error": "unauthorized"}), 401
        return jsonify({"cracked": runner.all_results()})

    return app


class ServerThread(QThread):
    started_ok = pyqtSignal(bool, str)

    def __init__(self, settings, runner):
        super().__init__()
        self.settings = settings
        self.runner = runner
        self._server = None

    def run(self):
        app = create_app(self.settings, self.runner)
        try:
            self._server = create_server(app, host=self.settings.static_ip, port=self.settings.port)
        except OSError as e:
            self.started_ok.emit(False, str(e))
            return
        self.started_ok.emit(True, "")
        self._server.run()   # blocks until close() is called from stop()

    def stop(self):
        if self._server is not None:
            self._server.close()
