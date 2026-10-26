<div align="center">
  <img src="pingu.jpg" width="110" alt="Ping Gu Logo" />
  <h1>Ping Gu</h1>
  <p><b>Lightweight Network Stability & Ping Monitor for Online Gaming</b></p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/Platform-Windows_10_%7C_11-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Platform" />
    <img src="https://img.shields.io/badge/License-MIT-22C55E?style=flat-square" alt="License" />
  </p>
</div>

---

## Overview

Web-based speed tests measure download bandwidth to a nearby local server over a few seconds. That tells you how fast a game update will download, not whether you will rubberband or drop packets in an actual match. Meanwhile, most dedicated ping utilities are either bloated, sketchy, or locked behind paid subscriptions.

**Ping Gu** is a free, open-source desktop utility built to check if your connection is actually ready before you queue. It tests sustained packet stability, tracks micro-jitter and worst-case spikes, and checks your local router in the background so you know whether lag is coming from your own Wi-Fi or your ISP.

---

## Features

* **Readiness Verdict:** Evaluates average ping, micro-jitter, 1% worst spikes (P99), and packet loss to give an immediate status (*Competitive Ready*, *Casual Only*, or *Do Not Queue*).
* **Local Router vs. ISP Isolation:** Simultaneously pings your local gateway alongside the target server. If a lag spike originates from your home Wi-Fi or local network instead of external routing, Ping Gu flags it directly.
* **Game Genre Profiles:** Simulate different network conditions by adjusting packet payload sizes and send rates:
  * **Standard:** 32 Bytes @ 1 ping/sec
  * **Tactical Shooter:** 256 Bytes @ 20 pings/sec (tests high-tickrate stability)
  * **MOBA / Action:** 512 Bytes @ 10 pings/sec
  * **MMO / Open World:** 1,350 Bytes @ 10 pings/sec (tests near-MTU large payloads)
  * **Custom:** Manual sliders for packet size (32–1472 B) and frequency (1–50 Hz)
* **Interactive Vertical Latency Graph:** Uses a vertical bar stream capped at 250ms so a single 999ms spike never squashes normal readings. Hover to pause scrolling, toggle local router bars on/off, or click any packet bar to inspect its details.
* **Load Test (Bufferbloat Check):** Optional 5-second background download test while pinging to see if household downloads or streaming cause your latency to spike.
* **Data Usage Guard & Custom Timer:** Tracks external WAN data used during a session and warns you before running heavy packet configurations or long timers.
* **Automatic TCP Fallback:** Automatically switches to TCP port handshakes (e.g., port 443/53) when target game datacenters block standard ICMP echo requests.

<img width="1909" height="1001" alt="image" src="https://github.com/user-attachments/assets/7df85fd2-7a5d-4379-9991-86aa8d90f568" />

---

## Download & Usage

### Option 1: Standalone Executable (No Installation Needed)
1. Go to the [**Releases**](../../releases) section on the right sidebar.
2. Download **`PingGu.exe`** from the latest release.
3. Run `PingGu.exe` directly—no Python installation or setup required.

### Option 2: Run from Source
Ensure you have Python 3.10+ installed on Windows:

```bash
git clone https://github.com/WisterWist/Ping-Gu.git
cd Ping-Gu
pip install -r requirements.txt
python main.py
```

### Build the Executable
```bash
pip install -r requirements-dev.txt
python build_exe.py
```
The output is `dist/PingGu.exe`.

### Run the Tests
```bash
python test_engine.py            # pings live targets
python test_graph.py             # opens real Tk windows
python test_app_integration.py   # opens real Tk windows
```
