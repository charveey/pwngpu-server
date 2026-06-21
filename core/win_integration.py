import os
import sys

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import ctypes
    import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "PwnGPUCrackServer"


def is_admin() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def set_launch_at_login(enabled: bool):
    """Add/remove a per-user (HKCU) Run key entry. No admin rights needed."""
    if not IS_WINDOWS:
        return
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
    try:
        if enabled:
            exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
            cmd = f'"{exe}" --minimized'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)
