import sys
import logging

from PyQt6.QtWidgets import QApplication

from core.settings import Settings
from core.hashcat_runner import HashcatRunner
from ui.main_window import MainWindow


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # tray controls lifecycle, not window close

    settings = Settings()
    runner = HashcatRunner(settings)
    runner.start()

    window = MainWindow(settings, runner)

    minimized = "--minimized" in sys.argv or settings.start_minimized
    if not minimized:
        window.show()

    if settings.auto_start_server:
        window.start_server(silent=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
