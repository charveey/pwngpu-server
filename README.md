# Pwnagotchi GPU Crack Server

A Windows tray app that pairs with the `pwngpu` pwnagotchi plugin
([charveey/pwnagotchi64-plugins](https://github.com/charveey/pwnagotchi64-plugins)).
Tether your pwnagotchi to your PC over USB, and handshakes get sent here
automatically and cracked locally with your GPU via hashcat.

## What it does

- Listens for `GET /health`, `POST /crack`, and `GET /results` — exactly
  what the plugin expects.
- Queues every uploaded `.hc22000` file and runs `hashcat -m 22000` against
  it in the background (the plugin's request only waits 60s, so cracking
  happens async and results get picked up the next time it polls).
- Shows live status, a log, and a running table of cracked SSID/BSSID/password
  in a system tray app.
- Can detect the USB tethering adapter and auto-assign the static IP the
  plugin expects as its gateway.
- Can launch at Windows login, minimized to tray, with the server
  auto-starting — set it up once and forget about it.

## 1. Install prerequisites

- **Python 3.10+** (only needed if running from source instead of the
  built exe).
- **hashcat for Windows** — download from https://hashcat.net/hashcat/ and
  unzip somewhere, e.g. `C:\hashcat\`. Make sure your GPU drivers
  (NVIDIA/AMD/Intel OpenCL or CUDA runtime) are installed, or hashcat will
  fall back to CPU-only.
- **A wordlist**, e.g. `rockyou.txt`. Point the app at it in Settings.

## 2. Run it

From source:

```
pip install -r requirements.txt
python main.py
```

Or build a standalone exe (recommended for the "seamless" experience —
no Python needed afterward):

```
build_exe.bat
```

This produces `dist\PwnGPUCrackServer.exe`. Copy it wherever you like, or
create a Start Menu / Desktop shortcut.

First run generates a random API key automatically — no setup needed
there. Open **Settings** and point `hashcat.exe` and the wordlist at the
right paths, then save.

## 3. USB networking (pwnagotchi <-> PC)

The plugin connects over the pwnagotchi's USB gadget interface (`usb0`),
expecting the PC to answer at `10.0.0.1`. When you plug the pwnagotchi
into your PC via a USB data cable:

1. Windows should detect a new network adapter (named something like
   "Remote NDIS based Internet Sharing Device", "USB Ethernet/RNDIS
   Gadget", or similar — driver name varies). If Windows doesn't install
   it automatically, check Device Manager for an unrecognized USB device
   and update its driver to the RNDIS/Ethernet gadget driver (this is a
   long-standing, well-documented step in Pi Zero/pwnagotchi USB-gadget
   guides — search "pwnagotchi usb0 RNDIS Windows driver" if you hit
   this).
2. The app's main window shows **USB link: detected** once it sees this
   adapter. If it has no IP yet, click **Configure USB Adapter IP** (or
   just run the app as Administrator — it'll do this automatically) to
   assign it `10.0.0.1 / 255.255.255.0`, matching the plugin's expected
   gateway.
3. With the adapter configured, `GET http://10.0.0.1:6881/health` from
   the pwnagotchi side should succeed once your server is running.

If you'd rather not run as Administrator, set the static IP manually once
via *Settings > Network adapters* in Windows — it'll persist across
reboots without needing the app's help after that.

## 4. Install and configure the plugin

On the pwnagotchi itself, edit `/etc/pwnagotchi/config.toml` to add the
plugin repo:

```toml
main.custom_plugin_repos = [
    "https://github.com/charveey/pwnagotchi64-plugins/archive/master.zip",
    ]
```

Then pull it down:

```
sudo pwnagotchi plugins update
sudo pwnagotchi plugins enable pwngpu
```

Now configure it, still in `config.toml`:

```toml
main.plugins.pwngpu.enabled = true
main.plugins.pwngpu.api_key = "<the API key shown in the app>"
main.plugins.pwngpu.port = 6881
main.plugins.pwngpu.sleep = 1800
```

`server_url` can be left unset — the plugin defaults to
`http://10.0.0.1:<port>`, which matches what this app listens on once the
adapter IP is set. Restart the pwnagotchi (`sudo systemctl restart
pwnagotchi`) after editing the config.

## 6. Seamless day-to-day use

In **Settings**, enable:
- **Start server automatically when app opens**
- **Start minimized to tray**
- **Launch automatically when Windows starts**

After that, just leave the PC on. Whenever you plug the pwnagotchi in via
USB, the app picks up the link, the plugin sends handshakes, hashcat
chews on them in the background, and cracked passwords show up in the
table (with a tray notification) as they're found.

## Notes

- This only operates on handshakes your pwnagotchi has already captured —
  use it on networks you own or are authorized to test.
- Cracked results persist in `%USERPROFILE%\PwnGPU\cracked_results.json`
  across restarts.
- Logs and the hashcat potfile also live under `%USERPROFILE%\PwnGPU\`.
