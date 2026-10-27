"""
Ping Gu - Presets, Constants & Config Management
Arctic Tuxedo theme constants, curated server lists, game simulation profiles,
and single-EXE safe local configuration persistence.
"""

import ctypes
import json
import os
import sys
import tkinter as tk
from typing import Any, Dict, List, Optional

# ============================================================================
# 1. PING GU THEME PALETTE & UI CONSTANTS
# ============================================================================
BG_TUXEDO_DARK = ("#F3F4F6", "#0D0F12")       # Deep slate arctic navy
CARD_DARK = ("#FFFFFF", "#15181D")            # Container card slate
TEXT_SNOW = ("#14171C", "#E8EAED")            # Crisp icy white text
ACCENT_BEAK_ORANGE = ("#D9480F", "#E8590C")   # Pingu beak vibrant orange
ACCENT_GLACIER_BLUE = ("#2F6FB5", "#6CA0DC")  # High-tech glacial cyan
STATUS_GREEN = ("#1E8E57", "#4CB782")         # Low ping / rock-solid stability
STATUS_YELLOW = ("#B7791F", "#E2B340")        # Moderate latency / jitter caution
STATUS_RED = ("#D6372E", "#E5534B")           # High ping / packet loss / lag spike
STATUS_OVERCAP_PURPLE = ("#7C4DD6", "#9D7BE0")# Severe spike exceeding visual ceiling (>250ms)

# Typography: Rajdhani for headings / numerics, Barlow for body text
FONT_HEAD = "Rajdhani"
FONT_BODY = "Barlow"

# Visual graph ceiling constant: pings above 250ms are visually capped at 100% bar width
GRAPH_MAX_CAP_MS = 250.0

# ============================================================================
# 2. CURATED SERVER PRESETS
# ============================================================================
DEFAULT_SERVERS: List[Dict[str, Any]] = [
    # Baseline Reliable Pings
    {
        "name": "Cloudflare Edge DNS",
        "category": "Baseline DNS",
        "host": "1.1.1.1",
        "port": 53,
        "description": "Ultra-fast global anycast DNS edge resolver."
    },
    {
        "name": "Google Public DNS",
        "category": "Baseline DNS",
        "host": "8.8.8.8",
        "port": 53,
        "description": "Google worldwide anycast primary DNS."
    },
    {
        "name": "Quad9 Security DNS",
        "category": "Baseline DNS",
        "host": "9.9.9.9",
        "port": 53,
        "description": "Anycast recursive DNS with malware filtering."
    },

    # SEA & Asia Game Datacenters
    {
        "name": "AWS Singapore (SEA Game Hub)",
        "category": "SEA / Asia Games",
        "host": "ec2.ap-southeast-1.amazonaws.com",
        "port": 443,
        "description": "Amazon Web Services Singapore ap-southeast-1 region."
    },
    {
        "name": "Google Cloud Singapore (SEA)",
        "category": "SEA / Asia Games",
        "host": "34.87.0.1",
        "port": 443,
        "description": "GCP asia-southeast1 gateway / Singapore edge."
    },
    {
        "name": "Albion Online East (Singapore Gateway)",
        "category": "SEA / Asia Games",
        "host": "login-east.albiononline.com",
        "port": 443,
        "description": "Albion Online Asia-Pacific server login gateway."
    },
    {
        "name": "AWS Tokyo (East Asia Hub)",
        "category": "East Asia",
        "host": "ec2.ap-northeast-1.amazonaws.com",
        "port": 443,
        "description": "AWS Tokyo ap-northeast-1 data center."
    },
    {
        "name": "AWS Hong Kong",
        "category": "East Asia",
        "host": "ec2.ap-east-1.amazonaws.com",
        "port": 443,
        "description": "AWS Hong Kong ap-east-1 data center."
    },

    # Global Hubs
    {
        "name": "AWS Sydney (Oceania)",
        "category": "Global Hubs",
        "host": "ec2.ap-southeast-2.amazonaws.com",
        "port": 443,
        "description": "AWS Sydney ap-southeast-2 data center."
    },
    {
        "name": "AWS Frankfurt (EU Central)",
        "category": "Global Hubs",
        "host": "ec2.eu-central-1.amazonaws.com",
        "port": 443,
        "description": "AWS Frankfurt eu-central-1 European data hub."
    },
    {
        "name": "AWS Oregon (US West)",
        "category": "Global Hubs",
        "host": "ec2.us-west-2.amazonaws.com",
        "port": 443,
        "description": "AWS Oregon us-west-2 North America West data hub."
    },
]

