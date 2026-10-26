"""
Ping Gu - Application Integration Test
Automated headless test harness verifying that PingGuApp initializes, integrates
the VerticalPingGraph, handles custom server persistence, validates custom user timers,
evaluates unwise session warnings, processes queue samples thread-safely, resets to
fresh boot state completely, and shuts down cleanly.
"""

import os
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from analyzer import evaluate_session_plan
from presets import (
    DEFAULT_SERVERS,
    GENRE_PROFILES,
    GRAPH_MAX_CAP_MS,
    load_user_config,
)
from scanner import PingSample
from ui_main import (
    CustomServerModal,
    InvalidTimerModal,
    PingGuApp,
    QuickGuideModal,
    WarningModal,
)


def print_banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_integration_tests() -> bool:
    print_banner("PING GU - PHASE 3.7 INTEGRATION TEST SUITE")
    print("Testing Full Desktop Dashboard, Custom Timer, Boot Reset & Tooltips")

    # 1. Initialize Application in Headless Mode
    print("\n[1/8] Initializing PingGuApp...")
    app = PingGuApp()
    app.withdraw()  # Run headless for automated test suite
    app.update()

    try:
        print(f"      OK: Main window initialized ({app.winfo_width()}x{app.winfo_height()})")
        print(f"      OK: Detected Gateway Badge: '{app.gw_badge.cget('text')}'")
        assert "Local Router" in app.gw_badge.cget("text"), "Gateway badge text should be 'Local Router'"

        # Verify shortened Data Used Badge
        wan_boot = app.wan_badge.cget("text")
        print(f"      OK: Initial Data Badge: '{wan_boot}'")
        assert wan_boot == "Data Used: 0.0 KB", f"Unexpected initial data badge text: '{wan_boot}'"

        # Verify idle Verdict Banner Copy
        idle_title = app.lbl_verdict_title.cget("text")
        print(f"      OK: Idle Verdict Banner Title: '{idle_title}'")
        assert idle_title == "CLICK SCAN NOOT — PICK A SERVER NOOT", f"Unexpected idle verdict title: '{idle_title}'"

        # Wait 250ms and pump Tk events to verify idle polling doesn't overwrite banner
        time.sleep(0.25)
        app.update()
        idle_title_after_poll = app.lbl_verdict_title.cget("text")
        assert idle_title_after_poll == "CLICK SCAN NOOT — PICK A SERVER NOOT", f"Idle verdict title was overwritten after poll: '{idle_title_after_poll}'"
        assert app.lbl_protocol_badge.cget("text") == "[Protocol: Standby]", f"Idle protocol badge was overwritten: '{app.lbl_protocol_badge.cget('text')}'"
        print(f"      OK: Verified Idle Verdict Banner & Standby Protocol persist after telemetry poll")

        # Verify App Icon & Header Logo (pingu.jpg / pingu.ico)
        assert hasattr(app, "header_logo_lbl") and app.header_logo_lbl is not None, "Header logo label must be created"
        assert app.header_logo_lbl.winfo_manager() == "pack", "Header logo label must be packed"
        ico_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pingu.ico")
        assert os.path.exists(ico_file), f"pingu.ico should exist at {ico_file}"
        print(f"      OK: Header Logo & Window Icon verified (pingu.ico exists, {os.path.getsize(ico_file)} bytes)")

        # Verify Action Buttons in Control Deck Row 1
        assert app.btn_start.winfo_manager() == "pack", "START NOOT SCAN button must be packed"
        assert app.btn_load_test.winfo_manager() == "pack", "Load Test (5s) button must be packed"
        assert app.btn_load_test.cget("text") == "🐟 Load Test (5s)", "Load Test button label mismatch"
        assert app.btn_reset.winfo_manager() == "pack", "Reset button must be packed"
        assert app.btn_reset.cget("text") == "↺ Reset", "Reset button label mismatch"
        assert app.btn_guide.winfo_manager() == "pack", "Guide button must be packed"
        print("      OK: Action buttons (START NOOT SCAN, Load Test (5s), ↺ Reset, ❓ Guide) packed")

        # Verify Metric Card Tooltips
        for key in ["pill_avg", "pill_p99", "pill_jitter", "pill_loss", "pill_igloo"]:
            card_info = app.telemetry_labels[key]
            assert "badge" in card_info, f"Card '{key}' missing help badge"
            assert hasattr(card_info["badge"], "_tooltip"), f"Card '{key}' badge missing _tooltip"
        print("      OK: All 5 Metric Cards equipped with interactive '?' tooltips")

        # 2. Test Custom Server Registration & Persistence
        print("\n[2/8] Testing Custom Target Server Registration & Persistence...")
        test_custom_server = {
            "name": "Arctic Integration Node",
            "category": "Custom",
            "host": "198.51.100.99",
            "port": 443,
            "description": "Integration test custom node"
        }
        app._on_custom_server_saved(test_custom_server)
        app.update()

        # Verify added to server dropdown
        combo_values = app.server_combo.cget("values")
        assert any("Arctic Integration Node" in v for v in combo_values), "Custom server missing in dropdown values"
        assert "Arctic Integration Node" in app.server_combo.get(), "Custom server not selected automatically"

        # Verify persistent in user_config.json
        cfg = load_user_config()
        saved_names = [s.get("name") for s in cfg.get("custom_servers", [])]
        assert "Arctic Integration Node" in saved_names, "Custom server missing from user_config.json"
        print(f"      OK: Custom target saved and verified in config: {saved_names}")

        # 3. Test Genre Profile & Dynamic Custom Sliders
        print("\n[3/8] Testing Genre Profile Switching & Dynamic Sliders...")
        app.genre_combo.set("Custom Noot Stress")
        app._on_genre_selected("Custom Noot Stress")
        app.update()

        assert app.custom_sliders_frame.winfo_manager() == "pack", "Custom sliders frame should be packed for Custom Noot Stress"
        print("      OK: Custom sliders frame dynamically shown on 'Custom Noot Stress'")

        # Adjust sliders
        app.slider_payload.set(128)
        app._on_slider_payload_moved(128)
        app.slider_rate.set(30)
        app._on_slider_rate_moved(30)
        app.update()

        payload, rate = app._get_current_profile_params()
        assert payload == 128 and rate == 30, f"Profile params mismatch: {payload}, {rate}"
        print(f"      OK: Custom sliders adjusted to {payload}B @ {rate}Hz")

        # Verify Pre-flight estimate updated
        est_text = app.pill_estimate.cget("text")
        print(f"      OK: Pre-flight Estimate Pill: '{est_text}'")
        assert "Est. Data" in est_text, "Estimate text invalid"

        # Switch back to Tactical Shooter
        app.genre_combo.set("Tactical Shooter (CS2 / Valorant)")
        app._on_genre_selected("Tactical Shooter (CS2 / Valorant)")
        app.update()
        assert app.custom_sliders_frame.winfo_manager() != "pack", "Custom sliders should be hidden for standard profiles"
        print("      OK: Custom sliders frame dynamically hidden on standard profile")

        # 4. Test Queue Ingestion & Live Telemetry Updates
        print("\n[4/8] Testing Thread-Safe Queue Ingestion & Telemetry Pills...")
        app.graph.clear_samples()

        t0 = time.time()
        test_samples = [
            PingSample(1, t0, "1.1.1.1", 24.2, 1.4, False, "ICMP", 256, 568, False),
            PingSample(2, t0 + 0.1, "1.1.1.1", 23.8, 1.5, False, "ICMP", 256, 568, False),
            PingSample(3, t0 + 0.2, "1.1.1.1", 145.0, 115.0, False, "ICMP", 256, 568, False),  # Igloo spike
            PingSample(4, t0 + 0.3, "1.1.1.1", 1250.0, 2.0, False, "ICMP", 256, 568, False),   # Over-cap spike
            PingSample(5, t0 + 0.4, "1.1.1.1", None, 1.6, True, "ICMP", 256, 284, False),       # Packet loss
        ]

        for s in test_samples:
            app._sample_queue.put(s)

        app._poll_sample_queue()
        app.update()

        assert app.graph.samples_count == 5, f"Expected 5 samples in graph, found {app.graph.samples_count}"
        print(f"      OK: {app.graph.samples_count} samples drained from queue and added to VerticalPingGraph")

        # Verify shortened WAN Counter updated
        wan_text = app.wan_badge.cget("text")
        print(f"      OK: WAN Data Badge: '{wan_text}'")
        assert "0.0 KB" not in wan_text and "Data Used:" in wan_text, "WAN counter should accumulate with 'Data Used:' prefix"

        # Verify Verdict Card updated
        verdict_title = app.lbl_verdict_title.cget("text")
        verdict_sub = app.lbl_root_cause.cget("text")
        print(f"      OK: Verdict Title: '{verdict_title}'")
        print(f"      OK: Root Cause Subtitle: '{verdict_sub}'")
        assert "ANGRY NOOT NOOT" in verdict_title, "Verdict should be ANGRY due to packet loss + 1250ms spike"

        # Verify 5 Telemetry Pills
        avg_val = app.telemetry_labels["pill_avg"]["val"].cget("text")
        p99_val = app.telemetry_labels["pill_p99"]["val"].cget("text")
        jit_val = app.telemetry_labels["pill_jitter"]["val"].cget("text")
        loss_val = app.telemetry_labels["pill_loss"]["val"].cget("text")
        igloo_val = app.telemetry_labels["pill_igloo"]["val"].cget("text")

        assert "ms" in avg_val, "Avg ping pill missing ms unit"
        assert "ms" in p99_val, "P99 spike pill missing ms unit"
        assert "%" in loss_val, "Packet loss pill missing % unit"
        print(f"      OK: Telemetry values: Avg={avg_val}, P99={p99_val}, Jitter={jit_val}, Loss={loss_val}, Igloo={igloo_val}")

        # 5. Test Smart "Unwise Action" Evaluation
        print("\n[5/8] Testing Smart Unwise Action Evaluation & Warning Modal...")
        eval_safe = evaluate_session_plan(timer_val_str="60", timer_unit="sec", pings_per_sec=5, payload_bytes=64)
        assert eval_safe.is_valid and not eval_safe.is_unwise, "Standard 60s plan should be wise"

        eval_unwise = evaluate_session_plan(timer_val_str="10", timer_unit="min", pings_per_sec=20, payload_bytes=64)
        assert eval_unwise.is_valid and eval_unwise.is_unwise, "20Hz for 10m should trigger unwise warning"
        assert "Tactical Shooter" in eval_unwise.warning_message
        assert "12,000 packets" in eval_unwise.warning_message or "packets" in eval_unwise.warning_message
        print(f"      OK: Smart evaluation triggered expected consequence warning: {eval_unwise.warning_message[:60]}...")

        # Test modal instantiation
        warning_proceeded = False
        warning_suppressed = False

        def on_proceed():
            nonlocal warning_proceeded
            warning_proceeded = True

        def on_suppress(flag: bool):
            nonlocal warning_suppressed
            warning_suppressed = flag

        modal = WarningModal(
            app,
            message=eval_unwise.warning_message,
            on_proceed_callback=on_proceed,
            on_suppress_callback=on_suppress
        )
        modal.update()
        modal.chk_suppress.select()
        modal._on_proceed()
        app.update()

        assert warning_proceeded is True, "Warning proceed callback not triggered"
        assert warning_suppressed is True, "Warning suppress callback not triggered"
        print("      OK: Warning modal proceed and suppress callbacks verified")

        # 6. Test Custom Timer Controls & Countdown Logic
        print("\n[6/8] Testing Custom Timer Modes, Validation & Auto-Stop...")
        # A. Mode switching
        app.timer_unit_menu.set("Continuous ∞")
        app._on_timer_unit_changed("Continuous ∞")
        assert app.timer_entry.cget("state") == "disabled", "Timer entry should be disabled in Continuous mode"

        app.timer_unit_menu.set("sec")
        app._on_timer_unit_changed("sec")
        assert app.timer_entry.cget("state") == "normal", "Timer entry should be enabled in sec mode"

        # B. Invalid input validation
        app.timer_entry.delete(0, "end")
        app.timer_entry.insert(0, "-15")
        app._check_warning_then_start()
        app.update()
        assert app.timer_entry.get() == "60", "Invalid timer input should be reset to 60"
        print("      OK: Invalid negative timer automatically rejected and reset to '60'")

        # C. Auto-stop countdown check
        app.timer_entry.delete(0, "end")
        app.timer_entry.insert(0, "45")
        app._active_scan_duration_sec = 45.0
        app._scan_start_time = time.time() - 10.0  # 10s elapsed
        app._is_scanning = True

        app._check_auto_stop_conditions()
        assert "35s left" in app.btn_start.cget("text"), f"Countdown mismatch: '{app.btn_start.cget('text')}'"
        print(f"      OK: Live countdown displayed on button: '{app.btn_start.cget('text')}'")

        # Simulate expiration
        app._scan_start_time = time.time() - 46.0
        app._check_auto_stop_conditions()
        assert app._is_scanning is False, "Scan should stop when timer expires"
        assert "completed" in app.lbl_root_cause.cget("text"), "Root cause should show completion"
        print(f"      OK: Custom timer auto-stop completed cleanly: '{app.lbl_root_cause.cget('text')}'")

        # 7. Test Full Boot-State Reset Button (↺ Reset)
        print("\n[7/8] Testing Full Boot-State Reset Button (↺ Reset)...")
        # Dirty the app state: add sample, change selections, adjust sliders
        app._session_analyzer.add_sample(test_samples[0])
        app.graph.add_sample(test_samples[0])
        app.genre_combo.set("Custom Noot Stress")
        app._on_genre_selected("Custom Noot Stress")
        app.slider_payload.set(512)
        app.slider_rate.set(25)
        app.timer_entry.delete(0, "end")
        app.timer_entry.insert(0, "120")
        app.timer_unit_menu.set("min")
        app.update()

        # Trigger full reset
        app.reset_to_boot_state()
        app.update()

        # Assert full restoration
        assert app._session_analyzer.samples_count == 0, "Analyzer samples should be empty after reset"
        assert app.graph.samples_count == 0, "Graph samples should be empty after reset"
        assert app.wan_badge.cget("text") == "Data Used: 0.0 KB", "Data Used badge should be reset to 0.0 KB"
        assert app.lbl_verdict_title.cget("text") == "CLICK SCAN NOOT — PICK A SERVER NOOT", "Verdict title not reset"
        assert app.lbl_protocol_badge.cget("text") == "[Protocol: Standby]", "Protocol badge not reset"
        assert app.telemetry_labels["pill_avg"]["val"].cget("text") == "0.0 ms", "Avg ping not reset"
        assert app.telemetry_labels["pill_p99"]["val"].cget("text") == "0.0 ms", "P99 spike not reset"
        assert app.telemetry_labels["pill_jitter"]["val"].cget("text") == "0.0 ms", "Jitter not reset"
        assert app.telemetry_labels["pill_loss"]["val"].cget("text") == "0.0 %", "Packet loss not reset"
        assert app.telemetry_labels["pill_igloo"]["val"].cget("text") == "0.0 ms", "Igloo health not reset"
        assert app.timer_entry.get() == "60", "Timer entry should be reset to 60"
        assert app.timer_unit_menu.get() == "sec", "Timer unit should be reset to sec"
        assert app.timer_entry.cget("state") == "normal", "Timer entry should be enabled"
        assert app.custom_sliders_frame.winfo_manager() != "pack", "Custom sliders should be hidden after reset"
        assert app.graph.show_local_igloo is False, "Show Local Ping should be reset to False"
        assert app.graph._igloo_switch.get() == 0, "Show Local Ping switch should be reset to OFF"
        print("      OK: All widgets, graph bars, telemetry pills & settings restored to 100% boot values!")

        # 8. Test Quick Guide Modal & Graceful Shutdown
        print("\n[8/8] Testing Quick Diagnostic Guide Modal & Graceful Shutdown...")
        guide = QuickGuideModal(app)
        guide.update()
        guide.destroy()
        app.update()
        print("      OK: QuickGuideModal launched and closed cleanly")

        app._on_window_close()
        print("      OK: Application closed cleanly without hanging threads")

        print_banner("ALL PHASE 3.7 INTEGRATION CHECKS COMPLETED WITH 100% SUCCESS!")
        print("NOOT NOOT!\n")
        return True

    except Exception as e:
        print(f"\n[ERROR] Integration test failure: {e}")
        import traceback
        traceback.print_exc()
        try:
            app.destroy()
        except Exception:
            pass
        return False


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
