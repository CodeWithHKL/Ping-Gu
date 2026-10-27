# -*- coding: utf-8 -*-
"""
Ping Gu - Main Desktop Application Dashboard (ui_main.py)
Complete Arctic Tuxedo dark-mode GUI dashboard featuring real-time telemetry cards,
responsive 2-row control deck, state-guarded zero-flicker widget configuration,
and virtualized vertical bar-list graph integration.
"""

from collections import deque
import os
import queue
import re
import threading
import time
import tkinter as tk
from typing import Any, Dict, List, Optional

import customtkinter as ctk

from analyzer import (
    SessionAnalyzer,
    SessionPlanEvaluation,
    estimate_data_usage,
    evaluate_session_plan,
    format_wan_bytes,
)
from presets import (
    FONT_BODY,
    FONT_HEAD,
    ACCENT_BEAK_ORANGE,
    ACCENT_GLACIER_BLUE,
    BG_TUXEDO_DARK,
    CARD_DARK,
    DEFAULT_SERVERS,
    GENRE_PROFILES,
    GRAPH_MAX_CAP_MS,
    STATUS_GREEN,
    STATUS_OVERCAP_PURPLE,
    STATUS_RED,
    STATUS_YELLOW,
    TEXT_SNOW,
    ensure_app_icon,
    load_user_config,
    resource_path,
    save_user_config,
)
from PIL import Image, ImageTk
from scanner import DualHopScanner, PingSample, get_default_gateway_ip
from ui_vertical_graph import (
    InfoTooltip,
    VerticalPingGraph,
    create_help_badge,
)


class CustomServerModal(ctk.CTkToplevel):
    """Modal dialog for adding custom game servers or datacenter IPs."""

    def __init__(self, parent: ctk.CTk, on_save_callback):
        super().__init__(parent)
        self.on_save_callback = on_save_callback

        self.title("Add Custom Game Server / IP")
        self.geometry("480x390")
        self.minsize(460, 360)
        self.resizable(True, True)
        self.configure(fg_color=BG_TUXEDO_DARK)
        self.transient(parent)
        self.grab_set()

        # Apply icon after delay to avoid Windows CTkToplevel override
        self.after(200, self._apply_icon)
        self.bind("<Return>", lambda event: self._on_save())
        self.bind("<Escape>", lambda event: self.destroy())

        self._build_ui()
        self.center_window(parent)

    def _apply_icon(self) -> None:
        try:
            if not self.winfo_exists():
                return
            ico_path = ensure_app_icon()
            if ico_path and os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except Exception:
            pass

    def center_window(self, parent: ctk.CTk) -> None:
        """Centers modal over parent window."""
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()

        w = 480
        h = 390
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        card = ctk.CTkFrame(self, fg_color=CARD_DARK, corner_radius=4, border_width=1, border_color=("#D5D9E0", "#262B33"))
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # 1. PIN BOTTOM FOOTER FIRST
        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(side="bottom", fill="x", padx=16, pady=(10, 14))

        btn_cancel = ctk.CTkButton(
            btn_box,
            text="Cancel",
            width=95,
            height=34,
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            fg_color=("#D5D9E0", "#262B33"),
            text_color=TEXT_SNOW,
            hover_color=("#B8BFC9", "#3A414C"),
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_save = ctk.CTkButton(
            btn_box,
            text="Save & Select Target",
            width=165,
            height=34,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color=ACCENT_BEAK_ORANGE,
            text_color="#FFFFFF",
            hover_color=("#B53B0A", "#C2410C"),
            command=self._on_save
        )
        btn_save.pack(side="right")

        # 2. HEADER & INPUT FIELDS
        title = ctk.CTkLabel(
            card,
            text="Register Custom Game Target",
            font=ctk.CTkFont(family=FONT_HEAD, size=16, weight="bold"),
            text_color=TEXT_SNOW
        )
        title.pack(side="top", anchor="w", padx=16, pady=(16, 4))

        subtitle = ctk.CTkLabel(
            card,
            text="Enter IP or hostname with optional TCP fallback port.",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=("#5B6472", "#9BA3AF")
        )
        subtitle.pack(side="top", anchor="w", padx=16, pady=(0, 12))

        # Scrollable form body ensures small screens never clip inputs
        form_frame = ctk.CTkScrollableFrame(card, fg_color="transparent")
        form_frame.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 4))

        # 1. Server Name
        lbl_name = ctk.CTkLabel(form_frame, text="Server Name / Display Label:", font=ctk.CTkFont(family=FONT_BODY, size=12), text_color=TEXT_SNOW)
        lbl_name.pack(anchor="w", padx=4, pady=(2, 2))
        self.entry_name = ctk.CTkEntry(form_frame, placeholder_text="e.g. Frankfurt Community Node", fg_color=("#F3F4F6", "#0D0F12"), border_color=("#D5D9E0", "#262B33"), text_color=TEXT_SNOW)
        self.entry_name.pack(fill="x", padx=4, pady=(0, 8))

        # 2. Host / IP
        lbl_host = ctk.CTkLabel(form_frame, text="Host or IPv4 Address:", font=ctk.CTkFont(family=FONT_BODY, size=12), text_color=TEXT_SNOW)
        lbl_host.pack(anchor="w", padx=4, pady=(2, 2))
        self.entry_host = ctk.CTkEntry(form_frame, placeholder_text="e.g. 198.51.100.24 or game.hub.com", fg_color=("#F3F4F6", "#0D0F12"), border_color=("#D5D9E0", "#262B33"), text_color=TEXT_SNOW)
        self.entry_host.pack(fill="x", padx=4, pady=(0, 8))

        # 3. Port
        lbl_port = ctk.CTkLabel(form_frame, text="TCP Fallback Port (if ICMP is blocked):", font=ctk.CTkFont(family=FONT_BODY, size=12), text_color=TEXT_SNOW)
        lbl_port.pack(anchor="w", padx=4, pady=(2, 2))
        self.entry_port = ctk.CTkEntry(form_frame, placeholder_text="443", fg_color=("#F3F4F6", "#0D0F12"), border_color=("#D5D9E0", "#262B33"), text_color=TEXT_SNOW)
        self.entry_port.insert(0, "443")
        self.entry_port.pack(fill="x", padx=4, pady=(0, 6))

        self.lbl_error = ctk.CTkLabel(form_frame, text="", font=ctk.CTkFont(family=FONT_BODY, size=12), text_color=STATUS_RED)
        self.lbl_error.pack(anchor="w", padx=4, pady=(0, 2))

    def _on_save(self) -> None:
        name = self.entry_name.get().strip()
        host = self.entry_host.get().strip()
        port_str = self.entry_port.get().strip()

        if not name:
            self.lbl_error.configure(text="Please provide a friendly display name.")
            return
        if not host:
            self.lbl_error.configure(text="Please provide a host or IPv4 address.")
            return

        try:
            port = int(port_str) if port_str else 443
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            self.lbl_error.configure(text="Port must be an integer between 1 and 65535.")
            return

        server_dict = {
            "name": name,
            "category": "Custom",
            "host": host,
            "port": port,
            "description": f"Custom user target: {host}:{port}"
        }
        self.on_save_callback(server_dict)
        self.destroy()