# ============================================================================
# 3. GAME GENRE SIMULATION PROFILES
# ============================================================================
GENRE_PROFILES: Dict[str, Dict[str, Any]] = {
    "Standard Ping": {
        "payload_bytes": 32,
        "pings_per_sec": 1,
        "description": "Standard ICMP ping (32 bytes @ 1Hz) for light baseline connectivity monitoring.",
        "high_resource_warning": False,
    },
    "Tactical Shooter (CS2 / Valorant)": {
        "payload_bytes": 256,
        "pings_per_sec": 20,
        "description": "High-tickrate simulation (256 bytes @ 20Hz) to detect sub-frame micro-jitter and packet bursts.",
        "high_resource_warning": False,
    },
    "MOBA / Action (Dota 2 / LoL)": {
        "payload_bytes": 512,
        "pings_per_sec": 10,
        "description": "Action command simulation (512 bytes @ 10Hz) for testing responsiveness in teamfights.",
        "high_resource_warning": False,
    },
    "MMO / Open World (Albion ZvZ / Raids)": {
        "payload_bytes": 1350,
        "pings_per_sec": 10,
        "description": "Near-MTU packet stress (1350 bytes @ 10Hz) simulating heavy open-world battles and ZvZ clashes.",
        "high_resource_warning": True,
    },
    "Custom Noot Stress": {
        "payload_bytes": 64,
        "pings_per_sec": 5,
        "description": "User-defined payload (32-1472 bytes) and frequency (1-50Hz) for custom stress tests.",
        "high_resource_warning": False,
    },
}

