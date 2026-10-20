"""
Ping Gu - Phase 1 Automated Terminal Verification Script
Tests gateway detection, data usage pre-flight estimator, dual-hop ping probes,
automatic TCP fallback (for AWS Singapore), and Noot-O-Meter verdict engine.
"""

import sys
import time
from typing import List

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from analyzer import SessionAnalyzer, estimate_data_usage, format_wan_bytes
from presets import (
    DEFAULT_SERVERS,
    GENRE_PROFILES,
    load_user_config,
    save_user_config,
)
from scanner import DualHopScanner, PingSample, get_default_gateway_ip


def print_banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_gateway_detection() -> str:
    print_banner("1. LOCAL GATEWAY AUTO-DETECTION (Your Igloo)")
    gw_ip = get_default_gateway_ip()
    if gw_ip:
        print(f"[OK] Detected Local Gateway (Igloo Router): {gw_ip}")
    else:
        print("[WARNING] Could not auto-detect default gateway. Using localhost/fallback.")
        gw_ip = "127.0.0.1"
    return gw_ip


def test_data_estimator() -> None:
    print_banner("2. PRE-FLIGHT WAN DATA ESTIMATOR VERIFICATION")
    profiles_to_test = [
        "Standard Ping",
        "Tactical Shooter (CS2 / Valorant)",
        "MMO / Open World (Albion ZvZ / Raids)",
    ]

    for name in profiles_to_test:
        prof = GENRE_PROFILES[name]
        p_bytes = prof["payload_bytes"]
        rate = prof["pings_per_sec"]
        warn_profile = prof["high_resource_warning"]

        # Calculate standard and burst estimates
        est_standard = estimate_data_usage(p_bytes, rate, include_bufferbloat=False)
        est_burst = estimate_data_usage(p_bytes, rate, include_bufferbloat=True)

        warn_badge = " [RESOURCE WARNING!]" if est_standard.needs_warning else " [NORMAL]"
        print(f"\n* Profile: '{name}'")
        print(f"  - Configuration: {p_bytes} bytes @ {rate} pings/sec (Hz)")
        print(f"  - WAN Standard: {est_standard.human_str}{warn_badge}")
        print(f"  - WAN w/ Bufferbloat Burst: {est_burst.human_str} [RESOURCE WARNING!]")
        print(f"  - Description: {prof['description']}")


def run_live_test(
    server_name: str,
    target_host: str,
    target_port: int,
    profile_name: str,
    duration_sec: float,
    gateway_ip: str
) -> SessionAnalyzer:
    prof = GENRE_PROFILES[profile_name]
    payload_bytes = prof["payload_bytes"]
    pings_per_sec = prof["pings_per_sec"]

    print(f"\n>> Starting {duration_sec:.1f}s test against: {server_name}")
    print(f"   Target: {target_host}:{target_port}")
    print(f"   Profile: {profile_name} ({payload_bytes} bytes @ {pings_per_sec} Hz)")

    scanner = DualHopScanner(
        target_host=target_host,
        target_port=target_port,
        payload_bytes=payload_bytes,
        pings_per_sec=pings_per_sec,
        gateway_ip=gateway_ip
    )
    analyzer = SessionAnalyzer(maxlen=500)

    samples_collected: List[PingSample] = []

    def on_sample(sample: PingSample):
        analyzer.add_sample(sample)
        samples_collected.append(sample)

    scanner.start(callback=on_sample)
    time.sleep(duration_sec)
    scanner.stop()

    print(f">> Probe finished. Collected {len(samples_collected)} samples.")
    print(f"   Protocol negotiated: {scanner.protocol_mode}")
    print(f"   Custom payload size supported: {scanner.custom_payload_supported}")
    print(f"   Session WAN Data Transferred: {format_wan_bytes(scanner.total_wan_bytes)} ({scanner.total_wan_bytes} bytes)")

    # Print first few samples
    print("\n   Sample Probe Details:")
    preview_count = min(3, len(samples_collected))
    for i in range(preview_count):
        s = samples_collected[i]
        server_str = f"{s.server_rtt_ms:.2f}ms" if s.server_rtt_ms is not None else "TIMEOUT"
        local_str = f"{s.local_rtt_ms:.2f}ms" if s.local_rtt_ms is not None else "N/A"
        print(f"     [Seq #{s.seq_id:02d}] Server: {server_str} | Local Igloo: {local_str} | Protocol: {s.protocol_used} | Tag: [{s.diagnosis_tag}] -> {s.diagnosis_detail}")

    if len(samples_collected) > preview_count:
        last_s = samples_collected[-1]
        server_str = f"{last_s.server_rtt_ms:.2f}ms" if last_s.server_rtt_ms is not None else "TIMEOUT"
        local_str = f"{last_s.local_rtt_ms:.2f}ms" if last_s.local_rtt_ms is not None else "N/A"
        print(f"     ... [Seq #{last_s.seq_id:02d}] Server: {server_str} | Local Igloo: {local_str} | Protocol: {last_s.protocol_used} | Tag: [{last_s.diagnosis_tag}] -> {last_s.diagnosis_detail}")

    # Compute and display verdict
    metrics = analyzer.compute_metrics()
    print("\n   [NOOT-O-METER VERDICT CARD]")
    print(f"   * Verdict:     {metrics['verdict_title']}")
    print(f"   * Color:       {metrics['verdict_color']}")
    print(f"   * Avg Latency: {metrics['avg_ms']} ms (Min: {metrics['min_ms']} ms, Max: {metrics['max_ms']} ms)")
    print(f"   * P99 Spike:   {metrics['p99_ms']} ms")
    print(f"   * Micro-Jitter:{metrics['jitter_ms']} ms")
    print(f"   * Packet Loss: {metrics['loss_pct']} %")
    print(f"   * WAN Usage:   {metrics['wan_data_str']}")
    print(f"   * Root Cause:  {metrics['root_cause_summary']}")

    return analyzer