class WarningModal(ctk.CTkToplevel):
    """Confirmation modal for high-bandwidth profiles or Bufferbloat stress tests."""

    def __init__(self, parent: ctk.CTk, message: str, on_proceed_callback, on_suppress_callback):
        super().__init__(parent)
        self.on_proceed_callback = on_proceed_callback
        self.on_suppress_callback = on_suppress_callback

        self.title("High Data / Network Load Warning")
        self.geometry("540x440")
        self.minsize(500, 390)
        self.resizable(True, True)
        self.configure(fg_color=BG_TUXEDO_DARK)
        self.transient(parent)
        self.grab_set()

        # Apply icon after delay to avoid Windows CTkToplevel override
        self.after(200, self._apply_icon)
        self.bind("<Return>", lambda event: self._on_proceed())
        self.bind("<Escape>", lambda event: self.destroy())

        self._build_ui(message)
        self.center_window(parent)

    def _apply_icon(self) -> None:
        try:
            if not self.winfo_exists():
                return
            ico_path = ensure_app_icon()
            if ico_path and os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except Exception:
            pass

    def center_window(self, parent: ctk.CTk) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()

        w = 540
        h = 440
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self, message: str) -> None:
        card = ctk.CTkFrame(self, fg_color=CARD_DARK, corner_radius=4, border_width=1, border_color="#B7791F")
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # 1. PIN FOOTER (CHECKBOX + ACTION BUTTONS) TO BOTTOM FIRST!
        # This reserves bottom space so long text above it can NEVER push buttons off-screen.
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=(10, 16))

        self.chk_suppress = ctk.CTkCheckBox(
            footer,
            text="Don't ask again this session",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=("#5B6472", "#9BA3AF"),
            fg_color=ACCENT_BEAK_ORANGE,
            hover_color=("#B53B0A", "#C2410C")
        )
        self.chk_suppress.pack(anchor="w", pady=(0, 12))

        btn_box = ctk.CTkFrame(footer, fg_color="transparent")
        btn_box.pack(fill="x")

        btn_cancel = ctk.CTkButton(
            btn_box,
            text="Cancel",
            width=95,
            height=36,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color=("#D5D9E0", "#262B33"),
            text_color=TEXT_SNOW,
            hover_color=("#B8BFC9", "#3A414C"),
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(10, 0))

        btn_proceed = ctk.CTkButton(
            btn_box,
            text="Proceed (Noot Noot!)",
            width=170,
            height=36,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color=ACCENT_BEAK_ORANGE,
            text_color="#FFFFFF",
            hover_color=("#B53B0A", "#C2410C"),
            command=self._on_proceed
        )
        btn_proceed.pack(side="right")

        # 2. TOP TITLE
        title = ctk.CTkLabel(
            card,
            text="High Data / Network Load Warning",
            font=ctk.CTkFont(family=FONT_HEAD, size=16, weight="bold"),
            text_color=("#B45309", "#FBBF24")
        )
        title.pack(side="top", anchor="w", padx=16, pady=(16, 8))

        # 3. MIDDLE SCROLLABLE TEXT AREA
        # Scrollable container prevents multi-line text from pushing the footer
        scroll_frame = ctk.CTkScrollableFrame(
            card,
            fg_color=("#F3F4F6", "#0D0F12"),
            corner_radius=4,
            border_width=1,
            border_color=("#D5D9E0", "#262B33")
        )
        scroll_frame.pack(side="top", fill="both", expand=True, padx=16, pady=(0, 4))

        lbl_msg = ctk.CTkLabel(
            scroll_frame,
            text=message,
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=TEXT_SNOW,
            justify="left",
            wraplength=440
        )
        lbl_msg.pack(anchor="w", padx=12, pady=10)

    def _on_proceed(self) -> None:
        if self.chk_suppress.get():
            self.on_suppress_callback(True)
        self.on_proceed_callback()
        self.destroy()


class InvalidTimerModal(ctk.CTkToplevel):
    """Modal dialog alerting user to invalid timer entry."""

    def __init__(self, parent: ctk.CTk, message: str):
        super().__init__(parent)
        self.title("Invalid Timer Input")
        self.geometry("460x240")
        self.minsize(420, 220)
        self.resizable(True, True)
        self.configure(fg_color=BG_TUXEDO_DARK)
        self.transient(parent)
        self.grab_set()

        self.after(200, self._apply_icon)
        self.bind("<Return>", lambda event: self.destroy())
        self.bind("<Escape>", lambda event: self.destroy())

        self._build_ui(message)
        self.center_window(parent)

    def _apply_icon(self) -> None:
        try:
            if not self.winfo_exists():
                return
            ico_path = ensure_app_icon()
            if ico_path and os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except Exception:
            pass

    def center_window(self, parent: ctk.CTk) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = 460
        h = 240
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self, message: str) -> None:
        card = ctk.CTkFrame(self, fg_color=CARD_DARK, corner_radius=4, border_width=1, border_color=STATUS_RED)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Pin button to bottom first
        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(side="bottom", fill="x", padx=16, pady=(10, 14))

        btn = ctk.CTkButton(
            btn_box,
            text="OK (Noot!)",
            width=110,
            height=32,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color=("#D5D9E0", "#262B33"),
            text_color=TEXT_SNOW,
            hover_color=("#B8BFC9", "#3A414C"),
            command=self.destroy
        )
        btn.pack(side="right")

        title = ctk.CTkLabel(
            card,
            text="Invalid Timer Duration",
            font=ctk.CTkFont(family=FONT_HEAD, size=16, weight="bold"),
            text_color=STATUS_RED
        )
        title.pack(side="top", anchor="w", padx=16, pady=(16, 6))

        lbl = ctk.CTkLabel(
            card,
            text=f"{message}\n\nResetting timer duration to 60 seconds.",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=TEXT_SNOW,
            justify="left",
            wraplength=390
        )
        lbl.pack(side="top", fill="both", expand=True, anchor="w", padx=16, pady=(0, 6))


