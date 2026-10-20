<div align="center">

<img src="pingu.jpg" width="105" alt="Ping Gu Logo" />

# 🐧 Ping Gu
### **Gaming Readiness & Network Stability Monitor**
*The Arctic Tuxedo "Noot-O-Meter" Desktop Monitor for Competitive Gamers*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-0284C7?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Build-Passing%20100%25-22C55E?style=for-the-badge)](#)

<p align="center">
  <b>Dual-hop gateway isolation &bull; Real-time micro-jitter tracking &bull; 0-flicker virtualized canvas &bull; Bufferbloat stress testing &bull; Game genre traffic simulation</b>
</p>

</div>

---

## 🎮 Why Ping Gu? (The Problem It Solves)

Standard web-based speed tests (Speedtest.net, Fast.com) measure **bulk bandwidth throughput** (Megabits per second) to local ISP servers over a brief 5-second download burst. 

**Bandwidth throughput is virtually meaningless for competitive online gaming:**
* Multiplayer games (CS2, Valorant, Apex Legends, League of Legends, Dota 2, WoW) require only **~50–150 Kbps** of bandwidth.
* What decides your hit-registration, movement smoothness, and rubberbanding is **packet pacing, sub-5ms micro-jitter, sub-frame latency stability, and zero packet loss**.
* When you lag in-game, standard speed tests cannot answer the million-dollar question: **"Is this lag happening inside my house (Wi-Fi channel congestion, someone streaming 4K) or is it external (ISP routing hops or game server overload)?"**

**Ping Gu** is engineered from the ground up to solve this exact problem. It continuously probes your game target while silently pinging your local gateway in parallel, providing instant root-cause diagnosis, visual forensics, and peace of mind before you queue competitive ranked games.

---

## ✨ Key Features

### 1. 🦭 Noot-O-Meter Verdict Engine
Instant, real-time diagnostic rating computed from a rolling 5,000-sample statistical window:
* 🟢 **NOOT EXCELLENT (Competitive Ready):** Sub-35ms ping, 0% packet loss, micro-jitter $<5$ms. Frame-perfect input response.
* 🟡 **NOOT PLAYABLE (Multiplayer Friendly):** Sub-75ms ping, minimal jitter. Smooth for casual games and MMOs.
* 🟠 **WARNING / NOOT STUTTER (Elevated Jitter):** High variance or bufferbloat queuing. Hitches and desync during fights.
* 🔴 **NOOT DISASTER (Do Not Queue):** Packet loss $\ge 2\%$ or severe latency spikes ($>150$ms). Rubberbanding, phantom shots, and disconnect risk.

### 2. 🏠 Silent Dual-Hop "Igloo vs. Blizzard" Diagnostics
Ping Gu simultaneously sends dual-hop telemetry:
* **Hop 1 (Local Router / "Your Igloo"):** Auto-detects your home gateway (`192.168.1.1` / `172.x.x.x`). If this spikes ($>15$ms), the lag is inside your house (Wi-Fi interference, local downloads).
* **Hop 2 (Target Server / "Blizzard Outside"):** Measures external game server latency. If Hop 1 is solid ($\le 2$ms) but Hop 2 spikes, your home Wi-Fi is blameless—the bottleneck is your ISP routing or game datacenter.

### 3. 🎯 Game Genre Traffic Simulation
Different genres transmit network packets in vastly different patterns:
* **Tactical Shooter (CS2 / Valorant):** $20\text{ pings/sec (Hz)}$ with small $64\text{B}$ packets to reveal frame-by-frame micro-stutters.
* **Battle Royale (Apex / Warzone):** $10\text{ pings/sec (Hz)}$ with $128\text{B}$ packets simulating medium tick-rate action.
* **MMO / Raid (WoW / FFXIV):** $2\text{ pings/sec (Hz)}$ with large $1350\text{B}$ near-MTU packets to stress packet fragmentation under crowded combat load.
* **Custom Noot Stress:** Fully customizable payload size ($32$ to $1472\text{ bytes}$) and ping frequency ($1$ to $50\text{ Hz}$).

### 4. ⚡ Zero-Flicker Virtualized Interactive Latency Stream
* **High-Performance Virtualization:** Uses a single native `tk.Canvas` with viewport slot recycling, maintaining 60 FPS even when streaming 5,000+ packets.
* **250ms Visual Ceiling:** Prevents massive 1,500ms lag spikes from squashing normal 15–30ms latency bars into unreadable slivers.
* **Interactive Inspection:** Hover to pause auto-scroll; click any packet bar to view its instant root-cause forensic diagnosis.
* **Dual Split-Bar Overlay:** Toggle **"Show Local Ping"** to render home router latency directly inside the packet bar with turquoise split tracks.

### 5. 🐟 Bufferbloat (5s Load Test) & Live WAN Data Guard
* **Bufferbloat Stress Burst:** Streams a 5-second Cloudflare speed testing burst while concurrent gaming pings run, verifying if your router's queueing (SQM/QoS) protects gaming packets during heavy household traffic.
* **Pre-Flight Data Estimator:** Live calculation of projected MB/minute before firing scans.
* **Custom User Timer:** Run scans for custom seconds, minutes, or `Continuous ∞` with real-time countdown.
* **Smart "Unwise Action" Warnings:** Dynamic safety evaluation that warns you before starting high-bandwidth or excessively long scans.
* **Full Boot-State `"↺ Reset"` Button:** One-click return of the entire application (Verdict, 5 Metric Cards, Graph, Counters, and Presets) to a fresh boot state.
* **Interactive Tooltips & Diagnostic Guide:** Comprehensive `?` badges on every control and a dedicated **"❓ Guide"** cheat-sheet modal.

---

## 🚀 Quick Start

### Option A: Standalone Windows Executable (No Python Required)
1. Download **`PingGu.exe`** from the [GitHub Releases](https://github.com/your-username/ping-gu/releases) page.
2. Double-click **`PingGu.exe`** to launch.
3. *(Optional)* Run as Administrator if your Windows policy requires elevated raw socket permissions for custom ICMP packet payloads. If run as a standard user, Ping Gu automatically falls back to OS-native ICMP / TCP handshake mode!

### Option B: Running from Source
```bash
# 1. Clone the repository
git clone https://github.com/your-username/ping-gu.git
cd ping-gu

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch Ping Gu
python main.py
```

### Option C: Compiling Standalone `.exe`
Build the single-file, zero-console Windows executable using the automated build script:
```bash
python build_exe.py
```
The compiled executable will be generated at `dist/PingGu.exe`.

---

## 📂 Project Architecture

Ping Gu follows a clean, decoupled modular design separated into backend measurement, statistical analysis, and zero-flicker presentation layers:

| Module | Primary Responsibility |
|---|---|
| [`main.py`](main.py) | Application entry point and CustomTkinter theme initializer. |
| [`ui_main.py`](ui_main.py) | Main window dashboard, responsive 2-row Control Deck, Verdict Banner, 5 Metric Cards, Custom Timer, and Modal dialogs (`WarningModal`, `QuickGuideModal`, `CustomServerModal`). |
| [`ui_vertical_graph.py`](ui_vertical_graph.py) | High-performance virtualized vertical bar-list graph using native `tk.Canvas` slot pooling, `InfoTooltip` system, and click-to-inspect forensic inspector. |
| [`scanner.py`](scanner.py) | Thread-safe Dual-Hop network scanner with automated gateway discovery, ICMP / TCP negotiation, and 5-second Cloudflare Bufferbloat burst engine. |
| [`analyzer.py`](analyzer.py) | Statistical rolling-window analyzer, P99 spike detection, sub-frame jitter calculation, WAN byte accumulator, and `evaluate_session_plan()` smart warning engine. |
| [`presets.py`](presets.py) | Arctic Tuxedo theme tokens, curated global/regional datacenter presets, game traffic profiles, and single-exe `resource_path()` asset resolvers. |
| [`build_exe.py`](build_exe.py) | Automated PyInstaller bundling pipeline with asset packaging (`pingu.ico`, `pingu.jpg`) and CustomTkinter asset collection. |

---

## 🧪 Test Suite

Ping Gu includes three comprehensive test harnesses covering the backend engine, graph virtualization, and full UI integration:

```bash
# Test 1: Core Dual-Hop backend, Bufferbloat, and gateway detection
python test_engine.py

# Test 2: Virtualized canvas culling, item recycling, and inspector selection
python test_graph.py --headless

# Test 3: Full end-to-end UI integration, custom timer, warnings, and boot reset
python test_app_integration.py
```

---

## 🎨 Arctic Tuxedo Theme Palette

| Token | Hex Code | Purpose |
|---|---|---|
| `BG_TUXEDO_DARK` | `#0F172A` | Deep slate arctic navy background |
| `CARD_DARK` | `#1E293B` | Container card surface slate |
| `TEXT_SNOW` | `#F8FAFC` | Crisp icy white text |
| `ACCENT_BEAK_ORANGE` | `#FF6B35` | Vibrant Pingu beak action accent |
| `ACCENT_GLACIER_BLUE` | `#38BDF8` | High-tech glacial telemetry highlight |
| `STATUS_GREEN` | `#22C55E` | Rock-solid / competitive readiness |
| `STATUS_YELLOW` | `#F59E0B` | Elevated latency / jitter caution |
| `STATUS_RED` | `#EF4444` | Packet loss / lag spike alert |
| `STATUS_OVERCAP_PURPLE` | `#A855F7` | Severe latency spike exceeding 250ms ceiling |

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

<div align="center">
  <b>Ping Gu</b> — Built with ❤️ for competitive gamers everywhere. <i>NOOT NOOT! 🐧</i>
</div>
