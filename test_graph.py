"""
Ping Gu - Phase 2 Visual Verification & Interactive Graph Test Harness
Launches a standalone CustomTkinter window hosting VerticalPingGraph.
Features automated 10Hz simulated packet stream, visual ceiling test buttons (>250ms),
forensic inspector validation, and headless verification mode.
"""

import argparse
import random
import sys
import threading
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import customtkinter as ctk

from analyzer import analyze_sample
from presets import (
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
from ui_vertical_graph import VerticalPingGraph


class TestGraphApp(ctk.CTk):
    """Interactive visual test harness for VerticalPingGraph."""

    def __init__(self, auto_start: bool = True):
        super().__init__()

        self.title("Ping Gu - Phase 2: Vertical Latency Graph Test Harness")
        self.geometry("960x720")
        self.minsize(780, 500)
        self.configure(fg_color=BG_TUXEDO_DARK)

        # Simulation state
        self._seq_id = 0
        self._is_streaming = False
        self._stream_timer_id = None
        self._baseline_ms = 22.0

        self._build_top_banner()
        self._build_test_toolbar()
        self._build_graph_view()

        if auto_start:
            self.toggle_stream()

    def _build_top_banner(self) -> None:
        """Top banner with Arctic Tuxedo theme info and test guidelines."""
        banner_frame = ctk.CTkFrame(self, fg_color=CARD_DARK, corner_radius=8)
        banner_frame.pack(fill="x", padx=10, pady=(10, 4))

        title = ctk.CTkLabel(
            banner_frame,
            text="🐧 Ping Gu — Virtualized Vertical Bar-List Graph (Phase 2 Test)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_SNOW
        )
        title.pack(side="left", padx=12, pady=6)

        sub_info = ctk.CTkLabel(
            banner_frame,
            text="Hover over list to pause • Click any row to inspect forensics • 250ms visual cap ceiling",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8"
        )
        sub_info.pack(side="right", padx=12, pady=6)

    def _build_test_toolbar(self) -> None:
        """Test controls bar with packet injection buttons."""
        bar = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=8)
        bar.pack(fill="x", padx=10, pady=4)

        # Stream toggle button
        self._btn_stream = ctk.CTkButton(
            bar,
            text="▶ Start Auto-Stream (10Hz)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=STATUS_GREEN,
            hover_color="#16A34A",
            width=175,
            command=self.toggle_stream
        )
        self._btn_stream.pack(side="left", padx=(8, 6), pady=6)

        # Manual Injection buttons
        btn_normal = ctk.CTkButton(
            bar,
            text="+ Normal (24ms)",
            font=ctk.CTkFont(size=10),
            fg_color="#334155",
            hover_color="#475569",
            width=100,
            command=self.inject_normal
        )
        btn_normal.pack(side="left", padx=3, pady=6)

        btn_igloo = ctk.CTkButton(
            bar,
            text="+ Igloo Spike (120ms)",
            font=ctk.CTkFont(size=10),
            fg_color="#0284C7",
            hover_color="#0369A1",
            width=125,
            command=self.inject_igloo_spike
        )
        btn_igloo.pack(side="left", padx=3, pady=6)

        btn_blizzard = ctk.CTkButton(
            bar,
            text="+ ISP Blizzard (195ms)",
            font=ctk.CTkFont(size=10),
            fg_color="#4338CA",
            hover_color="#3730A3",
            width=125,
            command=self.inject_isp_blizzard
        )
        btn_blizzard.pack(side="left", padx=3, pady=6)

        btn_overcap = ctk.CTkButton(
            bar,
            text="+ Over-Cap (1450ms)",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=STATUS_OVERCAP_PURPLE,
            hover_color="#9333EA",
            width=130,
            command=self.inject_overcap
        )
        btn_overcap.pack(side="left", padx=3, pady=6)

        btn_bloat = ctk.CTkButton(
            bar,
            text="+ Bufferbloat (85ms)",
            font=ctk.CTkFont(size=10),
            fg_color="#D97706",
            hover_color="#B45309",
            width=120,
            command=self.inject_bufferbloat
        )
        btn_bloat.pack(side="left", padx=3, pady=6)

        btn_loss = ctk.CTkButton(
            bar,
            text="+ Timeout / Lost",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=STATUS_RED,
            hover_color="#DC2626",
            width=105,
            command=self.inject_timeout
        )
        btn_loss.pack(side="left", padx=3, pady=6)

    def _build_graph_view(self) -> None:
        """Embeds the VerticalPingGraph widget."""
        self.graph = VerticalPingGraph(
            self,
            maxlen=500,
            show_local_igloo=False
        )
        self.graph.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    # ========================================================================
    # PACKET INJECTION HANDLERS
    # ========================================================================
    def inject_sample(
        self,
        server_rtt: float | None,
        local_rtt: float | None,
        is_timeout: bool = False,
        under_load: bool = False,
        protocol: str = "ICMP",
        payload_bytes: int = 256
    ) -> PingSample:
        """Creates and tags a simulated PingSample, then sends it to the graph."""
        self._seq_id += 1
        wan_bytes = (payload_bytes + 28) * 2 if not is_timeout else (payload_bytes + 28)

        sample = PingSample(
            seq_id=self._seq_id,
            timestamp=time.time(),
            target_host="1.1.1.1",
            server_rtt_ms=server_rtt,
            local_rtt_ms=local_rtt,
            is_timeout=is_timeout,
            protocol_used=protocol,
            payload_bytes=payload_bytes,
            wan_bytes_this_sample=wan_bytes,
            under_load_test=under_load
        )
        # Apply forensic diagnostics
        analyze_sample(sample, self._baseline_ms)
        self.graph.add_sample(sample)
        return sample

    def inject_normal(self) -> None:
        rtt = round(random.uniform(20.0, 32.0), 2)
        local_rtt = round(random.uniform(1.2, 3.5), 2)
        self.inject_sample(rtt, local_rtt)

    def inject_igloo_spike(self) -> None:
        local_rtt = round(random.uniform(85.0, 140.0), 2)
        rtt = round(local_rtt + random.uniform(15.0, 30.0), 2)
        self.inject_sample(rtt, local_rtt)

    def inject_isp_blizzard(self) -> None:
        local_rtt = round(random.uniform(1.2, 2.8), 2)
        rtt = round(random.uniform(185.0, 215.0), 2)
        self.inject_sample(rtt, local_rtt)

    def inject_overcap(self) -> None:
        local_rtt = round(random.uniform(1.5, 4.0), 2)
        rtt = round(random.uniform(1200.0, 1600.0), 2)
        self.inject_sample(rtt, local_rtt)

    def inject_bufferbloat(self) -> None:
        local_rtt = round(random.uniform(2.0, 5.0), 2)
        rtt = round(random.uniform(75.0, 110.0), 2)
        self.inject_sample(rtt, local_rtt, under_load=True)

    def inject_timeout(self) -> None:
        local_rtt = round(random.uniform(1.5, 3.0), 2)
        self.inject_sample(None, local_rtt, is_timeout=True)

    # ========================================================================
    # AUTO-STREAM ENGINE (10Hz)
    # ========================================================================
    def toggle_stream(self) -> None:
        """Starts or pauses the automated 10Hz test packet feed."""
        if self._is_streaming:
            self._is_streaming = False
            if self._stream_timer_id:
                self.after_cancel(self._stream_timer_id)
                self._stream_timer_id = None
            self._btn_stream.configure(
                text="▶ Resume Stream (10Hz)",
                fg_color=STATUS_GREEN
            )
        else:
            self._is_streaming = True
            self._btn_stream.configure(
                text="⏸ Pause Stream",
                fg_color=STATUS_RED
            )
            self._schedule_stream_tick()

    def _schedule_stream_tick(self) -> None:
        """Generates realistic packet traffic at 100ms (10Hz) interval."""
        if not self._is_streaming:
            return

        # Periodic scenario generation
        roll = random.random()
        if roll < 0.70:
            # 70% normal ping
            self.inject_normal()
        elif roll < 0.78:
            # Local Wi-Fi Igloo spike
            self.inject_igloo_spike()
        elif roll < 0.86:
            # ISP Blizzard routing spike
            self.inject_isp_blizzard()
        elif roll < 0.91:
            # Severe over-cap spike (>250ms)
            self.inject_overcap()
        elif roll < 0.96:
            # Bufferbloat under load
            self.inject_bufferbloat()
        else:
            # Packet loss timeout
            self.inject_timeout()

        self._stream_timer_id = self.after(100, self._schedule_stream_tick)