class QuickGuideModal(ctk.CTkToplevel):
    """Cheat-sheet modal explaining Noot verdicts, lag isolation, and genre profiles."""

    def __init__(self, parent: ctk.CTk):
        super().__init__(parent)
        self.title("Ping Gu — Diagnostic Guide & Cheat Sheet")
        self.geometry("640x560")
        self.minsize(560, 460)
        self.resizable(True, True)
        self.configure(fg_color=BG_TUXEDO_DARK)
        self.transient(parent)
        self.grab_set()

        self.after(200, self._apply_icon)
        self.bind("<Escape>", lambda event: self.destroy())

        self._build_ui()
        self.center_window(parent)

    def _apply_icon(self) -> None:
        try:
            if not self.winfo_exists():
                return
            ico_path = ensure_app_icon()
            if ico_path and os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except Exception:
            pass

    def center_window(self, parent: ctk.CTk) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = 640
        h = 560
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        # PIN CLOSE BUTTON TO BOTTOM FIRST
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(side="bottom", fill="x", padx=16, pady=(8, 14))

        btn_close = ctk.CTkButton(
            btn_box,
            text="Close Guide (Noot!)",
            width=160,
            height=34,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color=("#D5D9E0", "#262B33"),
            text_color=TEXT_SNOW,
            hover_color=("#B8BFC9", "#3A414C"),
            command=self.destroy
        )
        btn_close.pack(side="right")

        # Scrollable container for the guide content fills the rest
        container = ctk.CTkScrollableFrame(
            self,
            fg_color=CARD_DARK,
            corner_radius=4,
            border_width=1,
            border_color=("#D5D9E0", "#262B33")
        )
        container.pack(side="top", fill="both", expand=True, padx=16, pady=(16, 0))

        title = ctk.CTkLabel(
            container,
            text="Ping Gu — Network Diagnostic Cheat-Sheet",
            font=ctk.CTkFont(family=FONT_HEAD, size=17, weight="bold"),
            text_color=TEXT_SNOW
        )
        title.pack(anchor="w", padx=12, pady=(10, 2))

        sub = ctk.CTkLabel(
            container,
            text="How to interpret Noot-O-Meter telemetry and isolate gaming lag.",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=("#5B6472", "#9BA3AF")
        )
        sub.pack(anchor="w", padx=12, pady=(0, 12))

        # Section 1: Verdicts
        sec1_title = ctk.CTkLabel(
            container,
            text="1. Noot-O-Meter Verdicts",
            font=ctk.CTkFont(family=FONT_HEAD, size=14, weight="bold"),
            text_color=ACCENT_GLACIER_BLUE
        )
        sec1_title.pack(anchor="w", padx=12, pady=(4, 2))

        verdicts = [
            ("NOOT EXCELLENT (Competitive Ready)", "Sub-35ms ping, 0% packet loss, micro-jitter < 5ms. Hit registration is instant; movements are frame-perfect."),
            ("NOOT PLAYABLE (Multiplayer Friendly)", "Ping 35-75ms, packet loss < 0.5%, jitter < 10ms. Smooth for MMOs, RPGs, and casual online games."),
            ("WARNING / NOOT STUTTER (Elevated Jitter)", "Jitter > 10ms or P99 spike > 90ms. Noticeable hitching during intense firefights or frame timing desync."),
            ("NOOT DISASTER (Severe Packet Loss / Lag)", "Packet loss >= 2.0% or extreme latency spikes (>150ms). Severe rubberbanding, phantom shots, and potential disconnections."),
        ]
        for v_name, v_desc in verdicts:
            v_box = ctk.CTkFrame(container, fg_color=("#F3F4F6", "#0D0F12"), corner_radius=3)
            v_box.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(v_box, text=v_name, font=ctk.CTkFont(family=FONT_BODY, size=11, weight="bold"), text_color=TEXT_SNOW).pack(anchor="w", padx=8, pady=(4, 1))
            ctk.CTkLabel(v_box, text=v_desc, font=ctk.CTkFont(family=FONT_BODY, size=11), text_color=("#5B6472", "#9BA3AF"), wraplength=520, justify="left").pack(anchor="w", padx=8, pady=(0, 4))

        # Section 2: Home Wi-Fi vs. ISP Lag Isolation
        sec2_title = ctk.CTkLabel(
            container,
            text="2. Isolating Lag: Home Wi-Fi (Igloo) vs. ISP (Blizzard)",
            font=ctk.CTkFont(family=FONT_HEAD, size=14, weight="bold"),
            text_color=ACCENT_BEAK_ORANGE
        )
        sec2_title.pack(anchor="w", padx=12, pady=(12, 2))

        iso_points = [
            ("Local Router Ping Spiking (>15ms)", "The problem is inside your house. Wi-Fi interference, someone streaming 4K, or local LAN saturation. Switch to Ethernet cable or restart your router."),
            ("Local Router Stable (<2ms), Server Ping Spiking", "Your home network is solid! The lag is on your ISP's side: peering congestion, bad WAN routing, or game server overload."),
            ("Bufferbloat (Load Test)", "If ping spikes dramatically when bandwidth is saturated, your router lacks SQM (Smart Queue Management) to prioritize gaming packets over downloads.")
        ]
        for i_name, i_desc in iso_points:
            i_box = ctk.CTkFrame(container, fg_color=("#F3F4F6", "#0D0F12"), corner_radius=3)
            i_box.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(i_box, text=i_name, font=ctk.CTkFont(family=FONT_BODY, size=11, weight="bold"), text_color=TEXT_SNOW).pack(anchor="w", padx=8, pady=(4, 1))
            ctk.CTkLabel(i_box, text=i_desc, font=ctk.CTkFont(family=FONT_BODY, size=11), text_color=("#5B6472", "#9BA3AF"), wraplength=520, justify="left").pack(anchor="w", padx=8, pady=(0, 4))

        # Section 3: Genre Modes
        sec3_title = ctk.CTkLabel(
            container,
            text="3. Game Genre Traffic Profiles",
            font=ctk.CTkFont(family=FONT_HEAD, size=14, weight="bold"),
            text_color=ACCENT_GLACIER_BLUE
        )
        sec3_title.pack(anchor="w", padx=12, pady=(12, 2))

        genres = [
            ("Tactical Shooter (CS2 / Valorant)", "20 Hz rate, small 64B packets. Simulates high tick-rate competitive shooters to reveal frame-by-frame micro-stutters."),
            ("Battle Royale (Apex / Warzone)", "10 Hz rate, 128B packets. Simulates typical medium tick-rate shooter traffic."),
            ("MMO / RTS Raid (WoW / FFXIV)", "2 Hz rate, large 1350B packets. Stresses MTU packet fragmentation for crowded boss encounters."),
            ("Custom Noot Stress", "Adjustable from 32B to 1472B payload and 1 to 50 Hz ping rate to test your connection to its absolute limits.")
        ]
        for g_name, g_desc in genres:
            g_box = ctk.CTkFrame(container, fg_color=("#F3F4F6", "#0D0F12"), corner_radius=3)
            g_box.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(g_box, text=g_name, font=ctk.CTkFont(family=FONT_BODY, size=11, weight="bold"), text_color=TEXT_SNOW).pack(anchor="w", padx=8, pady=(4, 1))
            ctk.CTkLabel(g_box, text=g_desc, font=ctk.CTkFont(family=FONT_BODY, size=11), text_color=("#5B6472", "#9BA3AF"), wraplength=520, justify="left").pack(anchor="w", padx=8, pady=(0, 4))


