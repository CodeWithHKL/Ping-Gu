"""
Ping Gu - Dual-Hop Ping Engine, Protocol Fallback & WAN Data Tracker
Provides gateway auto-detection, concurrent dual-hop ping probes (Target + Local Gateway),
automatic ICMP-to-TCP fallback for game servers blocking ICMP, and precise WAN bandwidth accounting.
"""

import concurrent.futures
from dataclasses import dataclass
import os
import re
import socket
import subprocess
import threading
import time
from typing import Callable, Optional

import icmplib
import requests


# ============================================================================
# 1. STRUCTURED PACKET DATA
# ============================================================================
@dataclass
class PingSample:
    """Represents a single dual-hop network latency sample."""
    seq_id: int
    timestamp: float
    target_host: str
    server_rtt_ms: Optional[float]
    local_rtt_ms: Optional[float]
    is_timeout: bool
    protocol_used: str  # "ICMP", "TCP", or "ICMP+TCP"
    payload_bytes: int
    wan_bytes_this_sample: int
    under_load_test: bool
    diagnosis_tag: str = "PENDING"
    diagnosis_detail: str = ""


# ============================================================================
# 2. DEFAULT GATEWAY AUTO-DETECTION
# ============================================================================
def get_default_gateway_ip() -> Optional[str]:
    """
    Reliably detects the user's default IPv4 gateway (Your Igloo Router).
    Uses 'route print 0.0.0.0' or 'ipconfig' with CREATE_NO_WINDOW
    to prevent console flash when compiled into a single .exe.
    """
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    # Primary method: route print 0.0.0.0
    try:
        output = subprocess.check_output(
            ["route", "print", "0.0.0.0"],
            text=True,
            creationflags=flags,
            timeout=3.0
        )
        # Look for 0.0.0.0 destination line
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("0.0.0.0"):
                parts = line.split()
                # Table columns: Network Destination, Netmask, Gateway, Interface, Metric
                if len(parts) >= 3:
                    gw_candidate = parts[2]
                    # Verify it's a valid IPv4 address and not On-link
                    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", gw_candidate):
                        if gw_candidate != "0.0.0.0" and not gw_candidate.startswith("127."):
                            return gw_candidate
    except Exception:
        pass

    # Fallback method: ipconfig
    try:
        output = subprocess.check_output(
            ["ipconfig"],
            text=True,
            creationflags=flags,
            timeout=3.0
        )
        matches = re.findall(r"Default Gateway[ .:]+: ([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", output)
        for candidate in matches:
            if candidate != "0.0.0.0" and not candidate.startswith("127."):
                return candidate
    except Exception:
        pass

    return None


# ============================================================================
# 3. LOW-LEVEL PROBE FUNCTIONS
# ============================================================================
def probe_icmp(host: str, payload_bytes: int = 32, timeout: float = 1.0) -> Optional[float]:
    """
    Executes a single ICMP ping probe using icmplib.
    First tries unprivileged socket (works without admin on Windows),
    falls back to privileged if required.
    Returns latency in milliseconds, or None if packet dropped or timed out.
    """
    try:
        # Standard unprivileged attempt
        res = icmplib.ping(
            host,
            count=1,
            timeout=timeout,
            payload_size=payload_bytes,
            privileged=False
        )
        if res.is_alive and res.rtts:
            return round(res.avg_rtt, 2)
        return None
    except Exception:
        # Fallback attempt with privileged=True if socket permission requires it
        try:
            res = icmplib.ping(
                host,
                count=1,
                timeout=timeout,
                payload_size=payload_bytes,
                privileged=True
            )
            if res.is_alive and res.rtts:
                return round(res.avg_rtt, 2)
            return None
        except Exception:
            return None


def probe_tcp_handshake(host: str, port: int = 443, timeout: float = 1.0) -> Optional[float]:
    """
    High-precision TCP SYN-ACK Handshake latency probe.
    Measures TCP 3-way connection setup time using time.perf_counter().
    Used as an automatic fallback when game servers drop ICMP packets.
    Returns latency in milliseconds, or None if connection failed.
    """
    t0 = time.perf_counter()
    s = None
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        rtt_ms = (time.perf_counter() - t0) * 1000.0
        try:
            s.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        return round(rtt_ms, 2)
    except Exception:
        return None
    finally:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass


def probe_local_gateway(gateway_ip: str, timeout: float = 0.3) -> Optional[float]:
    """
    Lightweight, rate-limit-resistant probe for the local default gateway (Igloo Router).
    Strictly uses 32-byte ICMP to prevent router flood triggering.
    If ICMP times out or is dropped by router security policy, immediately falls back
    to a quick TCP connect timing probe on gateway ports (80, 443, 53) so local
    Wi-Fi/LAN latency is accurately measured even on routers dropping ICMP.
    """
    try:
        icmp_rtt = probe_icmp(gateway_ip, payload_bytes=32, timeout=timeout)
        if icmp_rtt is not None:
            return icmp_rtt
    except Exception:
        pass

    # Quick TCP fallback for router management / DNS ports
    for port in (80, 443, 53):
        try:
            tcp_rtt = probe_tcp_handshake(gateway_ip, port=port, timeout=0.15)
            if tcp_rtt is not None:
                return tcp_rtt
        except Exception:
            continue
    return None


# ============================================================================
# 4. DUAL-HOP SCANNER ENGINE
# ============================================================================
class DualHopScanner:
    """
    Dual-Hop Ping Engine that coordinates concurrent probes against
    both the game/target server and the local igloo router.
    Handles ICMP -> TCP automatic fallback and live WAN data tracking.
    """

    def __init__(
        self,
        target_host: str,
        target_port: int = 443,
        payload_bytes: int = 32,
        pings_per_sec: int = 1,
        gateway_ip: Optional[str] = None
    ):
        self.target_host = target_host
        self.target_port = target_port
        self.payload_bytes = payload_bytes
        self.pings_per_sec = max(1, pings_per_sec)
        self.gateway_ip = gateway_ip or get_default_gateway_ip()

        # Local gateway rate-limiting protection (max 4Hz / 250ms)
        self._last_local_probe_time: float = 0.0
        self._last_local_rtt_ms: Optional[float] = None
        self._local_lock = threading.Lock()

        # Protocol state: "AUTO", "ICMP", or "TCP"
        self.protocol_mode = "AUTO"
        self.custom_payload_supported = True

        # Threading & control
        self._is_running = False
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # Counters & WAN tracking
        self.seq_id = 0
        self._total_wan_bytes = 0
        self._wan_lock = threading.Lock()

        # Bufferbloat stress state
        self._under_load_active = False
        self._bufferbloat_thread: Optional[threading.Thread] = None

    @property
    def total_wan_bytes(self) -> int:
        """Thread-safe getter for total WAN bytes used."""
        with self._wan_lock:
            return self._total_wan_bytes

    def add_wan_bytes(self, n_bytes: int) -> None:
        """Thread-safe addition to WAN bandwidth counter."""
        with self._wan_lock:
            self._total_wan_bytes += n_bytes

    def trigger_bufferbloat_burst(self, duration_sec: float = 5.0) -> None:
        """
        Thread-safe method that streams a download burst from Cloudflare's
        speed testing endpoint for duration_sec seconds while pings continue.
        Downloaded bytes are added directly to the live WAN counter, and
        concurrent PingSamples have under_load_test set to True.
        """
        def _burst_worker():
            self._under_load_active = True
            t_end = time.time() + duration_sec
            url = "https://speed.cloudflare.com/__down?bytes=10000000"
            headers = {"User-Agent": "PingGu-NetworkMonitor/1.0"}
            try:
                while time.time() < t_end and not self._stop_event.is_set():
                    try:
                        with requests.get(url, headers=headers, stream=True, timeout=3.0) as resp:
                            if resp.status_code == 200:
                                for chunk in resp.iter_content(chunk_size=65536):
                                    if chunk:
                                        self.add_wan_bytes(len(chunk))
                                    if time.time() >= t_end or self._stop_event.is_set():
                                        break
                            elif resp.status_code == 403:
                                # Fallback endpoint if Cloudflare rate limits
                                fallback_url = "https://proof.ovh.net/files/10Mb.dat"
                                with requests.get(fallback_url, stream=True, timeout=3.0) as fb_resp:
                                    for chunk in fb_resp.iter_content(chunk_size=65536):
                                        if chunk:
                                            self.add_wan_bytes(len(chunk))
                                        if time.time() >= t_end or self._stop_event.is_set():
                                            break
                    except Exception:
                        time.sleep(0.1)
            finally:
                self._under_load_active = False

        self._bufferbloat_thread = threading.Thread(
            target=_burst_worker,
            daemon=True,
            name="BufferbloatBurstThread"
        )
        self._bufferbloat_thread.start()

    def probe_once(self) -> PingSample:
        """
        Performs a single concurrent dual-hop probe:
        Hop 1: Target Server (ICMP or TCP fallback)
        Hop 2: Local Gateway Router (ICMP)
        Calculates exact WAN bytes and returns a complete PingSample.
        """
        self.seq_id += 1
        current_seq = self.seq_id
        timestamp = time.time()
        is_under_load = self._under_load_active

        # Decide probe method for target host
        target_uses_tcp = (self.protocol_mode == "TCP")

        # Determine if local router needs a fresh probe or can reuse recent value (< 250ms / 4Hz)
        now_mono = time.monotonic()
        with self._local_lock:
            need_local_probe = (
                self.gateway_ip is not None
                and (now_mono - self._last_local_probe_time >= 0.25 or self._last_local_rtt_ms is None)
            )

        # Execute dual-hop concurrently using ThreadPoolExecutor(max_workers=2)
        def _probe_target():
            if target_uses_tcp:
                return probe_tcp_handshake(self.target_host, self.target_port, timeout=1.0)
            else:
                return probe_icmp(self.target_host, self.payload_bytes, timeout=1.0)

        def _probe_local():
            if not self.gateway_ip:
                return None
            return probe_local_gateway(self.gateway_ip, timeout=0.3)

        f_target = self._executor.submit(_probe_target)
        if need_local_probe:
            f_local = self._executor.submit(_probe_local)
        else:
            f_local = None

        server_rtt = f_target.result()
        if f_local is not None:
            local_rtt = f_local.result()
            with self._local_lock:
                self._last_local_probe_time = time.monotonic()
                if local_rtt is not None or self._last_local_rtt_ms is None:
                    self._last_local_rtt_ms = local_rtt
        else:
            with self._local_lock:
                local_rtt = self._last_local_rtt_ms

        # Fallback check on first probe or when AUTO mode is active
        if self.protocol_mode == "AUTO":
            if server_rtt is not None:
                # ICMP is supported and working
                self.protocol_mode = "ICMP"
                self.custom_payload_supported = True
            else:
                # ICMP timed out or failed. Test TCP Handshake fallback!
                tcp_rtt = probe_tcp_handshake(self.target_host, self.target_port, timeout=1.0)
                if tcp_rtt is not None:
                    # Switch cleanly to TCP mode
                    self.protocol_mode = "TCP"
                    self.custom_payload_supported = False
                    server_rtt = tcp_rtt
                    target_uses_tcp = True
                else:
                    # Both failed; default to ICMP
                    self.protocol_mode = "ICMP"
                    self.custom_payload_supported = True

        # Determine protocol tag string
        if target_uses_tcp:
            protocol_used = "ICMP+TCP" if local_rtt is not None else "TCP"
        else:
            protocol_used = "ICMP"

        is_timeout = (server_rtt is None)

        # WAN Data calculation (external traffic ONLY, local router traffic excluded)
        if target_uses_tcp:
            # TCP SYN-ACK handshake is approximately 180 bytes
            wan_bytes = 180 if not is_timeout else 60
        else:
            # ICMP: IP header (20B) + ICMP header (8B) + payload_bytes
            # Outgoing request + incoming reply if alive
            wan_bytes = (self.payload_bytes + 28) * 2 if not is_timeout else (self.payload_bytes + 28)

        self.add_wan_bytes(wan_bytes)

        sample = PingSample(
            seq_id=current_seq,
            timestamp=timestamp,
            target_host=self.target_host,
            server_rtt_ms=server_rtt,
            local_rtt_ms=local_rtt,
            is_timeout=is_timeout,
            protocol_used=protocol_used,
            payload_bytes=self.payload_bytes,
            wan_bytes_this_sample=wan_bytes,
            under_load_test=is_under_load
        )
        return sample

    def start(self, callback: Optional[Callable[[PingSample], None]] = None) -> None:
        """Starts background loop probing at pings_per_sec rate."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()

        def _loop():
            interval = 1.0 / self.pings_per_sec
            while not self._stop_event.is_set():
                t_start = time.perf_counter()
                try:
                    sample = self.probe_once()
                    if callback:
                        callback(sample)
                except Exception as e:
                    print(f"[scanner] Probe exception: {e}")

                elapsed = time.perf_counter() - t_start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        self._worker_thread = threading.Thread(
            target=_loop,
            daemon=True,
            name="DualHopScannerLoop"
        )
        self._worker_thread.start()

    def stop(self) -> None:
        """Stops the background probing loop gracefully."""
        self._stop_event.set()
        self._is_running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self._executor.shutdown(wait=False)
