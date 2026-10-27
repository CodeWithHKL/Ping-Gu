"""
Ping Gu - Virtualized Interactive Vertical Bar-List Graph Widget
High-performance native tk.Canvas implementation with pre-allocated row item pooling,
zero-flicker in-place updates, strict hover debouncing, and Arctic Tuxedo styling.
"""

from collections import deque
from datetime import datetime
import math
import tkinter as tk
from typing import Any, Deque, Dict, List, Optional

import customtkinter as ctk

from presets import (
    ThemedCanvas,
    pick_color,
    FONT_BODY,
    FONT_HEAD,
    ACCENT_BEAK_ORANGE,
    ACCENT_GLACIER_BLUE,
    BG_TUXEDO_DARK,
    CARD_DARK,
    GRAPH_MAX_CAP_MS,
    STATUS_GREEN,
    STATUS_OVERCAP_PURPLE,
    STATUS_RED,
    STATUS_YELLOW,
    TEXT_SNOW,
)
from scanner import PingSample


# ============================================================================
# CONSTANTS & METRICS
# ============================================================================
ROW_HEIGHT = 28               # Pixel height of each packet row in the canvas
COL_SEQ_TIME_WIDTH = 130      # Width of sequence # + timestamp column
COL_TAG_RTT_WIDTH_SINGLE = 175# Width of latency value + diagnostic badge column (single-track)
COL_TAG_RTT_WIDTH_DUAL = 245  # Width of latency value + diagnostic badge column (dual-track igloo)
COL_TAG_RTT_WIDTH = COL_TAG_RTT_WIDTH_SINGLE  # Backwards compatibility default
LOCAL_IGLOO_CEILING_MS = 50.0 # 50ms local ceiling for readable Wi-Fi/LAN bar scaling
CANVAS_BG = ("#ECEEF2", "#0A0C0F")         # Deep abyss dark slate canvas background
TRACK_BG = ("#FFFFFF", "#15181D")          # Latency bar slot container background
TRACK_BORDER = ("#D5D9E0", "#262B33")      # Latency bar slot border
HOVER_BG = ("#FFFFFF", "#15181D")          # Background tint when row is hovered
HOVER_BORDER = ("#B8BFC9", "#3A414C")      # Highlight outline for hovered row
SELECT_BORDER = ACCENT_GLACIER_BLUE  # Selection accent border for clicked row
MAX_VISIBLE_ROWS = 45         # Pre-allocated row item pool size


# ============================================================================
# INTERACTIVE FLOATING TOOLTIP HELPER
# ============================================================================
class InfoTooltip:
    """
    Lightweight, floating tooltip attached to an interactive '?' badge widget.
    Positions the tooltip smartly so it never clips beyond screen or window boundaries.
    """
    def __init__(self, badge_widget: Any, text: str, title: str = ""):
        self.widget = badge_widget
        self.text = text
        self.title = title
        self._tip_window: Optional[tk.Toplevel] = None

        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)
        self.widget.bind("<Button-1>", self.toggle_tip)

    def show_tip(self, event=None) -> None:
        if self._tip_window or not self.text:
            return

        try:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() + 6
            y = self.widget.winfo_rooty() - 4
        except Exception:
            return

        self._tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.wm_attributes("-topmost", True)
        except Exception:
            pass
        tw.configure(bg=pick_color(("#F3F4F6", "#0D0F12")))

        # Container frame for styling
        outer = tk.Frame(tw, bg=pick_color(("#2F6FB5", "#6CA0DC")), bd=1)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=pick_color(("#F3F4F6", "#0D0F12")), padx=10, pady=8)
        inner.pack(fill="both", expand=True)

        if self.title:
            lbl_title = tk.Label(
                inner,
                text=self.title,
                font=(FONT_BODY, 11, "bold"),
                fg=pick_color(("#2F6FB5", "#6CA0DC")),
                bg=pick_color(("#F3F4F6", "#0D0F12")),
                anchor="w",
                justify="left"
            )
            lbl_title.pack(fill="x", pady=(0, 4))

        lbl_body = tk.Label(
            inner,
            text=self.text,
            font=(FONT_BODY, 10),
            fg=pick_color(("#14171C", "#E8EAED")),
            bg=pick_color(("#F3F4F6", "#0D0F12")),
            wraplength=270,
            justify="left",
            anchor="w"
        )
        lbl_body.pack(fill="both", expand=True)

        tw.update_idletasks()
        tw_w = tw.winfo_reqwidth()
        tw_h = tw.winfo_reqheight()

        # Clamp within screen bounds
        try:
            screen_w = self.widget.winfo_screenwidth()
            screen_h = self.widget.winfo_screenheight()
        except Exception:
            screen_w, screen_h = 1920, 1080

        if x + tw_w > screen_w - 12:
            x = self.widget.winfo_rootx() - tw_w - 6
        if y + tw_h > screen_h - 12:
            y = screen_h - tw_h - 12
        if x < 10:
            x = 10
        if y < 10:
            y = 10

        tw.wm_geometry(f"+{x}+{y}")

    def hide_tip(self, event=None) -> None:
        if self._tip_window:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None

    def toggle_tip(self, event=None) -> None:
        if self._tip_window:
            self.hide_tip()
        else:
            self.show_tip()


def create_help_badge(parent: Any, text: str, title: str = "") -> ctk.CTkButton:
    """Creates a compact 20x20 circular '?' help badge with interactive tooltip."""
    btn = ctk.CTkButton(
        parent,
        text="?",
        width=20,
        height=20,
        corner_radius=4,
        font=ctk.CTkFont(family=FONT_HEAD, size=13, weight="bold"),
        fg_color=("#D5D9E0", "#262B33"),
        text_color=("#5B6472", "#9BA3AF"),
        hover_color=ACCENT_GLACIER_BLUE,
        cursor="hand2"
    )
    btn._tooltip = InfoTooltip(btn, text=text, title=title)
    return btn