class PingGuApp(ctk.CTk):
    """
    Main Desktop Dashboard for Ping Gu.
    Integrates scanner, SessionAnalyzer, and VerticalPingGraph.
    """

    def __init__(self):
        super().__init__()

        # Windows Taskbar Icon Fix (Set AppUserModelID)
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pinggu.noot.monitor.1")
            except Exception:
                pass

        # Load / generate pingu.ico and apply to window & taskbar
        ico_path = ensure_app_icon()
        if ico_path and os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception as e:
                print(f"[ui_main] iconbitmap error: {e}")

        # Also set iconphoto using PhotoImage for cross-platform / taskbar fallback
        jpg_path = resource_path("pingu.jpg")
        if os.path.exists(jpg_path):
            try:
                pil_icon = Image.open(jpg_path).resize((64, 64))
                self._app_icon_photo = ImageTk.PhotoImage(pil_icon)
                self.wm_iconphoto(True, self._app_icon_photo)
            except Exception as e:
                print(f"[ui_main] wm_iconphoto error: {e}")

        # Appearance & Window Configuration
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Ping Gu — Gaming Readiness & Network Stability Monitor")
        self.geometry("1120x780")
        self.minsize(960, 680)
        self.configure(fg_color=BG_TUXEDO_DARK)

        # Core State
        self._user_config = load_user_config()
        self._gateway_ip = get_default_gateway_ip() or "192.168.1.1"

        # Scanning & Queue Architecture
        self._scanner: Optional[DualHopScanner] = None
        self._session_analyzer = SessionAnalyzer(maxlen=5000)
        self._sample_queue: queue.Queue[PingSample] = queue.Queue()
        self._is_scanning = False
        self._scan_start_time: float = 0.0
        self._active_scan_duration_sec: Optional[float] = 60.0
        self._suppress_data_warning = False

        # Anti-Flicker State Cache & Throttle Timers
        self._widget_state_cache: Dict[int, Dict[str, Any]] = {}
        self._last_telemetry_update: float = 0.0

        # Build UI Hierarchy
        self._build_header_bar()
        self._build_control_deck()
        self._build_verdict_banner()
        self._build_telemetry_pill_cards()
        self._build_graph_body()

        # Polling Loop for Thread-Safe UI Updates
        self._poll_timer_id = self.after(25, self._poll_sample_queue)

        # Graceful Window Termination
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

    # ========================================================================
    # STATE-CHANGE GUARD HELPER (ELIMINATES CTK REDRAW FLICKER)
    # ========================================================================
    def _safe_configure(self, widget: Any, **kwargs) -> None:
        """
        State-change guard that only calls widget.configure() for keys whose
        values have actually changed. Prevents CustomTkinter on Windows from
        regenerating rounded corner PIL surfaces on every tick.
        """
        w_id = id(widget)
        cached = self._widget_state_cache.setdefault(w_id, {})
        changed = {}
        for k, v in kwargs.items():
            if cached.get(k) != v:
                changed[k] = v
                cached[k] = v
        if changed:
            widget.configure(**changed)

    # ========================================================================
    # 1. HEADER BAR
    # ========================================================================
    @staticmethod
    def _theme_button_text() -> str:
        return "Dark Mode" if ctk.get_appearance_mode() == "Light" else "Light Mode"

    def _toggle_theme(self) -> None:
        """Switches between light and dark mode and remembers the choice."""
        new_mode = "Dark" if ctk.get_appearance_mode() == "Light" else "Light"
        ctk.set_appearance_mode(new_mode)
        self._user_config["theme"] = new_mode
        save_user_config(self._user_config)
        self.btn_theme.configure(text=self._theme_button_text())
        self.graph.apply_theme()

    def _build_header_bar(self) -> None:
        header = ctk.CTkFrame(self, fg_color=CARD_DARK, corner_radius=4, border_width=1, border_color=("#D5D9E0", "#262B33"))
        header.pack(fill="x", padx=12, pady=(10, 5))

        # Left: App Brand & Subtitle
        left_box = ctk.CTkFrame(header, fg_color="transparent")
        left_box.pack(side="left", padx=12, pady=8)

        brand_line = ctk.CTkFrame(left_box, fg_color="transparent")
        brand_line.pack(anchor="w")

        # Load pingu.jpg for in-app header logo (42x42 px)
        self._header_logo_img = None
        jpg_path = resource_path("pingu.jpg")
        if os.path.exists(jpg_path):
            try:
                pil_logo = Image.open(jpg_path).convert("RGBA")
                pil_logo = pil_logo.resize((42, 42), Image.Resampling.LANCZOS)
                self._header_logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(42, 42))
            except Exception as e:
                print(f"[ui_main] Error loading header logo: {e}")

        if self._header_logo_img:
            self.header_logo_lbl = ctk.CTkLabel(brand_line, text="", image=self._header_logo_img)
            self.header_logo_lbl.pack(side="left", padx=(0, 10))
            title_text = "PING GU"
        else:
            self.header_logo_lbl = None
            title_text = "PING GU"

        self.title_lbl = ctk.CTkLabel(
            brand_line,
            text=title_text,
            font=ctk.CTkFont(family=FONT_HEAD, size=20, weight="bold"),
            text_color=TEXT_SNOW
        )
        self.title_lbl.pack(side="left", padx=(0, 8))

        self.gw_badge = ctk.CTkLabel(
            brand_line,
            text=f"Local Router: {self._gateway_ip}",
            font=ctk.CTkFont(family=FONT_HEAD, size=13, weight="bold"),
            fg_color=("#F3F4F6", "#0D0F12"),
            text_color=ACCENT_GLACIER_BLUE,
            corner_radius=3,
            padx=8,
            pady=2
        )
        self.gw_badge.pack(side="left")

        subtitle_lbl = ctk.CTkLabel(
            left_box,
            text="Gaming Ping & Stability Monitor",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=("#5B6472", "#9BA3AF")
        )
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # Right: Live WAN Data Counter, Guide Button & Custom Timer Group
        right_box = ctk.CTkFrame(header, fg_color="transparent")
        right_box.pack(side="right", padx=12, pady=8)

        # WAN Data Counter Badge
        self.wan_badge = ctk.CTkLabel(
            right_box,
            text="Data Used: 0.0 KB",
            font=ctk.CTkFont(family=FONT_HEAD, size=13, weight="bold"),
            fg_color=("#F3F4F6", "#0D0F12"),
            text_color=ACCENT_GLACIER_BLUE,
            corner_radius=3,
            padx=10,
            pady=4
        )
        self.wan_badge.pack(side="left", padx=(0, 8))

        # ❓ Guide Button
        self.btn_guide = ctk.CTkButton(
            right_box,
            text="Guide",
            width=75,
            height=26,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color=("#D5D9E0", "#262B33"),
            text_color=TEXT_SNOW,
            hover_color=("#B8BFC9", "#3A414C"),
            command=self._open_guide_modal
        )
        self.btn_guide.pack(side="left", padx=(0, 6))

        self.btn_theme = ctk.CTkButton(
            right_box,
            text=self._theme_button_text(),
            width=75,
            height=26,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color=("#D5D9E0", "#262B33"),
            hover_color=("#B8BFC9", "#3A414C"),
            text_color=TEXT_SNOW,
            command=self._toggle_theme
        )
        self.btn_theme.pack(side="left", padx=(0, 10))

        # Inline Custom Timer Control Group
        timer_group = ctk.CTkFrame(right_box, fg_color="transparent")
        timer_group.pack(side="left")

        lbl_timer = ctk.CTkLabel(
            timer_group,
            text="Timer:",
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            text_color=TEXT_SNOW
        )
        lbl_timer.pack(side="left", padx=(0, 4))

        self.timer_entry = ctk.CTkEntry(
            timer_group,
            width=55,
            height=26,
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            justify="center",
            text_color=TEXT_SNOW,
            fg_color=("#F3F4F6", "#0D0F12"),
            border_color=("#D5D9E0", "#262B33")
        )
        self.timer_entry.insert(0, "60")
        self.timer_entry.pack(side="left", padx=(0, 4))

        self.timer_unit_menu = ctk.CTkOptionMenu(
            timer_group,
            values=["sec", "min", "Continuous ∞"],
            width=95,
            height=26,
            text_color=TEXT_SNOW,
            dropdown_text_color=TEXT_SNOW,
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            dropdown_font=ctk.CTkFont(family=FONT_BODY, size=12),
            fg_color=("#F3F4F6", "#0D0F12"),
            button_color=("#D5D9E0", "#262B33"),
            button_hover_color=("#B8BFC9", "#3A414C"),
            dropdown_fg_color=("#F3F4F6", "#0D0F12"),
            command=self._on_timer_unit_changed
        )
        self.timer_unit_menu.set("sec")
        self.timer_unit_menu.pack(side="left", padx=(0, 4))

        timer_help = create_help_badge(
            timer_group,
            "Set how long the scan runs in seconds or minutes, or choose Continuous. Long high-rate scans use more internet data.",
            title="Timer Help"
        )
        timer_help.pack(side="left")

    # ========================================================================
    # 2. RESPONSIVE 2-ROW CONTROL DECK
    # ========================================================================
    def _build_control_deck(self) -> None:
        """
        Responsive 2-Row Control Deck ensuring that target selection and action
        buttons never clip or hide on non-maximized windows.
        """
        self.deck = ctk.CTkFrame(self, fg_color=CARD_DARK, corner_radius=4, border_width=1, border_color=("#D5D9E0", "#262B33"))
        self.deck.pack(fill="x", padx=12, pady=4)

        # --------------------------------------------------------------------
        # ROW 0: Target Server Selection & Genre Profile Selection
        # --------------------------------------------------------------------
        row0 = ctk.CTkFrame(self.deck, fg_color="transparent")
        row0.pack(fill="x", padx=12, pady=(8, 4))

        # Target Server (Left side of Row 0)
        lbl_srv = ctk.CTkLabel(row0, text="Target Server:", font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"), text_color=TEXT_SNOW)
        lbl_srv.pack(side="left", padx=(0, 6))

        self._refresh_server_options()
        self.server_combo = ctk.CTkComboBox(
            row0,
            values=self._server_display_list,
            width=280,
            text_color=TEXT_SNOW,
            dropdown_text_color=TEXT_SNOW,
            dropdown_fg_color=CARD_DARK,
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            dropdown_font=ctk.CTkFont(family=FONT_BODY, size=12),
            fg_color=("#F3F4F6", "#0D0F12"),
            border_color=("#D5D9E0", "#262B33"),
            command=self._on_server_selected
        )
        saved_srv = self._user_config.get("selected_server_name", "Cloudflare Edge DNS")
        matched = [opt for opt in self._server_display_list if saved_srv in opt]
        self.server_combo.set(matched[0] if matched else self._server_display_list[0])
        self.server_combo.pack(side="left", padx=(0, 6))

        btn_add_srv = ctk.CTkButton(
            row0,
            text="+ Custom IP",
            width=90,
            height=28,
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            fg_color=("#D5D9E0", "#262B33"),
            text_color=TEXT_SNOW,
            hover_color=("#B8BFC9", "#3A414C"),
            command=self._open_custom_server_modal
        )
        btn_add_srv.pack(side="left", padx=(0, 24))

        # Genre Profile (Right side of Row 0)
        lbl_prof = ctk.CTkLabel(row0, text="Genre Profile:", font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"), text_color=TEXT_SNOW)
        lbl_prof.pack(side="left", padx=(0, 4))

        prof_help = create_help_badge(
            row0,
            "Simulates different game traffic patterns: Shooter sends 20 small packets/sec to catch micro-stutters; MMO sends large 1350-byte packets to stress-test crowded fights.",
            title="Genre Profile Help"
        )
        prof_help.pack(side="left", padx=(0, 6))

        self.genre_names = list(GENRE_PROFILES.keys())
        self.genre_combo = ctk.CTkComboBox(
            row0,
            values=self.genre_names,
            width=260,
            text_color=TEXT_SNOW,
            dropdown_text_color=TEXT_SNOW,
            dropdown_fg_color=CARD_DARK,
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            dropdown_font=ctk.CTkFont(family=FONT_BODY, size=12),
            fg_color=("#F3F4F6", "#0D0F12"),
            border_color=("#D5D9E0", "#262B33"),
            command=self._on_genre_selected
        )
        saved_genre = self._user_config.get("selected_genre", "Tactical Shooter (CS2 / Valorant)")
        self.genre_combo.set(saved_genre if saved_genre in self.genre_names else self.genre_names[1])
        self.genre_combo.pack(side="left")

        # --------------------------------------------------------------------
        # COLLAPSIBLE SUB-ROW: Dynamic Custom Sliders (for "Custom Noot Stress")
        # --------------------------------------------------------------------
        self.custom_sliders_frame = ctk.CTkFrame(self.deck, fg_color=("#F3F4F6", "#0D0F12"), corner_radius=4, border_width=1, border_color=("#D5D9E0", "#262B33"))
        slider_box = ctk.CTkFrame(self.custom_sliders_frame, fg_color="transparent")
        slider_box.pack(fill="x", padx=12, pady=6)

        # Slider 1: Payload Bytes (32 to 1472)
        self.lbl_slider_payload = ctk.CTkLabel(
            slider_box,
            text="Payload Size: 64 Bytes",
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            text_color=TEXT_SNOW,
            width=165,
            anchor="w"
        )
        self.lbl_slider_payload.pack(side="left", padx=(4, 6))

        self.slider_payload = ctk.CTkSlider(
            slider_box,
            from_=32,
            to=1472,
            number_of_steps=90,
            width=220,
            progress_color=ACCENT_GLACIER_BLUE,
            command=self._on_slider_payload_moved
        )
        self.slider_payload.set(self._user_config.get("custom_payload_bytes", 64))
        self.slider_payload.pack(side="left", padx=(0, 24))

        # Slider 2: Ping Rate (1 to 50 Hz)
        self.lbl_slider_rate = ctk.CTkLabel(
            slider_box,
            text="Ping Rate: 5 Hz (Ticks/sec)",
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            text_color=TEXT_SNOW,
            width=175,
            anchor="w"
        )
        self.lbl_slider_rate.pack(side="left", padx=(4, 6))

        self.slider_rate = ctk.CTkSlider(
            slider_box,
            from_=1,
            to=50,
            number_of_steps=49,
            width=220,
            progress_color=ACCENT_BEAK_ORANGE,
            command=self._on_slider_rate_moved
        )
        self.slider_rate.set(self._user_config.get("custom_pings_per_sec", 5))
        self.slider_rate.pack(side="left")

        # --------------------------------------------------------------------
        # ROW 1: Data Estimate (Left) and Pinned Action Buttons (Right)
        # --------------------------------------------------------------------
        row1 = ctk.CTkFrame(self.deck, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(4, 8))

        # Left: Pre-Flight Data Estimate Pill
        self.pill_estimate = ctk.CTkLabel(
            row1,
            text="Est. Data: ~0.65 MB / min",
            font=ctk.CTkFont(family=FONT_HEAD, size=13, weight="bold"),
            fg_color=("#F3F4F6", "#0D0F12"),
            text_color=ACCENT_GLACIER_BLUE,
            corner_radius=3,
            padx=10,
            pady=5
        )
        self.pill_estimate.pack(side="left")

        # Right: Action buttons (Pinned with side="right", never clipped!)
        self.btn_start = ctk.CTkButton(
            row1,
            text="▶ START NOOT SCAN",
            width=170,
            height=34,
            font=ctk.CTkFont(family=FONT_HEAD, size=14, weight="bold"),
            fg_color=ACCENT_BEAK_ORANGE,
            text_color="#FFFFFF",
            hover_color=("#B53B0A", "#C2410C"),
            command=self._toggle_scan
        )
        self.btn_start.pack(side="right", padx=(6, 0))

        self.btn_load_test = ctk.CTkButton(
            row1,
            text="Load Test (5s)",
            width=140,
            height=34,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color="transparent",
            border_width=1,
            border_color=("#B8BFC9", "#3A414C"),
            text_color=("#14171C", "#E8EAED"),
            text_color_disabled=("#7A828F", "#6B7280"),
            hover_color=("#D5D9E0", "#262B33"),
            state="disabled",
            command=self._on_load_test_click
        )
        self.btn_load_test.pack(side="right", padx=(4, 0))

        load_test_help = create_help_badge(
            row1,
            "Bufferbloat Check: Downloads a 5-second data burst while pinging to test if background downloads or 4K streams on your network cause your game ping to spike.",
            title="Load Test Help"
        )
        load_test_help.pack(side="right", padx=(4, 6))

        self.btn_reset = ctk.CTkButton(
            row1,
            text="↺ Reset",
            width=85,
            height=34,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color=("#D5D9E0", "#262B33"),
            text_color=TEXT_SNOW,
            hover_color=("#B8BFC9", "#3A414C"),
            command=self.reset_to_boot_state
        )
        self.btn_reset.pack(side="right", padx=(6, 0))

        # Initial estimate update
        self._update_preflight_estimate()
        if self.genre_combo.get() == "Custom Noot Stress":
            self.custom_sliders_frame.pack(fill="x", padx=12, pady=(0, 6))

    # ========================================================================
    # 3. NOOT-O-METER VERDICT BANNER & PROTOCOL BADGE
    # ========================================================================
    def _build_verdict_banner(self) -> None:
        self.verdict_card = ctk.CTkFrame(
            self,
            fg_color=CARD_DARK,
            corner_radius=4,
            border_width=1.5,
            border_color=("#D5D9E0", "#262B33")
        )
        self.verdict_card.pack(fill="x", padx=12, pady=4)

        top_line = ctk.CTkFrame(self.verdict_card, fg_color="transparent")
        top_line.pack(fill="x", padx=14, pady=(8, 2))

        # Default/Idle Verdict Title
        self.lbl_verdict_title = ctk.CTkLabel(
            top_line,
            text="CLICK SCAN NOOT — PICK A SERVER NOOT",
            font=ctk.CTkFont(family=FONT_HEAD, size=17, weight="bold"),
            text_color=STATUS_GREEN
        )
        self.lbl_verdict_title.pack(side="left")

        # Active Protocol Indicator Badge
        self.lbl_protocol_badge = ctk.CTkLabel(
            top_line,
            text="[Protocol: Standby]",
            font=ctk.CTkFont(family=FONT_HEAD, size=13, weight="bold"),
            fg_color=("#F3F4F6", "#0D0F12"),
            text_color=("#5B6472", "#9BA3AF"),
            corner_radius=3,
            padx=10,
            pady=2
        )
        self.lbl_protocol_badge.pack(side="right")

        # Subtitle / Root Cause Diagnosis
        self.lbl_root_cause = ctk.CTkLabel(
            self.verdict_card,
            text="Select your target datacenter and genre profile above, then click Start Noot Scan.",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=("#5B6472", "#9BA3AF"),
            anchor="w",
            justify="left"
        )
        self.lbl_root_cause.pack(fill="x", padx=14, pady=(0, 8))

    # ========================================================================
    # 4. LIVE TELEMETRY METRIC CARDS (5 COMPACT PILLS)
    # ========================================================================
    def _build_telemetry_pill_cards(self) -> None:
        self.telemetry_deck = ctk.CTkFrame(self, fg_color="transparent")
        self.telemetry_deck.pack(fill="x", padx=12, pady=4)

        cards_data = [
            (
                "AVG PING", "0.0 ms", "Live: -- ms", "pill_avg",
                "Average round-trip time to the server. Lower is faster, but Average Ping hides brief lag spikes—always check P99 Spike and Micro-Jitter too!"
            ),
            (
                "P99 SPIKE", "0.0 ms", "Worst 1% spike", "pill_p99",
                "Worst 1% Lag Spike. Even if your Average Ping is 20ms, a high P99 Spike (over 120ms) means you will feel sudden rubberbanding or delayed shots."
            ),
            (
                "MICRO-JITTER", "0.0 ms", "Sub-frame variance", "pill_jitter",
                "Ping variance from packet to packet. Under 5ms is rock-solid for competitive gaming; over 15ms makes movement and hit-reg feel stuttery."
            ),
            (
                "PACKET LOSS", "0.0 %", "0 dropped packets", "pill_loss",
                "Percentage of packets that never returned. Even 1% loss causes severe teleporting or unregistered inputs."
            ),
            (
                "IGLOO ROUTER", "0.0 ms", "Solid (Wi-Fi/LAN)", "pill_igloo",
                "Ping to your own home Wi-Fi/router. If this spikes over 15ms, the lag is happening inside your house (Wi-Fi interference or local traffic), NOT your ISP or game server!"
            ),
        ]

        self.telemetry_labels: Dict[str, Dict[str, Any]] = {}

        for i, (title, val, sub, key, tip_text) in enumerate(cards_data):
            card = ctk.CTkFrame(
                self.telemetry_deck,
                fg_color=CARD_DARK,
                corner_radius=4,
                border_width=1,
                border_color=("#D5D9E0", "#262B33")
            )
            card.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 6, 0))

            top_box = ctk.CTkFrame(card, fg_color="transparent")
            top_box.pack(fill="x", padx=12, pady=(8, 0))

            lbl_t = ctk.CTkLabel(top_box, text=title, font=ctk.CTkFont(family=FONT_BODY, size=11, weight="bold"), text_color=("#7A828F", "#6B7280"))
            lbl_t.pack(side="left")

            badge = create_help_badge(top_box, tip_text, title=f"{title} Help")
            badge.pack(side="right")

            lbl_v = ctk.CTkLabel(card, text=val, font=ctk.CTkFont(family=FONT_HEAD, size=28, weight="bold"), text_color=TEXT_SNOW)
            lbl_v.pack(anchor="w", padx=12, pady=(0, 0))

            lbl_s = ctk.CTkLabel(card, text=sub, font=ctk.CTkFont(family=FONT_BODY, size=11), text_color=("#5B6472", "#9BA3AF"))
            lbl_s.pack(anchor="w", padx=12, pady=(0, 8))

            self.telemetry_labels[key] = {
                "title": lbl_t,
                "val": lbl_v,
                "sub": lbl_s,
                "card": card,
                "badge": badge
            }

    # ========================================================================
    # 5. VERTICAL GRAPH INTEGRATION
    # ========================================================================
    def _build_graph_body(self) -> None:
        self.graph = VerticalPingGraph(
            self,
            maxlen=5000,
            show_local_igloo=False
        )
        self.graph.pack(fill="both", expand=True, padx=12, pady=(4, 10))

    # ========================================================================
    # 6. CONFIG & SERVER MANAGEMENT
    # ========================================================================
    def _refresh_server_options(self) -> None:
        """Combines DEFAULT_SERVERS with custom user-saved servers."""
        self._server_map: Dict[str, Dict[str, Any]] = {}
        self._server_display_list: List[str] = []

        # 1. Curated defaults
        for s in DEFAULT_SERVERS:
            disp = f"{s['name']} ({s['host']})"
            self._server_map[disp] = s
            self._server_display_list.append(disp)

        # 2. Custom user servers
        customs = self._user_config.get("custom_servers", [])
        for c in customs:
            disp = f"[Custom] {c['name']} ({c['host']})"
            self._server_map[disp] = c
            self._server_display_list.append(disp)

    def _get_selected_server(self) -> Dict[str, Any]:
        """Returns currently chosen server dictionary."""
        disp = self.server_combo.get()
        return self._server_map.get(disp, DEFAULT_SERVERS[0])

    def _open_custom_server_modal(self) -> None:
        CustomServerModal(self, on_save_callback=self._on_custom_server_saved)

    def _on_custom_server_saved(self, server_dict: Dict[str, Any]) -> None:
        """Saves custom server to user_config and updates dropdown."""
        customs = self._user_config.setdefault("custom_servers", [])
        customs = [c for c in customs if c.get("host") != server_dict["host"]]
        customs.append(server_dict)
        self._user_config["custom_servers"] = customs
        save_user_config(self._user_config)

        self._refresh_server_options()
        self.server_combo.configure(values=self._server_display_list)
        new_disp = f"[Custom] {server_dict['name']} ({server_dict['host']})"
        self.server_combo.set(new_disp)

    def _on_server_selected(self, choice: str) -> None:
        srv = self._server_map.get(choice)
        if srv:
            self._user_config["selected_server_name"] = srv["name"]
            save_user_config(self._user_config)

    # ========================================================================
    # 7. GENRE PROFILE & DATA ESTIMATION LOGIC
    # ========================================================================
    def _on_genre_selected(self, choice: str) -> None:
        self._user_config["selected_genre"] = choice
        save_user_config(self._user_config)

        if choice == "Custom Noot Stress":
            self.custom_sliders_frame.pack(fill="x", padx=12, pady=(0, 6))
        else:
            self.custom_sliders_frame.pack_forget()

        self._update_preflight_estimate()

    def _on_slider_payload_moved(self, value: float) -> None:
        val = int(value)
        self.lbl_slider_payload.configure(text=f"Payload Size: {val} Bytes")
        self._user_config["custom_payload_bytes"] = val
        save_user_config(self._user_config)
        self._update_preflight_estimate()

    def _on_slider_rate_moved(self, value: float) -> None:
        val = int(value)
        self.lbl_slider_rate.configure(text=f"Ping Rate: {val} Hz (Ticks/sec)")
        self._user_config["custom_pings_per_sec"] = val
        save_user_config(self._user_config)
        self._update_preflight_estimate()

    def _get_current_profile_params(self) -> tuple[int, int]:
        """Returns (payload_bytes, pings_per_sec) based on UI selections."""
        genre = self.genre_combo.get()
        if genre == "Custom Noot Stress":
            return int(self.slider_payload.get()), int(self.slider_rate.get())
        else:
            prof = GENRE_PROFILES.get(genre, GENRE_PROFILES["Standard Ping"])
            return prof["payload_bytes"], prof["pings_per_sec"]

    def _update_preflight_estimate(self) -> None:
        payload_bytes, pings_per_sec = self._get_current_profile_params()
        estimate = estimate_data_usage(payload_bytes, pings_per_sec)

        if estimate.needs_warning:
            self._safe_configure(
                self.pill_estimate,
                text=f"Est. Data: {estimate.human_str} [HIGH USAGE]",
                text_color=ACCENT_BEAK_ORANGE
            )
        else:
            self._safe_configure(
                self.pill_estimate,
                text=f"Est. Data: {estimate.human_str}",
                text_color=ACCENT_GLACIER_BLUE
            )

    # ========================================================================
    # 8. SCAN EXECUTION & THREADED QUEUE LOGIC
    # ========================================================================
    def _on_timer_unit_changed(self, choice: str) -> None:
        """Enables/disables numeric input depending on selected mode."""
        if "Continuous" in choice:
            self.timer_entry.configure(state="disabled")
        else:
            self.timer_entry.configure(state="normal")

    def _open_guide_modal(self) -> None:
        """Opens the Quick Diagnostic Guide popup cheat-sheet."""
        QuickGuideModal(self)

    def _toggle_scan(self) -> None:
        if self._is_scanning:
            self.stop_scan()
        else:
            self._check_warning_then_start()

    def _check_warning_then_start(self) -> None:
        """
        Validates custom timer entry and evaluates session load using
        evaluate_session_plan(). Shows InvalidTimerModal for non-positive input,
        or WarningModal if the session plan crosses unwise resource thresholds.
        """
        mode = self.timer_unit_menu.get()
        duration_input = self.timer_entry.get().strip()
        payload_bytes, pings_per_sec = self._get_current_profile_params()
        profile_name = self.genre_combo.get()

        eval_result = evaluate_session_plan(
            timer_val_str=duration_input,
            timer_unit=mode,
            profile_name=profile_name,
            payload_bytes=payload_bytes,
            pings_per_sec=pings_per_sec
        )

        if not eval_result.is_valid:
            InvalidTimerModal(self, message=eval_result.error_message)
            self.timer_entry.configure(state="normal")
            self.timer_entry.delete(0, "end")
            self.timer_entry.insert(0, "60")
            return

        self._active_scan_duration_sec = eval_result.duration_sec

        if eval_result.is_unwise and not self._suppress_data_warning:
            WarningModal(
                self,
                message=eval_result.warning_message,
                on_proceed_callback=self.start_scan,
                on_suppress_callback=self._set_suppress_warning
            )
        else:
            self.start_scan()

    def _set_suppress_warning(self, suppress: bool) -> None:
        self._suppress_data_warning = suppress

    def start_scan(self) -> None:
        """Initializes DualHopScanner and starts background sampling."""
        if self._is_scanning:
            return

        srv = self._get_selected_server()
        payload_bytes, pings_per_sec = self._get_current_profile_params()

        self._is_scanning = True
        self._scan_start_time = time.time()

        # Update UI Controls with live countdown state
        if self._active_scan_duration_sec is not None:
            init_btn_text = f"⏹ STOP SCAN ({int(self._active_scan_duration_sec)}s left)"
        else:
            init_btn_text = "⏹ STOP SCAN (Continuous)"

        self._safe_configure(
            self.btn_start,
            text=init_btn_text,
            fg_color=STATUS_RED,
            hover_color="#DC2626"
        )
        self.btn_load_test.configure(state="normal")
        self.server_combo.configure(state="disabled")
        self.genre_combo.configure(state="disabled")

        self._safe_configure(
            self.lbl_protocol_badge,
            text=f"[Probing: {srv['host']}...]",
            text_color=TEXT_SNOW
        )

        # Initialize Scanner
        self._scanner = DualHopScanner(
            target_host=srv["host"],
            target_port=srv.get("port", 443),
            payload_bytes=payload_bytes,
            pings_per_sec=pings_per_sec,
            gateway_ip=self._gateway_ip
        )
        self._scanner.start(callback=self._on_scanner_sample)

    def stop_scan(self, reason: str = "") -> None:
        """Gracefully halts active scanner."""
        if not self._is_scanning:
            return

        self._is_scanning = False
        if self._scanner:
            self._scanner.stop()
            self._scanner = None

        self._safe_configure(
            self.btn_start,
            text="▶ START NOOT SCAN",
            fg_color=ACCENT_BEAK_ORANGE,
            hover_color=("#B53B0A", "#C2410C")
        )
        self.btn_load_test.configure(state="disabled")
        self.server_combo.configure(state="normal")
        self.genre_combo.configure(state="normal")

        if reason:
            self._safe_configure(self.lbl_root_cause, text=f"ℹ{reason}")

    def _on_scanner_sample(self, sample: PingSample) -> None:
        """Called by background scanner thread; enqueues sample safely."""
        self._sample_queue.put(sample)

    def _on_load_test_click(self) -> None:
        """Triggered when user clicks 'Load Test (5s)'."""
        if not self._is_scanning or not self._scanner:
            return

        if not self._suppress_data_warning:
            msg = (
                "The Bufferbloat Load Test will stream a ~10-15 MB download burst "
                "from Cloudflare speed testing servers over the next 5 seconds.\n\n"
                "This stress-tests your router's queueing (SQM/QoS) while concurrent "
                "gaming pings are running."
            )
            WarningModal(
                self,
                message=msg,
                on_proceed_callback=self._execute_bufferbloat_burst,
                on_suppress_callback=self._set_suppress_warning
            )
        else:
            self._execute_bufferbloat_burst()

    def _execute_bufferbloat_burst(self) -> None:
        if self._scanner:
            self._safe_configure(
                self.btn_load_test,
                text="Loading (5s)...",
                state="disabled",
                fg_color="#9A3412"
            )
            self._scanner.trigger_bufferbloat_burst(duration_sec=5.0)

            def _restore_btn():
                if self._is_scanning:
                    self._safe_configure(
                        self.btn_load_test,
                        text="Load Test (5s)",
                        state="normal",
                        fg_color="transparent"
                    )

            self.after(5500, _restore_btn)

    # ========================================================================
    # 9. MAIN-THREAD SAMPLE POLLING & THROTTLED TELEMETRY UPDATES
    # ========================================================================
    def _poll_sample_queue(self) -> None:
        """
        Drains up to 50 samples from queue per tick, feeds them to SessionAnalyzer
        and VerticalPingGraph immediately for silky smooth live graph streaming.
        Throttles updating the top CTkLabel/CTkFrame telemetry widgets to at most
        5 times per second (every 200ms) to eliminate window flickering.
        """
        now = time.monotonic()
        processed_count = 0
        last_sample: Optional[PingSample] = None

        while not self._sample_queue.empty() and processed_count < 50:
            sample = self._sample_queue.get_nowait()
            self._session_analyzer.add_sample(sample)
            self.graph.add_sample(sample)
            last_sample = sample
            processed_count += 1

        # Throttle top telemetry cards and verdict banner to at most 5Hz (every 200ms)
        if (now - self._last_telemetry_update >= 0.20) or (not self._is_scanning and processed_count > 0):
            self._last_telemetry_update = now
            self._update_telemetry_ui(last_sample)
            self._check_auto_stop_conditions()

        self._poll_timer_id = self.after(25, self._poll_sample_queue)

    def _update_telemetry_ui(self, last_sample: Optional[PingSample]) -> None:
        """Updates metric cards, Verdict Banner, WAN counter and protocol badge."""
        metrics = self._session_analyzer.compute_metrics()

        # 1. Update WAN Counter Badge (Shortened Label)
        self._safe_configure(self.wan_badge, text=f"Data Used: {metrics['wan_data_str']}")

        # 2. Update Protocol Badge & Verdict Card
        if metrics["sample_count"] == 0 and not self._is_scanning:
            self._safe_configure(self.lbl_protocol_badge, text="[Protocol: Standby]", text_color=("#5B6472", "#9BA3AF"))
            self._safe_configure(
                self.lbl_verdict_title,
                text="CLICK SCAN NOOT — PICK A SERVER NOOT",
                text_color=STATUS_GREEN
            )
            self._safe_configure(self.verdict_card, border_color=("#D5D9E0", "#262B33"))
            self._safe_configure(
                self.lbl_root_cause,
                text="Select your target datacenter and genre profile above, then click Start Noot Scan."
            )
        else:
            if self._scanner:
                mode = self._scanner.protocol_mode
                if mode == "TCP":
                    proto_text = f"[Protocol: TCP Port {self._scanner.target_port} | OS Fixed Payload]"
                    proto_color = ACCENT_BEAK_ORANGE
                elif mode == "ICMP":
                    proto_text = f"[Protocol: ICMP | Payload: {self._scanner.payload_bytes}B]"
                    proto_color = STATUS_GREEN
                else:
                    proto_text = f"[Negotiating Protocol...]"
                    proto_color = TEXT_SNOW
                self._safe_configure(self.lbl_protocol_badge, text=proto_text, text_color=proto_color)

            # 3. Update Verdict Card
            self._safe_configure(
                self.lbl_verdict_title,
                text=metrics["verdict_title"],
                text_color=metrics["verdict_color"]
            )
            self._safe_configure(self.verdict_card, border_color=metrics["verdict_color"])
            self._safe_configure(self.lbl_root_cause, text=metrics["root_cause_summary"])

        # 4. Update 5 Metric Cards
        # Pill 1: Avg / Live Ping
        curr = f"{metrics['current_ms']:.1f} ms" if metrics["current_ms"] is not None else "-- ms"
        self._safe_configure(self.telemetry_labels["pill_avg"]["val"], text=f"{metrics['avg_ms']:.1f} ms")
        self._safe_configure(self.telemetry_labels["pill_avg"]["sub"], text=f"Live: {curr} (Min: {metrics['min_ms']:.0f})")

        # Pill 2: P99 Spike
        p99_color = STATUS_RED if metrics["p99_ms"] >= 150 else (STATUS_YELLOW if metrics["p99_ms"] >= 80 else TEXT_SNOW)
        self._safe_configure(self.telemetry_labels["pill_p99"]["val"], text=f"{metrics['p99_ms']:.1f} ms", text_color=p99_color)

        # Pill 3: Jitter
        jit_color = STATUS_RED if metrics["jitter_ms"] >= 15 else (STATUS_YELLOW if metrics["jitter_ms"] >= 6 else TEXT_SNOW)
        self._safe_configure(self.telemetry_labels["pill_jitter"]["val"], text=f"{metrics['jitter_ms']:.1f} ms", text_color=jit_color)

        # Pill 4: Packet Loss
        loss_color = STATUS_RED if metrics["loss_pct"] >= 2.0 else (STATUS_YELLOW if metrics["loss_pct"] > 0 else STATUS_GREEN)
        self._safe_configure(self.telemetry_labels["pill_loss"]["val"], text=f"{metrics['loss_pct']:.1f} %", text_color=loss_color)

        # Pill 5: Igloo Health
        if last_sample and last_sample.local_rtt_ms is not None:
            local_ms = last_sample.local_rtt_ms
            if local_ms > 15.0:
                self._safe_configure(self.telemetry_labels["pill_igloo"]["val"], text=f"{local_ms:.1f} ms", text_color=STATUS_RED)
                self._safe_configure(self.telemetry_labels["pill_igloo"]["sub"], text="SPIKING! (Wi-Fi/LAN Delay)", text_color=STATUS_RED)
            else:
                self._safe_configure(self.telemetry_labels["pill_igloo"]["val"], text=f"{local_ms:.1f} ms", text_color=ACCENT_GLACIER_BLUE)
                self._safe_configure(self.telemetry_labels["pill_igloo"]["sub"], text="Solid (Wi-Fi/LAN)", text_color=("#5B6472", "#9BA3AF"))

    def _check_auto_stop_conditions(self) -> None:
        """Evaluates custom timer countdown and auto-stop condition."""
        if not self._is_scanning:
            return

        elapsed = time.time() - self._scan_start_time
        if self._active_scan_duration_sec is not None:
            remaining = max(0, int(round(self._active_scan_duration_sec - elapsed)))
            self._safe_configure(self.btn_start, text=f"⏹ STOP SCAN ({remaining}s left)")
            if elapsed >= self._active_scan_duration_sec:
                self.stop_scan(reason=f"Custom timer ({int(self._active_scan_duration_sec)}s) completed.")
        else:
            self._safe_configure(self.btn_start, text="⏹ STOP SCAN (Continuous)")

    # ========================================================================
    # 10. FULL BOOT-STATE RESET LOGIC
    # ========================================================================
    def reset_to_boot_state(self) -> None:
        """
        Full Boot-State Reset: Returns the entire application to its fresh boot state.
        Halts any active scan, resets SessionAnalyzer, flushes queues, clears graph,
        restores Verdict Banner, Metric Cards, Data Used badge, Server & Genre presets,
        and Timer inputs.
        """
        # 1. Stop active scan if running
        if self._is_scanning:
            self.stop_scan()

        # 2. Reset analyzer and clear queue
        self._session_analyzer.reset()
        while not self._sample_queue.empty():
            try:
                self._sample_queue.get_nowait()
            except queue.Empty:
                break

        # 3. Reset Data Used badge
        self._safe_configure(self.wan_badge, text="Data Used: 0.0 KB")

        # 4. Reset Verdict Banner
        self._safe_configure(
            self.lbl_verdict_title,
            text="CLICK SCAN NOOT — PICK A SERVER NOOT",
            text_color=STATUS_GREEN
        )
        self._safe_configure(self.verdict_card, border_color=("#D5D9E0", "#262B33"))
        self._safe_configure(
            self.lbl_root_cause,
            text="Select your target datacenter and genre profile above, then click Start Noot Scan."
        )
        self._safe_configure(
            self.lbl_protocol_badge,
            text="[Protocol: Standby]",
            text_color=("#5B6472", "#9BA3AF")
        )

        # 5. Reset 5 Metric Cards
        self._safe_configure(self.telemetry_labels["pill_avg"]["val"], text="0.0 ms", text_color=TEXT_SNOW)
        self._safe_configure(self.telemetry_labels["pill_avg"]["sub"], text="Live: -- ms", text_color=("#5B6472", "#9BA3AF"))

        self._safe_configure(self.telemetry_labels["pill_p99"]["val"], text="0.0 ms", text_color=TEXT_SNOW)
        self._safe_configure(self.telemetry_labels["pill_p99"]["sub"], text="Worst 1% spike", text_color=("#5B6472", "#9BA3AF"))

        self._safe_configure(self.telemetry_labels["pill_jitter"]["val"], text="0.0 ms", text_color=TEXT_SNOW)
        self._safe_configure(self.telemetry_labels["pill_jitter"]["sub"], text="Sub-frame variance", text_color=("#5B6472", "#9BA3AF"))

        self._safe_configure(self.telemetry_labels["pill_loss"]["val"], text="0.0 %", text_color=STATUS_GREEN)
        self._safe_configure(self.telemetry_labels["pill_loss"]["sub"], text="0 dropped packets", text_color=("#5B6472", "#9BA3AF"))

        self._safe_configure(self.telemetry_labels["pill_igloo"]["val"], text="0.0 ms", text_color=ACCENT_GLACIER_BLUE)
        self._safe_configure(self.telemetry_labels["pill_igloo"]["sub"], text="Solid (Wi-Fi/LAN)", text_color=("#5B6472", "#9BA3AF"))

        # 6. Reset VerticalPingGraph
        self.graph.reset_to_boot()

        # 7. Reset Server & Genre selections
        if self._server_display_list:
            self.server_combo.set(self._server_display_list[0])
            self._user_config["selected_server_name"] = DEFAULT_SERVERS[0]["name"]

        default_genre = self.genre_names[1] if len(self.genre_names) > 1 else self.genre_names[0]
        self.genre_combo.set(default_genre)
        self._user_config["selected_genre"] = default_genre
        self.custom_sliders_frame.pack_forget()

        # Reset Custom Sliders
        self.slider_payload.set(64)
        self.slider_rate.set(5)
        self.lbl_slider_payload.configure(text="Payload Size: 64 Bytes")
        self.lbl_slider_rate.configure(text="Ping Rate: 5 Hz (Ticks/sec)")
        self._user_config["custom_payload_bytes"] = 64
        self._user_config["custom_pings_per_sec"] = 5

        # 8. Reset Timer Control Group
        self.timer_entry.configure(state="normal")
        self.timer_entry.delete(0, "end")
        self.timer_entry.insert(0, "60")
        self.timer_unit_menu.set("sec")
        self._active_scan_duration_sec = 60.0

        save_user_config(self._user_config)
        self._update_preflight_estimate()

    # ========================================================================
    # 11. GRACEFUL SHUTDOWN
    # ========================================================================
    def _on_window_close(self) -> None:
        """Terminates active scanner and background threads before exit."""
        if self._poll_timer_id:
            try:
                self.after_cancel(self._poll_timer_id)
            except Exception:
                pass

        if self._is_scanning and self._scanner:
            self._scanner.stop()
            self._scanner = None

        self.destroy()