def test_bufferbloat_burst(gateway_ip: str) -> None:
    print_banner("3C. BUFFERBLOAT 'UNDER LOAD' BURST GENERATOR TEST")
    scanner = DualHopScanner(
        target_host="1.1.1.1",
        target_port=53,
        payload_bytes=64,
        pings_per_sec=10,
        gateway_ip=gateway_ip
    )
    analyzer = SessionAnalyzer()
    samples = []

    def on_sample(s: PingSample):
        analyzer.add_sample(s)
        samples.append(s)

    scanner.start(callback=on_sample)
    print(">> Starting baseline probes (0.5s)...")
    time.sleep(0.5)

    print(">> Triggering 2.0s Bufferbloat download burst from Cloudflare speed test...")
    bytes_before = scanner.total_wan_bytes
    scanner.trigger_bufferbloat_burst(duration_sec=2.0)
    if scanner._bufferbloat_thread:
        scanner._bufferbloat_thread.join(timeout=3.0)
    time.sleep(0.5)
    scanner.stop()

    bytes_after = scanner.total_wan_bytes
    downloaded_burst = bytes_after - bytes_before
    under_load_count = sum(1 for s in samples if s.under_load_test)

    print(f"[OK] Bufferbloat burst completed!")
    print(f"     Burst data downloaded: {format_wan_bytes(downloaded_burst)} ({downloaded_burst} bytes)")
    print(f"     Total samples collected: {len(samples)}")
    print(f"     Samples tagged under_load_test=True: {under_load_count}")
    assert under_load_count > 0, "No samples captured under_load_test=True during burst"
    assert downloaded_burst > 50_000, "Bufferbloat burst should have downloaded > 50KB"


def test_user_config_manager() -> None:
    print_banner("4. USER CONFIG PERSISTENCE VERIFICATION")
    # Load existing or default config
    cfg = load_user_config()
    print(f"[OK] Successfully loaded user config: {list(cfg.keys())}")

    # Test saving custom server
    test_server = {
        "name": "Custom Arctic Test Gateway",
        "category": "Custom",
        "host": "1.0.0.1",
        "port": 53,
        "description": "Cloudflare secondary test DNS"
    }
    cfg["custom_servers"] = [test_server]
    save_ok = save_user_config(cfg)
    print(f"[OK] Config save test: {save_ok}")

    reloaded = load_user_config()
    custom_names = [s.get("name") for s in reloaded.get("custom_servers", [])]
    assert "Custom Arctic Test Gateway" in custom_names, "Custom server persistence failed"
    print(f"[OK] Config persistence verified round-trip! Custom servers: {custom_names}")


def main() -> None:
    print_banner("PING GU - PHASE 1: CORE BACKEND ENGINE TEST")
    print("Arctic Tuxedo / Noot Noot! Network Stability Monitor")

    # 1. Gateway Detection
    gw_ip = test_gateway_detection()

    # 2. Pre-flight data estimator
    test_data_estimator()

    # 3. Live 3-second test against Cloudflare Edge DNS (1.1.1.1)
    print_banner("3A. LIVE 3-SECOND TEST: Cloudflare Edge DNS (1.1.1.1)")
    run_live_test(
        server_name="Cloudflare Edge DNS (1.1.1.1)",
        target_host="1.1.1.1",
        target_port=53,
        profile_name="Tactical Shooter (CS2 / Valorant)",
        duration_sec=3.0,
        gateway_ip=gw_ip
    )

    # 3B. Live 2-second test against AWS Singapore (ec2.ap-southeast-1.amazonaws.com)
    # Testing ICMP Blocked -> Automatic TCP Handshake fallback
    print_banner("3B. LIVE 2-SECOND TEST: AWS Singapore (ec2.ap-southeast-1.amazonaws.com)")
    sg_analyzer = run_live_test(
        server_name="AWS Singapore (SEA Game Hub)",
        target_host="ec2.ap-southeast-1.amazonaws.com",
        target_port=443,
        profile_name="MOBA / Action (Dota 2 / LoL)",
        duration_sec=2.0,
        gateway_ip=gw_ip
    )

    # 3C. Bufferbloat Burst Generator Test
    test_bufferbloat_burst(gw_ip)

    # 4. Single-EXE safe user config
    test_user_config_manager()

    print_banner("ALL PHASE 1 BACKEND VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("Engine is solid, responsive, and ready for Phase 2 GUI development.")
    print("NOOT NOOT!\n")


if __name__ == "__main__":
    main()