class VerticalPingGraph(ctk.CTkFrame):
    """
    Zero-flicker virtualized vertical bar-list graph.
    Renders ONLY visible rows using a pre-allocated item pool on a single native
    tk.Canvas. Replaces canvas.delete('all') with in-place item reconfiguration
    to eliminate GDI blinking completely on Windows.
    """

    def __init__(
        self,
        master: tk.Widget,
        maxlen: int = 5000,
        show_local_igloo: bool = False,
        **kwargs
    ):
        super().__init__(master, fg_color=BG_TUXEDO_DARK, **kwargs)

        self.maxlen = maxlen
        self._show_local_igloo = show_local_igloo

        # Sample storage (rolling window of up to maxlen packets)
        self._samples: Deque[PingSample] = deque(maxlen=maxlen)

        # Frozen snapshot when user is hovering / inspecting
        self._frozen_samples: Optional[List[PingSample]] = None
        self._is_hover_paused = False
        self._manually_scrolled = False

        # Virtualized scroll state (0 = newest row at top)
        self._scroll_top_row = 0

        # Hover & selection tracking
        self._hovered_row_idx: Optional[int] = None
        self._selected_sample: Optional[PingSample] = None
        self._last_status_badge_state = None

        # Redraw throttle (Dirty Flag Pattern)
        self._dirty = False
        self._redraw_timer_id: Optional[str] = None

        # Build UI Structure
        self._create_header_bar()
        self._create_column_headers()
        self._create_canvas_and_scrollbar()
        self._create_forensic_inspector()

        # Pre-allocate canvas item pool for zero-flicker in-place rendering
        self._create_item_pool()

        # Bindings for resize & controls
        self._plot_canvas.bind("<Configure>", self._on_canvas_configure)
        self._plot_canvas.bind("<Motion>", self._on_canvas_motion)
        self._plot_canvas.bind("<Button-1>", self._on_canvas_click)
        self._plot_canvas.bind("<Enter>", self._on_canvas_enter)
        self._plot_canvas.bind("<Leave>", self._on_canvas_leave)
        self._plot_canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)

    # ========================================================================
    # 1. UI COMPONENT CREATION
    # ========================================================================
    def _create_header_bar(self) -> None:
        """Top bar displaying live status, stream mode, and quick toggles."""
        self._header_frame = ctk.CTkFrame(
            self,
            fg_color=CARD_DARK,
            corner_radius=4,
            height=38
        )
        self._header_frame.pack(fill="x", padx=6, pady=(6, 4))
        self._header_frame.pack_propagate(False)

        # Left: Stream Title & Status
        self._title_label = ctk.CTkLabel(
            self._header_frame,
            text="Real-Time Latency Stream",
            font=ctk.CTkFont(family=FONT_HEAD, size=15, weight="bold"),
            text_color=TEXT_SNOW
        )
        self._title_label.pack(side="left", padx=(12, 4))

        self._help_badge = create_help_badge(
            self._header_frame,
            text="Bars cap visually at 250ms so huge spikes don't squash normal bars. Hover to pause auto-scroll, and click any bar to see its forensic diagnosis at the bottom.",
            title="Real-Time Latency Stream"
        )
        self._help_badge.pack(side="left", padx=(0, 8))

        # Status Badge (Live vs Paused vs Scrolled)
        self._status_badge = ctk.CTkLabel(
            self._header_frame,
            text="LIVE (Auto-follow)",
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            text_color=STATUS_GREEN
        )
        self._status_badge.pack(side="left", padx=4)

        # Right: Action controls
        self._clear_btn = ctk.CTkButton(
            self._header_frame,
            text="Clear Bars",
            width=75,
            height=24,
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            fg_color=("#D5D9E0", "#262B33"),
            text_color=TEXT_SNOW,
            hover_color=("#B8BFC9", "#3A414C"),
            command=self.clear_samples
        )
        self._clear_btn.pack(side="right", padx=(4, 10))

        self._resume_btn = ctk.CTkButton(
            self._header_frame,
            text="▶ Resume Live",
            width=90,
            height=24,
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            fg_color=ACCENT_BEAK_ORANGE,
            text_color="#FFFFFF",
            hover_color=("#B53B0A", "#C2410C"),
            command=self.resume_live
        )

        # Igloo Overlay Switch (Show Local Ping)
        self._igloo_switch = ctk.CTkSwitch(
            self._header_frame,
            text="Show Local Ping",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=TEXT_SNOW,
            progress_color=ACCENT_GLACIER_BLUE,
            command=self._on_igloo_switch_toggled
        )
        if self._show_local_igloo:
            self._igloo_switch.select()
        else:
            self._igloo_switch.deselect()
        self._igloo_switch.pack(side="right", padx=(8, 12))

    def _create_column_headers(self) -> None:
        """Fixed column labels above the virtualized canvas."""
        self._col_header_frame = ctk.CTkFrame(
            self,
            fg_color=BG_TUXEDO_DARK,
            height=22
        )
        self._col_header_frame.pack(fill="x", padx=8, pady=(2, 2))
        self._col_header_frame.pack_propagate(False)

        # Left label: Packet & Timestamp
        self._lbl_col_seq = ctk.CTkLabel(
            self._col_header_frame,
            text="PKT #   TIME",
            font=ctk.CTkFont(family=FONT_HEAD, size=12, weight="bold"),
            text_color=("#7A828F", "#6B7280"),
            width=COL_SEQ_TIME_WIDTH,
            anchor="w"
        )
        self._lbl_col_seq.pack(side="left", padx=(6, 0))

        # Right label: Value & Diagnosis
        self._lbl_col_rtt = ctk.CTkLabel(
            self._col_header_frame,
            text="LATENCY  /  DIAGNOSIS",
            font=ctk.CTkFont(family=FONT_HEAD, size=12, weight="bold"),
            text_color=("#7A828F", "#6B7280"),
            width=COL_TAG_RTT_WIDTH_SINGLE,
            anchor="e"
        )
        self._lbl_col_rtt.pack(side="right", padx=(0, 24))

        # Center label: Scale
        self._lbl_col_bar = ctk.CTkLabel(
            self._col_header_frame,
            text="LATENCY SPECTRUM (0 ──────── 250ms CAP)",
            font=ctk.CTkFont(family=FONT_HEAD, size=12, weight="bold"),
            text_color=("#7A828F", "#6B7280"),
            anchor="center"
        )
        self._lbl_col_bar.pack(side="left", fill="x", expand=True)

        self._update_column_headers()

    def _update_column_headers(self) -> None:
        """Updates column header labels to reflect single vs dual-track igloo mode."""
        if not hasattr(self, "_lbl_col_bar") or not hasattr(self, "_lbl_col_rtt"):
            return
        if self._show_local_igloo:
            self._lbl_col_bar.configure(text="SPECTRUM (TOP: SERVER 250ms | BOTTOM: IGLOO 50ms)")
            self._lbl_col_rtt.configure(text="SRV / IGLOO / DIAG", width=COL_TAG_RTT_WIDTH_DUAL)
        else:
            self._lbl_col_bar.configure(text="LATENCY SPECTRUM (0 ──────── 250ms CAP)")
            self._lbl_col_rtt.configure(text="LATENCY  /  DIAGNOSIS", width=COL_TAG_RTT_WIDTH_SINGLE)

    def _create_canvas_and_scrollbar(self) -> None:
        """Container with native tk.Canvas and modern CTkScrollbar."""
        self._center_container = ctk.CTkFrame(
            self,
            fg_color=CANVAS_BG,
            corner_radius=4,
            border_width=1,
            border_color=("#FFFFFF", "#15181D")
        )
        self._center_container.pack(fill="both", expand=True, padx=6, pady=2)

        # Native tk.Canvas with zero border to maintain Windows double buffering
        self._plot_canvas = ThemedCanvas(
            self._center_container,
            bg=CANVAS_BG,
            highlightthickness=0,
            bd=0
        )
        self._plot_canvas.pack(side="left", fill="both", expand=True)

        # CustomTkinter Vertical Scrollbar
        self._scrollbar = ctk.CTkScrollbar(
            self._center_container,
            orientation="vertical",
            command=self._on_scrollbar_move,
            fg_color=("#F3F4F6", "#0D0F12"),
            button_color=("#D5D9E0", "#262B33"),
            button_hover_color=("#B8BFC9", "#3A414C")
        )
        self._scrollbar.pack(side="right", fill="y", padx=(0, 2), pady=2)

    def _create_forensic_inspector(self) -> None:
        """Bottom docked forensic analysis card for clicked packet inspection."""
        self._inspector_card = ctk.CTkFrame(
            self,
            fg_color=CARD_DARK,
            corner_radius=4,
            border_width=1,
            border_color=("#D5D9E0", "#262B33")
        )
        self._inspector_card.pack(fill="x", padx=6, pady=(4, 6))

        # Default placeholder when no sample is clicked
        self._inspector_placeholder = ctk.CTkLabel(
            self._inspector_card,
            text="Click any packet bar above to inspect forensic hop latency, protocol framing & root cause analysis.",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=("#5B6472", "#9BA3AF")
        )
        self._inspector_placeholder.pack(fill="x", padx=12, pady=10)

        # Detailed container (hidden until selection)
        self._inspector_content = ctk.CTkFrame(self._inspector_card, fg_color="transparent")

        # Top row: Packet #, Time, Protocol, Tag
        self._insp_row1 = ctk.CTkFrame(self._inspector_content, fg_color="transparent")
        self._insp_row1.pack(fill="x", padx=8, pady=(6, 2))

        self._insp_seq_badge = ctk.CTkLabel(
            self._insp_row1,
            text="PKT #000",
            font=ctk.CTkFont(family=FONT_HEAD, size=14, weight="bold"),
            text_color=ACCENT_BEAK_ORANGE
        )
        self._insp_seq_badge.pack(side="left", padx=(0, 10))

        self._insp_time_lbl = ctk.CTkLabel(
            self._insp_row1,
            text="Time: --:--:--.---",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=TEXT_SNOW
        )
        self._insp_time_lbl.pack(side="left", padx=(0, 12))

        self._insp_proto_lbl = ctk.CTkLabel(
            self._insp_row1,
            text="Protocol: ICMP (32 B)",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=ACCENT_GLACIER_BLUE
        )
        self._insp_proto_lbl.pack(side="left", padx=(0, 12))

        self._insp_tag_badge = ctk.CTkLabel(
            self._insp_row1,
            text="[NORMAL]",
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            text_color=STATUS_GREEN
        )
        self._insp_tag_badge.pack(side="left")

        self._insp_close_btn = ctk.CTkButton(
            self._insp_row1,
            text="Deselect",
            width=70,
            height=20,
            font=ctk.CTkFont(family=FONT_BODY, size=11),
            fg_color=("#D5D9E0", "#262B33"),
            text_color=TEXT_SNOW,
            hover_color=("#B8BFC9", "#3A414C"),
            command=self._clear_selection
        )
        self._insp_close_btn.pack(side="right")

        # Middle row: Hop Metrics Chips
        self._insp_row2 = ctk.CTkFrame(self._inspector_content, fg_color="transparent")
        self._insp_row2.pack(fill="x", padx=8, pady=2)

        self._chip_server = ctk.CTkLabel(
            self._insp_row2,
            text="Server RTT: -- ms",
            font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"),
            text_color=TEXT_SNOW
        )
        self._chip_server.pack(side="left", padx=(0, 16))

        self._chip_local = ctk.CTkLabel(
            self._insp_row2,
            text="Local Igloo (Router): -- ms",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=ACCENT_GLACIER_BLUE
        )
        self._chip_local.pack(side="left", padx=(0, 16))

        self._chip_wan = ctk.CTkLabel(
            self._insp_row2,
            text="WAN Data: -- B",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=("#5B6472", "#9BA3AF")
        )
        self._chip_wan.pack(side="left")

        # Bottom row: Forensic Detail Diagnosis
        self._insp_detail_box = ctk.CTkFrame(
            self._inspector_content,
            fg_color=("#F3F4F6", "#0D0F12"),
            corner_radius=3,
            border_width=1,
            border_color=("#D5D9E0", "#262B33")
        )
        self._insp_detail_box.pack(fill="x", padx=8, pady=(4, 6))

        self._insp_detail_lbl = ctk.CTkLabel(
            self._insp_detail_box,
            text="Forensic Analysis: Smooth sliding! Normal latency.",
            font=ctk.CTkFont(family=FONT_BODY, size=12),
            text_color=TEXT_SNOW,
            anchor="w",
            justify="left"
        )
        self._insp_detail_lbl.pack(fill="x", padx=10, pady=6)

    # ========================================================================
    # 2. PRE-ALLOCATED CANVAS ITEM POOL (ZERO-FLICKER)
    # ========================================================================
    def _create_item_pool(self) -> None:
        """
        Pre-creates reusable canvas items for MAX_VISIBLE_ROWS.
        Eliminates canvas.delete('all') during live updates and hover.
        """
        self._row_slots: List[Dict[str, int]] = []

        for _ in range(MAX_VISIBLE_ROWS):
            hover_box = self._plot_canvas.create_rectangle(0, 0, 0, 0, fill="", outline="", state="hidden")
            sep = self._plot_canvas.create_line(0, 0, 0, 0, fill=("#E9EBEF", "#101318"), width=1, state="hidden")
            seq = self._plot_canvas.create_text(0, 0, text="", fill=("#5B6472", "#9BA3AF"), font=(FONT_HEAD, 11, "bold"), anchor="w", state="hidden")
            time_txt = self._plot_canvas.create_text(0, 0, text="", fill=("#7A828F", "#6B7280"), font=(FONT_HEAD, 11), anchor="w", state="hidden")
            track = self._plot_canvas.create_rectangle(0, 0, 0, 0, fill=TRACK_BG, outline=TRACK_BORDER, width=1, state="hidden")
            srv_bar = self._plot_canvas.create_rectangle(0, 0, 0, 0, fill="", outline="", state="hidden")
            cap_line = self._plot_canvas.create_line(0, 0, 0, 0, fill=("#D6372E", "#E5534B"), width=3, state="hidden")
            igloo_bar = self._plot_canvas.create_rectangle(0, 0, 0, 0, fill=ACCENT_GLACIER_BLUE, outline="", state="hidden")
            ibadge_box = self._plot_canvas.create_rectangle(0, 0, 0, 0, fill=("#D6E6F7", "#1F4E79"), outline=("#2F6FB5", "#6CA0DC"), width=1, state="hidden")
            ibadge_txt = self._plot_canvas.create_text(0, 0, text="IGLOO SPIKE", fill=("#12304F", "#EEF3F9"), font=(FONT_BODY, 8, "bold"), anchor="center", state="hidden")
            lost_txt = self._plot_canvas.create_text(0, 0, text="LOST / TIMEOUT", fill=("#9B1C1C", "#FCA5A5"), font=(FONT_BODY, 8, "bold"), anchor="center", state="hidden")
            rtt_txt = self._plot_canvas.create_text(0, 0, text="", fill=TEXT_SNOW, font=(FONT_HEAD, 11, "bold"), anchor="w", state="hidden")
            dbadge_box = self._plot_canvas.create_rectangle(0, 0, 0, 0, fill="", outline="", state="hidden")
            dbadge_txt = self._plot_canvas.create_text(0, 0, text="", fill="", font=(FONT_BODY, 8, "bold"), anchor="center", state="hidden")

            self._row_slots.append({
                "hover_box": hover_box,
                "separator": sep,
                "seq_text": seq,
                "time_text": time_txt,
                "track_bg": track,
                "server_bar": srv_bar,
                "overcap_line": cap_line,
                "igloo_bar": igloo_bar,
                "igloo_badge_box": ibadge_box,
                "igloo_badge_text": ibadge_txt,
                "lost_text": lost_txt,
                "rtt_text": rtt_txt,
                "diag_badge_box": dbadge_box,
                "diag_badge_text": dbadge_txt,
            })

        # Single pre-created empty state text item
        self._empty_text_id = self._plot_canvas.create_text(
            0, 0,
            text="Waiting for network pings... Start scanning to view live latency stream.",
            fill=("#B8BFC9", "#3A414C"),
            font=(FONT_BODY, 11, "italic"),
            anchor="center",
            state="normal"
        )

    # ========================================================================
    # 3. PUBLIC CONTROL METHODS
    # ========================================================================
    def add_sample(self, sample: PingSample) -> None:
        """
        Appends a new PingSample to the buffer.
        Schedules a throttled canvas redraw via dirty flag pattern.
        """
        self._samples.append(sample)

        # If not paused and not manually scrolled away, auto-follow newest
        if not self._is_hover_paused and not self._manually_scrolled:
            self._scroll_top_row = 0

        self._request_redraw()

    def clear_samples(self) -> None:
        """Empties the sample buffer and hides visible row slots."""
        self._samples.clear()
        self._frozen_samples = None
        self._scroll_top_row = 0
        self._hovered_row_idx = None
        self._clear_selection()
        self._request_redraw()

    def reset_to_boot(self) -> None:
        """Completely restores graph, inspector, and toggles back to fresh boot state."""
        self._samples.clear()
        self._frozen_samples = None
        self._scroll_top_row = 0
        self._hovered_row_idx = None
        self._manually_scrolled = False
        self._is_hover_paused = False
        self._clear_selection()
        self.set_show_local_igloo(False)
        self._update_status_badge()
        self._render_canvas()

    @property
    def show_local_igloo(self) -> bool:
        """Property getter for whether local igloo ping overlay is shown."""
        return self._show_local_igloo

    @show_local_igloo.setter
    def show_local_igloo(self, show: bool) -> None:
        """Property setter for local igloo ping overlay."""
        self.set_show_local_igloo(show)

    def set_show_local_igloo(self, show: bool) -> None:
        """Toggles rendering of the inner local router ping sub-bar."""
        self._show_local_igloo = bool(show)
        if hasattr(self, "_igloo_switch"):
            if self._show_local_igloo:
                self._igloo_switch.select()
            else:
                self._igloo_switch.deselect()
        self._update_column_headers()
        self._render_canvas()

    def resume_live(self) -> None:
        """Resumes live auto-follow and resets manual scroll offset."""
        self._manually_scrolled = False
        self._is_hover_paused = False
        self._frozen_samples = None
        self._scroll_top_row = 0
        self._update_status_badge()
        self._request_redraw()

    def get_selected_sample(self) -> Optional[PingSample]:
        """Returns currently inspected PingSample, or None."""
        return self._selected_sample

    @property
    def samples_count(self) -> int:
        """Returns total number of buffered samples."""
        return len(self._samples)

    # ========================================================================
    # 4. THROTTLED IN-PLACE CANVAS RENDERING
    # ========================================================================
    def _request_redraw(self) -> None:
        """Flags canvas as dirty and schedules a redraw within 20ms (~50 FPS)."""
        self._dirty = True
        if self._redraw_timer_id is None:
            self._redraw_timer_id = self.after(20, self._process_dirty_redraw)

    def _process_dirty_redraw(self) -> None:
        """Timer callback processing dirty redraws without canvas recreation."""
        self._redraw_timer_id = None
        if self._dirty:
            self._dirty = False
            self._render_canvas()

    def _get_active_samples(self) -> List[PingSample]:
        """
        Returns active sample list.
        Uses frozen snapshot if user is hovering to avoid shifting rows under mouse.
        """
        if self._is_hover_paused and self._frozen_samples is not None:
            return self._frozen_samples
        return list(self._samples)

    def apply_theme(self) -> None:
        """Re-colours the canvas after a light/dark switch."""
        self._plot_canvas.apply_theme()
        self._render_canvas()

    def _render_canvas(self) -> None:
        """
        In-place canvas updater using pre-allocated item slots.
        NEVER calls canvas.delete('all'), completely eliminating GDI blink.
        """
        canvas = self._plot_canvas
        active_samples = self._get_active_samples()
        total_samples = len(active_samples)

        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()

        if canvas_width <= 10:
            canvas_width = 800
        if canvas_height <= 10:
            canvas_height = 400

        if total_samples == 0:
            # Position and show empty text
            canvas.coords(self._empty_text_id, canvas_width // 2, canvas_height // 2)
            canvas.itemconfigure(self._empty_text_id, state="normal")
            for slot in self._row_slots:
                for item_id in slot.values():
                    canvas.itemconfigure(item_id, state="hidden")
            self._scrollbar.set(0.0, 1.0)
            return

        # Hide empty state text
        canvas.itemconfigure(self._empty_text_id, state="hidden")

        # Virtualization calculations
        visible_rows_count = min(len(self._row_slots), (canvas_height // ROW_HEIGHT) + 2)
        max_start_row = max(0, total_samples - (canvas_height // ROW_HEIGHT))

        self._scroll_top_row = max(0, min(max_start_row, self._scroll_top_row))
        start_row = self._scroll_top_row
        end_row = min(total_samples, start_row + visible_rows_count)

        # Update scrollbar position
        if total_samples <= (canvas_height // ROW_HEIGHT):
            self._scrollbar.set(0.0, 1.0)
        else:
            first = start_row / total_samples
            last = min(1.0, end_row / total_samples)
            self._scrollbar.set(first, last)

        # Geometry calculations
        col1_w = COL_SEQ_TIME_WIDTH
        col3_w = COL_TAG_RTT_WIDTH_DUAL if self._show_local_igloo else COL_TAG_RTT_WIDTH_SINGLE
        bar_x1 = col1_w + 10
        bar_x2 = max(bar_x1 + 60, canvas_width - col3_w - 12)
        bar_track_width = bar_x2 - bar_x1
        active_slots_count = end_row - start_row

        # Iterate through pre-allocated slots
        for slot_idx in range(len(self._row_slots)):
            slot = self._row_slots[slot_idx]

            if slot_idx < active_slots_count:
                row_idx = start_row + slot_idx
                sample_idx = total_samples - 1 - row_idx
                sample = active_samples[sample_idx]

                y_top = slot_idx * ROW_HEIGHT
                y_bottom = y_top + ROW_HEIGHT

                is_hovered = (self._hovered_row_idx == row_idx)
                is_selected = (
                    self._selected_sample is not None
                    and self._selected_sample.seq_id == sample.seq_id
                )

                # 1. Hover & Selection highlight
                if is_selected:
                    canvas.coords(slot["hover_box"], 2, y_top + 1, canvas_width - 2, y_bottom - 1)
                    canvas.itemconfigure(slot["hover_box"], fill=("#FFFFFF", "#15181D"), outline=SELECT_BORDER, width=1.5, state="normal")
                    canvas.itemconfigure(slot["separator"], state="hidden")
                elif is_hovered:
                    canvas.coords(slot["hover_box"], 2, y_top + 1, canvas_width - 2, y_bottom - 1)
                    canvas.itemconfigure(slot["hover_box"], fill=HOVER_BG, outline=HOVER_BORDER, width=1, state="normal")
                    canvas.itemconfigure(slot["separator"], state="hidden")
                else:
                    canvas.itemconfigure(slot["hover_box"], state="hidden")
                    canvas.coords(slot["separator"], 4, y_bottom, canvas_width - 4, y_bottom)
                    canvas.itemconfigure(slot["separator"], state="normal")

                # 2. Left Column: Sequence # & Time
                time_str = datetime.fromtimestamp(sample.timestamp).strftime("%H:%M:%S.%f")[:-5]
                canvas.coords(slot["seq_text"], 8, y_top + (ROW_HEIGHT // 2))
                canvas.itemconfigure(
                    slot["seq_text"],
                    text=f"#{sample.seq_id:03d}",
                    fill=TEXT_SNOW if is_hovered else ("#5B6472", "#9BA3AF"),
                    state="normal"
                )

                canvas.coords(slot["time_text"], 55, y_top + (ROW_HEIGHT // 2))
                canvas.itemconfigure(slot["time_text"], text=time_str, state="normal")

                # 3. Center Column: Horizontal Latency Bar
                track_y1 = y_top + 5
                track_y2 = y_bottom - 5
                canvas.coords(slot["track_bg"], bar_x1, track_y1, bar_x2, track_y2)
                canvas.itemconfigure(slot["track_bg"], state="normal")

                if not self._show_local_igloo:
                    # ========================================================
                    # SINGLE TRACK MODE (Full 16px Height for Server RTT)
                    # ========================================================
                    srv_top = track_y1 + 1
                    srv_bottom = track_y2 - 1
                    canvas.itemconfigure(slot["igloo_bar"], state="hidden")

                    if sample.is_timeout or sample.server_rtt_ms is None:
                        canvas.coords(slot["server_bar"], bar_x1 + 1, srv_top, bar_x2 - 1, srv_bottom)
                        canvas.itemconfigure(slot["server_bar"], fill=("#FBE0DE", "#7F1D1D"), outline=("#D6372E", "#E5534B"), width=1, state="normal")
                        canvas.coords(slot["lost_text"], bar_x1 + (bar_track_width // 2), y_top + (ROW_HEIGHT // 2))
                        canvas.itemconfigure(slot["lost_text"], state="normal")
                        canvas.itemconfigure(slot["overcap_line"], state="hidden")
                        canvas.itemconfigure(slot["igloo_badge_box"], state="hidden")
                        canvas.itemconfigure(slot["igloo_badge_text"], state="hidden")
                        val_text = "TIMEOUT"
                        val_color = STATUS_RED
                    else:
                        canvas.itemconfigure(slot["lost_text"], state="hidden")
                        rtt = sample.server_rtt_ms
                        ratio = min(rtt / GRAPH_MAX_CAP_MS, 1.0)
                        bar_fill_w = max(4.0, bar_track_width * ratio)
                        fill_x2 = min(bar_x2 - 1, bar_x1 + bar_fill_w)

                        if rtt > GRAPH_MAX_CAP_MS:
                            fill_color = STATUS_OVERCAP_PURPLE
                            val_text = f"{rtt:.1f}ms [CAP]"
                            val_color = STATUS_OVERCAP_PURPLE
                        elif rtt > 130.0:
                            fill_color = STATUS_RED
                            val_text = f"{rtt:.1f} ms"
                            val_color = STATUS_RED
                        elif rtt > 60.0:
                            fill_color = STATUS_YELLOW
                            val_text = f"{rtt:.1f} ms"
                            val_color = STATUS_YELLOW
                        else:
                            fill_color = STATUS_GREEN
                            val_text = f"{rtt:.1f} ms"
                            val_color = TEXT_SNOW

                        canvas.coords(slot["server_bar"], bar_x1 + 1, srv_top, fill_x2, srv_bottom)
                        canvas.itemconfigure(slot["server_bar"], fill=fill_color, outline="", state="normal")

                        if rtt > GRAPH_MAX_CAP_MS:
                            canvas.coords(slot["overcap_line"], bar_x2 - 1, srv_top, bar_x2 - 1, srv_bottom)
                            canvas.itemconfigure(slot["overcap_line"], state="normal")
                        else:
                            canvas.itemconfigure(slot["overcap_line"], state="hidden")

                        # Alert overlay on track if local router spiked while igloo toggle is off
                        if sample.diagnosis_tag == "LOCAL_IGLOO_SPIKE":
                            bx = bar_x1 + 6
                            by = track_y1 + 2
                            canvas.coords(slot["igloo_badge_box"], bx, by, bx + 84, track_y2 - 2)
                            canvas.itemconfigure(slot["igloo_badge_box"], state="normal")
                            canvas.coords(slot["igloo_badge_text"], bx + 42, track_y1 + ((track_y2 - track_y1) // 2))
                            canvas.itemconfigure(slot["igloo_badge_text"], state="normal")
                        else:
                            canvas.itemconfigure(slot["igloo_badge_box"], state="hidden")
                            canvas.itemconfigure(slot["igloo_badge_text"], state="hidden")

                else:
                    # ========================================================
                    # DUAL TRACK MODE (Top: Server 9px | Bottom: Igloo 6px)
                    # ========================================================
                    canvas.itemconfigure(slot["igloo_badge_box"], state="hidden")
                    canvas.itemconfigure(slot["igloo_badge_text"], state="hidden")

                    # Top Half: Server RTT
                    srv_top = track_y1 + 1
                    srv_bottom = srv_top + 9

                    if sample.is_timeout or sample.server_rtt_ms is None:
                        canvas.coords(slot["server_bar"], bar_x1 + 1, srv_top, bar_x2 - 1, srv_bottom)
                        canvas.itemconfigure(slot["server_bar"], fill=("#FBE0DE", "#7F1D1D"), outline=("#D6372E", "#E5534B"), width=1, state="normal")
                        canvas.coords(slot["lost_text"], bar_x1 + (bar_track_width // 2), srv_top + 4)
                        canvas.itemconfigure(slot["lost_text"], state="normal")
                        canvas.itemconfigure(slot["overcap_line"], state="hidden")
                        srv_str = "TIMEOUT"
                    else:
                        canvas.itemconfigure(slot["lost_text"], state="hidden")
                        rtt = sample.server_rtt_ms
                        ratio = min(rtt / GRAPH_MAX_CAP_MS, 1.0)
                        bar_fill_w = max(4.0, bar_track_width * ratio)
                        fill_x2 = min(bar_x2 - 1, bar_x1 + bar_fill_w)

                        if rtt > GRAPH_MAX_CAP_MS:
                            fill_color = STATUS_OVERCAP_PURPLE
                            srv_str = f"{rtt:.0f}m[CAP]"
                        elif rtt > 130.0:
                            fill_color = STATUS_RED
                            srv_str = f"{rtt:.1f}ms"
                        elif rtt > 60.0:
                            fill_color = STATUS_YELLOW
                            srv_str = f"{rtt:.1f}ms"
                        else:
                            fill_color = STATUS_GREEN
                            srv_str = f"{rtt:.1f}ms"

                        canvas.coords(slot["server_bar"], bar_x1 + 1, srv_top, fill_x2, srv_bottom)
                        canvas.itemconfigure(slot["server_bar"], fill=fill_color, outline="", state="normal")

                        if rtt > GRAPH_MAX_CAP_MS:
                            canvas.coords(slot["overcap_line"], bar_x2 - 1, srv_top, bar_x2 - 1, srv_bottom)
                            canvas.itemconfigure(slot["overcap_line"], state="normal")
                        else:
                            canvas.itemconfigure(slot["overcap_line"], state="hidden")

                    # Bottom Half: Local Igloo RTT (50ms scale, min 6px width)
                    igloo_top = srv_bottom + 1
                    igloo_bottom = igloo_top + 6

                    if sample.local_rtt_ms is not None:
                        loc_rtt = sample.local_rtt_ms
                        loc_ratio = min(loc_rtt / LOCAL_IGLOO_CEILING_MS, 1.0)
                        loc_w = max(6.0, bar_track_width * loc_ratio)
                        loc_x2 = min(bar_x2 - 1, bar_x1 + 1 + loc_w)
                        loc_color = STATUS_RED if loc_rtt >= 15.0 else ACCENT_GLACIER_BLUE

                        canvas.coords(slot["igloo_bar"], bar_x1 + 1, igloo_top, loc_x2, igloo_bottom)
                        canvas.itemconfigure(slot["igloo_bar"], fill=loc_color, outline="", state="normal")
                        loc_str = f"{loc_rtt:.1f}ms"
                    else:
                        canvas.itemconfigure(slot["igloo_bar"], state="hidden")
                        loc_str = "--"

                    # Dual readout text
                    val_text = f"{srv_str} | {loc_str}"
                    if sample.is_timeout or (sample.local_rtt_ms is not None and sample.local_rtt_ms >= 15.0):
                        val_color = STATUS_RED
                    elif sample.server_rtt_ms and sample.server_rtt_ms > GRAPH_MAX_CAP_MS:
                        val_color = STATUS_OVERCAP_PURPLE
                    elif sample.server_rtt_ms and sample.server_rtt_ms > 130.0:
                        val_color = STATUS_RED
                    elif sample.server_rtt_ms and sample.server_rtt_ms > 60.0:
                        val_color = STATUS_YELLOW
                    else:
                        val_color = TEXT_SNOW

                # 4. Right Column: RTT Value & Diagnosis Tag Badge
                rtt_val_x = bar_x2 + 10
                canvas.coords(slot["rtt_text"], rtt_val_x, y_top + (ROW_HEIGHT // 2))
                canvas.itemconfigure(slot["rtt_text"], text=val_text, fill=val_color, state="normal")

                # Diagnostic badge pill
                tag = sample.diagnosis_tag
                badge_x = canvas_width - 16
                center_y = y_top + (ROW_HEIGHT // 2)

                if tag in ("PACKET_LOST", "LOCAL_IGLOO_SPIKE", "BUFFERBLOAT_SPIKE", "ISP_BLIZZARD_SPIKE"):
                    if tag == "PACKET_LOST":
                        b_txt = "LOST"; bg_col = ("#FBE0DE", "#7F1D1D"); fg_col = ("#9B1C1C", "#FCA5A5"); out_col = ("#FBE0DE", "#7F1D1D")
                    elif tag == "LOCAL_IGLOO_SPIKE":
                        b_txt = "IGLOO"; bg_col = ("#D6E6F7", "#1F4E79"); fg_col = ("#23405F", "#C9DDF2"); out_col = ("#D6E6F7", "#1F4E79")
                    elif tag == "BUFFERBLOAT_SPIKE":
                        b_txt = "BLOAT"; bg_col = ("#F3E3B8", "#4A3A14"); fg_col = ("#92400E", "#FDE68A"); out_col = ("#F3E3B8", "#4A3A14")
                    else:
                        b_txt = "BLIZZARD"; bg_col = ("#E3E9F3", "#1A2233"); fg_col = ("#26344D", "#C9D6EA"); out_col = ("#3E64A3", "#5B7FBF")

                    w = len(b_txt) * 7 + 12
                    h = 16
                    bx1 = badge_x - w
                    bx2 = badge_x
                    by1 = center_y - (h // 2)
                    by2 = center_y + (h // 2)

                    canvas.coords(slot["diag_badge_box"], bx1, by1, bx2, by2)
                    canvas.itemconfigure(slot["diag_badge_box"], fill=bg_col, outline=out_col, state="normal")
                    canvas.coords(slot["diag_badge_text"], bx1 + (w // 2), center_y)
                    canvas.itemconfigure(slot["diag_badge_text"], text=b_txt, fill=fg_col, font=(FONT_BODY, 8, "bold"), state="normal")
                elif tag == "OK":
                    canvas.itemconfigure(slot["diag_badge_box"], state="hidden")
                    canvas.coords(slot["diag_badge_text"], badge_x - 6, center_y)
                    canvas.itemconfigure(slot["diag_badge_text"], text="", fill=STATUS_GREEN, font=(FONT_BODY, 9, "bold"), state="normal")
                else:
                    canvas.itemconfigure(slot["diag_badge_box"], state="hidden")
                    canvas.itemconfigure(slot["diag_badge_text"], state="hidden")
            else:
                # Slot is outside visible rows; hide all items
                for item_id in slot.values():
                    canvas.itemconfigure(item_id, state="hidden")

    # ========================================================================
    # 5. IN-PLACE HOVER DEBOUNCING & INTERACTION
    # ========================================================================
    def _update_hover_slot(self, row_idx: Optional[int]) -> None:
        """
        Updates ONLY the hover/selection box of the affected slot via itemconfigure.
        Does NOT re-render layout, ensuring 0% hover flicker.
        """
        if row_idx is None:
            return
        active_samples = self._get_active_samples()
        if not active_samples or row_idx < 0 or row_idx >= len(active_samples):
            return

        slot_idx = row_idx - self._scroll_top_row
        if slot_idx < 0 or slot_idx >= len(self._row_slots):
            return

        slot = self._row_slots[slot_idx]
        sample_idx = len(active_samples) - 1 - row_idx
        if sample_idx < 0 or sample_idx >= len(active_samples):
            return
        sample = active_samples[sample_idx]

        canvas_width = self._plot_canvas.winfo_width()
        y_top = slot_idx * ROW_HEIGHT
        y_bottom = y_top + ROW_HEIGHT

        is_selected = (self._selected_sample is not None and self._selected_sample.seq_id == sample.seq_id)
        is_hovered = (self._hovered_row_idx == row_idx)

        if is_selected:
            self._plot_canvas.coords(slot["hover_box"], 2, y_top + 1, canvas_width - 2, y_bottom - 1)
            self._plot_canvas.itemconfigure(slot["hover_box"], fill=("#FFFFFF", "#15181D"), outline=SELECT_BORDER, width=1.5, state="normal")
            self._plot_canvas.itemconfigure(slot["separator"], state="hidden")
            self._plot_canvas.itemconfigure(slot["seq_text"], fill=TEXT_SNOW)
        elif is_hovered:
            self._plot_canvas.coords(slot["hover_box"], 2, y_top + 1, canvas_width - 2, y_bottom - 1)
            self._plot_canvas.itemconfigure(slot["hover_box"], fill=HOVER_BG, outline=HOVER_BORDER, width=1, state="normal")
            self._plot_canvas.itemconfigure(slot["separator"], state="hidden")
            self._plot_canvas.itemconfigure(slot["seq_text"], fill=TEXT_SNOW)
        else:
            self._plot_canvas.itemconfigure(slot["hover_box"], state="hidden")
            self._plot_canvas.coords(slot["separator"], 4, y_bottom, canvas_width - 4, y_bottom)
            self._plot_canvas.itemconfigure(slot["separator"], state="normal")
            self._plot_canvas.itemconfigure(slot["seq_text"], fill=("#5B6472", "#9BA3AF"))

    def _on_canvas_motion(self, event: tk.Event) -> None:
        """
        Calculates row under cursor.
        CRITICAL: If mouse is moving within the same row, returns immediately!
        """
        active_samples = self._get_active_samples()
        if not active_samples:
            return

        rel_row = event.y // ROW_HEIGHT
        row_idx = self._scroll_top_row + rel_row

        if 0 <= row_idx < len(active_samples):
            new_hover = row_idx
        else:
            new_hover = None

        # Same row -> do nothing, eliminate motion flicker!
        if new_hover == self._hovered_row_idx:
            return

        old_hover = self._hovered_row_idx
        self._hovered_row_idx = new_hover

        self._update_hover_slot(old_hover)
        self._update_hover_slot(new_hover)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Handles canvas resize."""
        self._request_redraw()

    def _on_canvas_enter(self, event: tk.Event) -> None:
        """
        Pauses auto-scrolling when mouse enters canvas.
        Freezes snapshot so rows don't shift under cursor.
        """
        if not self._is_hover_paused:
            self._is_hover_paused = True
            self._frozen_samples = list(self._samples)
            self._update_status_badge()

    def _on_canvas_leave(self, event: tk.Event) -> None:
        """Unpauses auto-scrolling when mouse leaves canvas."""
        old_hover = self._hovered_row_idx
        self._hovered_row_idx = None
        self._update_hover_slot(old_hover)

        if self._is_hover_paused:
            self._is_hover_paused = False
            if not self._manually_scrolled:
                self._frozen_samples = None
                self._scroll_top_row = 0
            self._update_status_badge()
            self._request_redraw()

    def _on_canvas_click(self, event: tk.Event) -> None:
        """Selects clicked row and populates Forensic Inspector."""
        active_samples = self._get_active_samples()
        if not active_samples:
            return

        rel_row = event.y // ROW_HEIGHT
        row_idx = self._scroll_top_row + rel_row

        if 0 <= row_idx < len(active_samples):
            sample_idx = len(active_samples) - 1 - row_idx
            sample = active_samples[sample_idx]
            self._select_sample(sample)
            self._request_redraw()

    def _on_canvas_mousewheel(self, event: tk.Event) -> None:
        """Handles mouse wheel scrolling."""
        active_samples = self._get_active_samples()
        if not active_samples:
            return

        step = -int(event.delta / 120) * 3
        self._scroll_by_rows(step)

    def _on_scrollbar_move(self, action: str, *args) -> None:
        """Handles CTkScrollbar user drag."""
        active_samples = self._get_active_samples()
        total_samples = len(active_samples)
        if total_samples == 0:
            return

        canvas_height = self._plot_canvas.winfo_height()
        max_start_row = max(0, total_samples - (canvas_height // ROW_HEIGHT))

        if action == "moveto":
            fraction = float(args[0])
            new_row = int(fraction * total_samples)
            self._scroll_top_row = max(0, min(max_start_row, new_row))
            self._manually_scrolled = (self._scroll_top_row > 0)
            self._update_status_badge()
            self._request_redraw()
        elif action == "scroll":
            count = int(args[0])
            self._scroll_by_rows(count * 2)

    def _scroll_by_rows(self, delta_rows: int) -> None:
        """Scrolls viewport by delta_rows."""
        active_samples = self._get_active_samples()
        total_samples = len(active_samples)
        if total_samples == 0:
            return

        canvas_height = self._plot_canvas.winfo_height()
        max_start_row = max(0, total_samples - (canvas_height // ROW_HEIGHT))

        new_top = max(0, min(max_start_row, self._scroll_top_row + delta_rows))
        if new_top != self._scroll_top_row:
            self._scroll_top_row = new_top
            self._manually_scrolled = (self._scroll_top_row > 0)
            self._update_status_badge()
            self._request_redraw()

    def _on_igloo_switch_toggled(self) -> None:
        self._show_local_igloo = bool(self._igloo_switch.get())
        self._update_column_headers()
        self._render_canvas()

    def _update_status_badge(self) -> None:
        """
        State-guarded update to prevent layout flashing in CustomTkinter.
        Only reconfigures when state key actually changes.
        """
        state_key = (self._is_hover_paused, self._manually_scrolled)
        if self._last_status_badge_state == state_key:
            return
        self._last_status_badge_state = state_key

        if self._is_hover_paused:
            self._status_badge.configure(
                text="⏸ Hovering: List Paused (Click a bar to inspect)",
                text_color=STATUS_YELLOW
            )
            if not self._resume_btn.winfo_ismapped():
                self._resume_btn.pack(side="right", padx=6)
        elif self._manually_scrolled:
            self._status_badge.configure(
                text="↕ Manually Scrolled (Auto-follow Paused)",
                text_color=STATUS_YELLOW
            )
            if not self._resume_btn.winfo_ismapped():
                self._resume_btn.pack(side="right", padx=6)
        else:
            self._status_badge.configure(
                text="LIVE (Auto-follow)",
                text_color=STATUS_GREEN
            )
            if self._resume_btn.winfo_ismapped():
                self._resume_btn.pack_forget()

    # ========================================================================
    # 6. NOOT FORENSIC INSPECTOR PANEL
    # ========================================================================
    def _select_sample(self, sample: PingSample) -> None:
        """Populates the bottom card with forensic packet details."""
        self._selected_sample = sample
        self._inspector_placeholder.pack_forget()
        self._inspector_content.pack(fill="x", expand=True)

        self._insp_seq_badge.configure(text=f"PKT #{sample.seq_id:03d}")
        time_str = datetime.fromtimestamp(sample.timestamp).strftime("%H:%M:%S.%f")[:-3]
        self._insp_time_lbl.configure(text=f"Time: {time_str}")
        self._insp_proto_lbl.configure(
            text=f"Protocol: {sample.protocol_used} ({sample.payload_bytes} B Payload)"
        )

        tag = sample.diagnosis_tag
        if tag == "PACKET_LOST":
            tag_color = STATUS_RED
            tag_name = "[PACKET LOST IN TRANSIT]"
        elif tag == "LOCAL_IGLOO_SPIKE":
            tag_color = ACCENT_BEAK_ORANGE
            tag_name = "[LOCAL IGLOO WI-FI SPIKE]"
        elif tag == "BUFFERBLOAT_SPIKE":
            tag_color = STATUS_YELLOW
            tag_name = "[BUFFERBLOAT LOAD SPIKE]"
        elif tag == "ISP_BLIZZARD_SPIKE":
            tag_color = ACCENT_GLACIER_BLUE
            tag_name = "[ISP ROUTING BLIZZARD]"
        else:
            tag_color = STATUS_GREEN
            tag_name = "[ROCK SOLID / NORMAL]"

        self._insp_tag_badge.configure(text=tag_name, text_color=tag_color)

        if sample.is_timeout or sample.server_rtt_ms is None:
            server_str = "TIMEOUT (Dropped)"
            server_color = STATUS_RED
        elif sample.server_rtt_ms > GRAPH_MAX_CAP_MS:
            server_str = f"{sample.server_rtt_ms:.1f} ms [VISUAL CAP EXCEEDED]"
            server_color = STATUS_OVERCAP_PURPLE
        else:
            server_str = f"{sample.server_rtt_ms:.1f} ms"
            server_color = STATUS_GREEN if sample.server_rtt_ms <= 60 else (STATUS_YELLOW if sample.server_rtt_ms <= 130 else STATUS_RED)

        self._chip_server.configure(text=f"Game Server: {server_str}", text_color=server_color)

        local_str = f"{sample.local_rtt_ms:.1f} ms" if sample.local_rtt_ms is not None else "N/A (Router Ping Blocked)"
        local_color = STATUS_YELLOW if (sample.local_rtt_ms and sample.local_rtt_ms > 15.0) else ACCENT_GLACIER_BLUE
        self._chip_local.configure(text=f"Local Igloo Router: {local_str}", text_color=local_color)

        self._chip_wan.configure(text=f"WAN Data: {sample.wan_bytes_this_sample} Bytes")

        detail_msg = sample.diagnosis_detail if sample.diagnosis_detail else "Normal ping latency."
        self._insp_detail_lbl.configure(text=f"Noot Forensic Analysis: {detail_msg}")
        self._insp_detail_box.configure(border_color=tag_color)

    def _clear_selection(self) -> None:
        """Clears inspector selection and restores default placeholder."""
        self._selected_sample = None
        self._inspector_content.pack_forget()
        self._inspector_placeholder.pack(fill="x", padx=12, pady=10)
        self._request_redraw()