# ============================================================================
# 4. SINGLE-EXE SAFE CONFIG PERSISTENCE
# ============================================================================
def get_config_dir() -> str:
    """Returns portable directory path in %LOCALAPPDATA%\\PingGu."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        # Fallback for cross-platform or unpopulated env
        local_app_data = os.path.expanduser("~")
    config_dir = os.path.join(local_app_data, "PingGu")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_config_filepath() -> str:
    """Returns full file path for user_config.json."""
    return os.path.join(get_config_dir(), "user_config.json")


def load_user_config() -> Dict[str, Any]:
    """
    Safely loads custom user-saved servers and preferences.
    If the file does not exist or is corrupted, returns default configuration.
    """
    filepath = get_config_filepath()
    if not os.path.exists(filepath):
        return {
            "custom_servers": [],
            "selected_server_name": "Cloudflare Edge DNS",
            "selected_genre": "Tactical Shooter (CS2 / Valorant)",
            "custom_payload_bytes": 64,
            "custom_pings_per_sec": 5,
        }

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Config root is not a dictionary")
            return data
    except Exception:
        # Return fallback if read or parse fails
        return {
            "custom_servers": [],
            "selected_server_name": "Cloudflare Edge DNS",
            "selected_genre": "Tactical Shooter (CS2 / Valorant)",
            "custom_payload_bytes": 64,
            "custom_pings_per_sec": 5,
        }


def save_user_config(data: Dict[str, Any]) -> bool:
    """
    Saves user configuration to %LOCALAPPDATA%\\PingGu\\user_config.json.
    Returns True on success, False otherwise.
    """
    filepath = get_config_filepath()
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[presets] Error saving user config to {filepath}: {e}")
        return False


# ============================================================================
# 5. ASSET RESOLUTION & ICON GENERATOR
# ============================================================================
def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller single-exe bundles.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def ensure_app_icon() -> Optional[str]:
    """
    Checks if pingu.ico exists, or generates it from pingu.jpg.
    Returns the absolute path to pingu.ico, or None if unavailable.
    """
    ico_path = resource_path("pingu.ico")
    if os.path.exists(ico_path):
        return ico_path

    # Check project directory directly as well
    local_ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pingu.ico")
    if os.path.exists(local_ico):
        return local_ico

    jpg_path = resource_path("pingu.jpg")
    if not os.path.exists(jpg_path):
        fallback_jpg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pingu.jpg")
        if os.path.exists(fallback_jpg):
            jpg_path = fallback_jpg
        else:
            return None

    try:
        from PIL import Image
        img = Image.open(jpg_path)
        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        square_img = img.crop((left, top, left + min_dim, top + min_dim))

        dest_ico_path = os.path.join(os.path.dirname(os.path.abspath(jpg_path)), "pingu.ico")
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        square_img.save(dest_ico_path, format="ICO", sizes=icon_sizes)
        return dest_ico_path
    except Exception as e:
        print(f"[presets] Warning: Failed to generate pingu.ico: {e}")
        return None


def load_app_fonts() -> None:
    """
    Registers the bundled Rajdhani / Barlow TTFs for this process only (Windows),
    so they work without being installed system-wide. Must run before any Tk window.
    """
    if sys.platform != "win32":
        return
    fonts_dir = resource_path("fonts")
    if not os.path.isdir(fonts_dir):
        return
    FR_PRIVATE = 0x10
    add_font = ctypes.windll.gdi32.AddFontResourceExW
    for name in os.listdir(fonts_dir):
        if name.lower().endswith(".ttf"):
            add_font(os.path.join(fonts_dir, name), FR_PRIVATE, 0)


# ============================================================================
# THEME HELPERS (light / dark)
# Colours are (light, dark) tuples, which CustomTkinter resolves automatically.
# Raw tk widgets and canvas items need them resolved by hand.
# ============================================================================
def is_light_mode() -> bool:
    import customtkinter as ctk
    return ctk.get_appearance_mode() == "Light"


def pick_color(color: Any) -> Any:
    """Resolves a (light, dark) tuple to the colour for the current mode."""
    if isinstance(color, (tuple, list)):
        return color[0] if is_light_mode() else color[1]
    return color


class ThemedCanvas(tk.Canvas):
    """tk.Canvas that accepts (light, dark) colour tuples and can re-theme in place."""

    _ITEM_OPTS = ("fill", "outline")

    def __init__(self, master=None, **kw):
        self._item_specs: Dict[Any, Any] = {}
        self._bg_spec: Any = None
        if isinstance(kw.get("bg"), (tuple, list)):
            self._bg_spec = kw["bg"]
            kw["bg"] = pick_color(kw["bg"])
        super().__init__(master, **kw)

    def _create(self, itemType, args, kw):
        specs = {}
        for opt in self._ITEM_OPTS:
            if isinstance(kw.get(opt), (tuple, list)):
                specs[opt] = kw[opt]
                kw[opt] = pick_color(kw[opt])
        item = super()._create(itemType, args, kw)
        for opt, spec in specs.items():
            self._item_specs[(item, opt)] = spec
        return item

    def itemconfigure(self, tagOrId, cnf=None, **kw):
        if isinstance(tagOrId, int):
            for opt in self._ITEM_OPTS:
                if opt in kw:
                    if isinstance(kw[opt], (tuple, list)):
                        self._item_specs[(tagOrId, opt)] = kw[opt]
                        kw[opt] = pick_color(kw[opt])
                    else:
                        self._item_specs.pop((tagOrId, opt), None)
        return super().itemconfigure(tagOrId, cnf, **kw)

    itemconfig = itemconfigure

    def apply_theme(self) -> None:
        if self._bg_spec is not None:
            super().configure(bg=pick_color(self._bg_spec))
        for (item, opt), spec in self._item_specs.items():
            try:
                tk.Canvas.itemconfigure(self, item, **{opt: pick_color(spec)})
            except tk.TclError:
                pass