def run_headless_verification() -> bool:
    """
    Automated non-interactive verification for CI/Terminal testing.
    Validates sample ingestion, visual cap logic, hover pause state,
    and forensic inspector updates without blocking the terminal.
    """
    print("\n" + "=" * 65)
    print("  PING GU - PHASE 2 HEADLESS VERIFICATION")
    print("=" * 65)

    app = TestGraphApp(auto_start=False)
    app.geometry("1000x650")
    app.update()
    app.withdraw()  # Hide window during automated checks
    # A pointer already over the canvas fires <Enter> and freezes an empty sample list;
    # release it so rendering reads live samples regardless of the machine's cursor position.
    app.graph._on_canvas_leave(None)

    try:
        graph = app.graph
        print("[1/6] Injecting test packets into VerticalPingGraph...")

        # 1. Inject normal sample
        s_norm = app.inject_sample(24.5, 1.8)
        assert graph.samples_count == 1, "Normal sample not added"
        print(f"      OK: Normal sample #{s_norm.seq_id} added (24.5ms)")

        # 2. Inject over-cap spike (1450ms)
        s_cap = app.inject_sample(1450.0, 2.1)
        assert graph.samples_count == 2, "Over-cap sample not added"
        assert s_cap.server_rtt_ms > GRAPH_MAX_CAP_MS, "Sample should exceed visual cap"
        print(f"      OK: Over-cap sample #{s_cap.seq_id} added (1450.0ms > 250ms ceiling)")

        # 3. Inject Igloo spike
        s_igloo = app.inject_sample(110.0, 95.0)
        assert s_igloo.diagnosis_tag == "LOCAL_IGLOO_SPIKE", f"Tag mismatch: {s_igloo.diagnosis_tag}"
        print(f"      OK: Igloo spike #{s_igloo.seq_id} tagged [{s_igloo.diagnosis_tag}]")

        # 4. Inject Timeout
        s_loss = app.inject_sample(None, 1.5, is_timeout=True)
        assert s_loss.diagnosis_tag == "PACKET_LOST", f"Tag mismatch: {s_loss.diagnosis_tag}"
        print(f"      OK: Timeout sample #{s_loss.seq_id} tagged [{s_loss.diagnosis_tag}]")

        # 5. Verify Forensic Inspector Selection
        print("[2/6] Testing Forensic Inspector selection...")
        graph._select_sample(s_cap)
        selected = graph.get_selected_sample()
        assert selected is not None and selected.seq_id == s_cap.seq_id, "Selection failed"
        assert "VISUAL CAP EXCEEDED" in graph._chip_server.cget("text"), "Server chip text missing cap notice"
        print(f"      OK: Inspector locked to sample #{selected.seq_id} with visual cap warning")

        # 6. Test Igloo Overlay Toggle
        print("[3/6] Testing Local Igloo Overlay Toggle...")
        graph.set_show_local_igloo(True)
        assert graph._show_local_igloo is True, "Igloo overlay not enabled"
        bar_txt = graph._lbl_col_bar.cget("text")
        rtt_hdr = graph._lbl_col_rtt.cget("text")
        assert "SPECTRUM (TOP: SERVER 250ms | BOTTOM: IGLOO 50ms)" in bar_txt, f"Dual spectrum header mismatch: '{bar_txt}'"
        assert "SRV / IGLOO / DIAG" in rtt_hdr, f"Dual RTT header mismatch: '{rtt_hdr}'"

        # Verify rendered text on visible row contains dual format (server | local)
        slot0_txt = graph._plot_canvas.itemcget(graph._row_slots[0]["rtt_text"], "text")
        assert " | " in slot0_txt, f"Dual readout missing server/local separator in row text: '{slot0_txt}' (hover_paused={graph._is_hover_paused})"
        print(f"      OK: Dual-track igloo overlay active: '{slot0_txt}'")

        graph.set_show_local_igloo(False)
        assert graph._show_local_igloo is False, "Igloo overlay not disabled"
        bar_txt = graph._lbl_col_bar.cget("text")
        rtt_hdr = graph._lbl_col_rtt.cget("text")
        assert "LATENCY SPECTRUM (0 ──────── 250ms CAP)" in bar_txt, f"Single spectrum header mismatch: '{bar_txt}'"
        assert "LATENCY  /  DIAGNOSIS" in rtt_hdr, f"Single RTT header mismatch: '{rtt_hdr}'"
        slot0_single_txt = graph._plot_canvas.itemcget(graph._row_slots[0]["rtt_text"], "text")
        assert " | " not in slot0_single_txt, f"Single readout should not contain dual separator: '{slot0_single_txt}'"
        print("      OK: Local Igloo overlay toggle works cleanly (split bars & dual readout verified)")

        # 7. Test Hover Pause & Freeze
        print("[4/6] Testing Hover Pause & Viewport Freeze...")
        graph._on_canvas_enter(None)
        assert graph._is_hover_paused is True, "Hover pause not activated"
        assert graph._frozen_samples is not None, "Snapshot not frozen on hover"
        graph._on_canvas_leave(None)
        assert graph._is_hover_paused is False, "Hover pause not deactivated"
        print("      OK: Hover pause & freeze mechanism verified")

        # 8. Test Scrolling & Resume Live
        print("[5/6] Testing Virtualized Scroll & Resume Live...")
        for i in range(25):
            app.inject_sample(25.0 + i, 1.5)
        # Scroll down by 5 rows
        graph._scroll_by_rows(5)
        assert graph._manually_scrolled is True, "Manual scroll state not set"
        assert graph._scroll_top_row > 0, "Top row should have advanced"
        # Resume live
        graph.resume_live()
        assert graph._manually_scrolled is False, "Manual scroll not reset by resume_live"
        assert graph._scroll_top_row == 0, "Top row should be reset to 0 by resume_live"
        print("      OK: Manual scroll and Resume Live behavior verified")

        # 9. Test Viewport Render Dispatch
        print("[6/6] Testing Canvas Redraw Dispatch & Clear...")
        graph._render_canvas()
        graph.clear_samples()
        assert graph.samples_count == 0, "Graph clear failed"
        assert graph.get_selected_sample() is None, "Selection not cleared"
        print("      OK: Viewport culling canvas redraw & clear executed cleanly")

        print("\n" + "=" * 65)
        print("  ALL PHASE 2 GRAPH VERIFICATION CHECKS PASSED (100% OK)!")
        print("=" * 65 + "\n")
        return True

    finally:
        app.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ping Gu Phase 2 Graph Test Harness")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run non-interactive automated verification checks"
    )
    args = parser.parse_args()

    if args.headless:
        success = run_headless_verification()
        sys.exit(0 if success else 1)
    else:
        # Launch interactive UI
        app = TestGraphApp(auto_start=True)
        app.mainloop()


if __name__ == "__main__":
    main()
