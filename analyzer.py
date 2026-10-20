"""
Ping Gu - The Noot-O-Meter Brain, Forensic Correlator & Data Estimator
Provides pre-flight WAN data estimation, per-packet forensic root cause tagging,
rolling window statistics (P99, jitter, packet loss), and the Noot-O-Meter Verdict.
"""

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, NamedTuple, Optional, Tuple

from presets import (
    STATUS_GREEN,
    STATUS_OVERCAP_PURPLE,
    STATUS_RED,
    STATUS_YELLOW,
)
from scanner import PingSample


# ============================================================================
# 1. PRE-FLIGHT DATA USAGE ESTIMATOR
# ============================================================================
class DataEstimate(NamedTuple):
    est_mb_per_min: float
    human_str: str
    needs_warning: bool


def estimate_data_usage(
    payload_bytes: int,
    pings_per_sec: int,
    include_bufferbloat: bool = False
) -> DataEstimate:
    """
    Calculates estimated WAN usage in MB per minute for a chosen profile.
    Returns:
      DataEstimate(est_mb_per_min, human_str, needs_warning)
    Warning is triggered if est_mb_per_min >= 1.5, payload_bytes >= 1000,
    pings_per_sec >= 25, or include_bufferbloat is True.
    """
    pings_per_min = pings_per_sec * 60
    # Standard ICMP ping: request + reply with IP (20B) + ICMP (8B) headers
    bytes_per_ping = (payload_bytes + 28) * 2
    ping_bytes_per_min = pings_per_min * bytes_per_ping

    # Bufferbloat stress test streams ~15MB Cloudflare chunk
    burst_bytes = 15_000_000 if include_bufferbloat else 0
    total_bytes_per_min = ping_bytes_per_min + burst_bytes

    est_mb = round(total_bytes_per_min / (1024 * 1024), 2)
    human_str = f"~{est_mb:.2f} MB / min"

    needs_warning = bool(
        est_mb >= 1.5
        or payload_bytes >= 1000
        or pings_per_sec >= 25
        or include_bufferbloat
    )

    return DataEstimate(
        est_mb_per_min=est_mb,
        human_str=human_str,
        needs_warning=needs_warning
    )


@dataclass
class SessionPlanEvaluation:
    is_valid: bool
    error_message: str
    is_unwise: bool
    warning_title: str
    warning_message: str
    duration_sec: Optional[float]
    total_packets: Optional[int]
    projected_wan_mb: Optional[float]


def evaluate_session_plan(
    timer_val_str: str = "",
    timer_unit: str = "sec",  # "sec", "min", or "Continuous ∞"
    profile_name: str = "Tactical Shooter (CS2 / Valorant)",
    payload_bytes: int = 64,
    pings_per_sec: int = 5,
    *,
    mode: Optional[str] = None,
    duration_input: Optional[str] = None,
) -> SessionPlanEvaluation:
    """
    Validates custom timer inputs and computes session load projections.
    Returns SessionPlanEvaluation with validation results and smart unwise action warnings.
    """
    if mode is not None:
        timer_unit = mode
    if duration_input is not None:
        timer_val_str = duration_input
    # 1. Invalid Input Check
    if timer_unit in ("sec", "min"):
        try:
            val = float(timer_val_str.strip())
            if val <= 0:
                return SessionPlanEvaluation(
                    is_valid=False,
                    error_message="Timer duration must be a positive number greater than 0.",
                    is_unwise=False,
                    warning_title="",
                    warning_message="",
                    duration_sec=None,
                    total_packets=None,
                    projected_wan_mb=None
                )
            duration_sec = val if timer_unit == "sec" else val * 60.0
        except ValueError:
            return SessionPlanEvaluation(
                is_valid=False,
                error_message="Please enter a valid numeric value for the timer duration.",
                is_unwise=False,
                warning_title="",
                warning_message="",
                duration_sec=None,
                total_packets=None,
                projected_wan_mb=None
            )
    else:
        # "Continuous ∞"
        duration_sec = None

    # 2. Compute Projections
    if duration_sec is not None:
        total_packets = int(round(pings_per_sec * duration_sec))
    else:
        total_packets = None

    estimate = estimate_data_usage(payload_bytes, pings_per_sec, include_bufferbloat=False)
    est_mb_per_min = estimate.est_mb_per_min

    if duration_sec is not None:
        projected_wan_mb = round(est_mb_per_min * (duration_sec / 60.0), 2)
    else:
        projected_wan_mb = None

    # 3. Smart Unwise Resource / Duration Checks
    is_unwise = False
    warning_reasons = []

    # Criterion 1: Mode is "Continuous ∞" AND (pings_per_sec >= 10 OR payload_bytes >= 500)
    if duration_sec is None and (pings_per_sec >= 10 or payload_bytes >= 500):
        is_unwise = True
        warning_reasons.append(
            f"Running in Continuous ∞ mode at {pings_per_sec} pings/sec ({payload_bytes}B) "
            f"will generate ~{pings_per_sec * 60:,} packets/min indefinitely."
        )

    # Criterion 2: Custom timer duration > 300s on high-freq (>= 10Hz) or > 900s on any profile
    if duration_sec is not None:
        if pings_per_sec >= 10 and duration_sec > 300.0:
            is_unwise = True
            warning_reasons.append(
                f"Scan duration ({duration_sec:.0f}s / {duration_sec/60:.1f}min) exceeds 5 minutes "
                f"on a high-frequency profile ({pings_per_sec} Hz)."
            )
        elif duration_sec > 900.0:
            is_unwise = True
            warning_reasons.append(
                f"Scan duration ({duration_sec:.0f}s / {duration_sec/60:.1f}min) exceeds 15 minutes."
            )

    # Criterion 3: Total projected WAN data >= 5.0 MB OR est_mb_per_min >= 1.5 MB/min
    if (projected_wan_mb is not None and projected_wan_mb >= 5.0) or est_mb_per_min >= 1.5:
        is_unwise = True
        if projected_wan_mb is not None and projected_wan_mb >= 5.0:
            warning_reasons.append(f"Projected session bandwidth usage is ~{projected_wan_mb:.2f} MB (>= 5.0 MB).")
        else:
            warning_reasons.append(f"Projected bandwidth transfer rate is ~{est_mb_per_min:.2f} MB/min (>= 1.5 MB/min).")

    # Criterion 4: Total projected packets exceed 3,600 packets
    if total_packets is not None and total_packets > 3600:
        is_unwise = True
        warning_reasons.append(f"Session will fire {total_packets:,} packets (> 3,600 packets).")

    if is_unwise:
        warning_title = "⚠️ Unwise Settings / High-Resource Warning"
        if duration_sec is None:
            time_str = "indefinitely in Continuous mode"
            pkt_str = f"~{pings_per_sec * 60:,} packets per minute"
            data_str = f"~{est_mb_per_min:.2f} MB / min"
        else:
            time_str = f"for {duration_sec:.0f}s ({duration_sec/60:.1f} min)"
            pkt_str = f"{total_packets:,} packets"
            data_str = f"~{projected_wan_mb:.2f} MB of data"

        bullets = "\n".join(f"• {r}" for r in warning_reasons)
        warning_message = (
            f"Unwise Scan Warning: Running {profile_name} ({pings_per_sec} pings/sec @ {payload_bytes}B) "
            f"{time_str} will fire {pkt_str} and consume {data_str}.\n\n"
            f"Reasons for caution:\n{bullets}\n\n"
            f"This may saturate your network adapter, trigger router flood protection, "
            f"or consume mobile hotspot data.\n\n"
            f"Do you want to proceed anyway?"
        )
    else:
        warning_title = ""
        warning_message = ""

    return SessionPlanEvaluation(
        is_valid=True,
        error_message="",
        is_unwise=is_unwise,
        warning_title=warning_title,
        warning_message=warning_message,
        duration_sec=duration_sec,
        total_packets=total_packets,
        projected_wan_mb=projected_wan_mb
    )


# ============================================================================
# 2. BYTE FORMATTING HELPER
# ============================================================================
def format_wan_bytes(n_bytes: int) -> str:
    """Formats byte count into a clean human-readable string."""
    if n_bytes < 1024:
        return f"{n_bytes} B"
    elif n_bytes < 1024 * 1024:
        return f"{n_bytes / 1024:.1f} KB"
    elif n_bytes < 1024 * 1024 * 1024:
        return f"{n_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{n_bytes / (1024 * 1024 * 1024):.2f} GB"


# ============================================================================
# 3. PER-PACKET FORENSIC TAGGING
# ============================================================================
def analyze_sample(sample: PingSample, baseline_server_ms: float) -> Tuple[str, str]:
    """
    Evaluates a PingSample against the server baseline latency to diagnose
    the exact root cause of latency spikes or packet loss.
    Updates sample.diagnosis_tag and sample.diagnosis_detail in place.
    Returns: (diagnosis_tag, diagnosis_detail)
    """
    # 1. Packet Loss check
    if sample.is_timeout or sample.server_rtt_ms is None:
        tag = "PACKET_LOST"
        detail = "Packet lost in transit! Check if Local Igloo also dropped."

    # 2. Local Igloo / Router Wi-Fi Spike check
    # Local router latency above 15ms with concurrent server latency spike
    elif (
        sample.local_rtt_ms is not None
        and sample.local_rtt_ms > 15.0
        and sample.server_rtt_ms > max(baseline_server_ms * 1.25, baseline_server_ms + 15.0)
    ):
        tag = "LOCAL_IGLOO_SPIKE"
        detail = (
            f"Problem Inside Your Igloo! Local router spiked to {sample.local_rtt_ms:.1f}ms, "
            f"causing the server spike ({sample.server_rtt_ms:.1f}ms)."
        )

    # 3. Bufferbloat / Download Load Spike check
    elif (
        sample.under_load_test
        and sample.server_rtt_ms > (baseline_server_ms + 30.0)
    ):
        tag = "BUFFERBLOAT_SPIKE"
        detail = (
            f"Heavy Fish Load! Background download caused your ping to spike "
            f"to {sample.server_rtt_ms:.1f}ms (Bufferbloat)."
        )

    # 4. External ISP / Backbone / Datacenter Spike check
    elif sample.server_rtt_ms > max(baseline_server_ms * 1.6, baseline_server_ms + 25.0):
        local_str = f"{sample.local_rtt_ms:.1f}ms" if sample.local_rtt_ms is not None else "solid"
        tag = "ISP_BLIZZARD_SPIKE"
        detail = (
            f"Blizzard Outside! Your Igloo router was solid ({local_str}), "
            f"so this spike ({sample.server_rtt_ms:.1f}ms) happened on ISP/Server routing."
        )

    # 5. Normal Latency
    else:
        tag = "OK"
        detail = "Smooth sliding! Normal latency."

    sample.diagnosis_tag = tag
    sample.diagnosis_detail = detail
    return tag, detail


# ============================================================================
# 4. ROLLING WINDOW SESSION ANALYZER & NOOT-O-METER VERDICT
# ============================================================================
class SessionAnalyzer:
    """
    Maintains a rolling window of recent PingSamples (up to 500),
    computes live network metrics (P99, jitter, packet loss, WAN data),
    and generates the Noot-O-Meter Verdict Card.
    """

    def __init__(self, maxlen: int = 5000):
        self.samples: Deque[PingSample] = deque(maxlen=maxlen)
        self.total_wan_bytes = 0

    def reset(self) -> None:
        """Completely clears all samples and resets WAN byte counter to boot state."""
        self.samples.clear()
        self.total_wan_bytes = 0

    @property
    def samples_count(self) -> int:
        return len(self.samples)

    def add_sample(self, sample: PingSample) -> None:
        """
        Adds a sample, computes baseline, runs forensic tagging,
        and accumulates WAN bytes.
        """
        baseline = self.get_baseline_rtt()
        analyze_sample(sample, baseline)
        self.samples.append(sample)
        self.total_wan_bytes += sample.wan_bytes_this_sample

    def get_baseline_rtt(self) -> float:
        """
        Calculates a resilient baseline RTT using the 20th percentile
        of valid server pings (or min if < 5 samples).
        Defaults to 20.0ms if no valid pings recorded yet.
        """
        valid = [s.server_rtt_ms for s in self.samples if s.server_rtt_ms is not None]
        if not valid:
            return 20.0
        if len(valid) < 5:
            return min(valid)
        sorted_valid = sorted(valid)
        idx = int(0.20 * (len(sorted_valid) - 1))
        return sorted_valid[idx]

    def compute_metrics(self) -> Dict[str, Any]:
        """
        Computes rolling statistics and Noot-O-Meter verdict card:
        - current_ms, avg_ms, min_ms, max_ms, p99_ms
        - jitter_ms, loss_pct
        - total_wan_bytes, wan_data_str
        - verdict_title, verdict_color, root_cause_summary
        """
        total_count = len(self.samples)
        if total_count == 0:
            return {
                "sample_count": 0,
                "current_ms": None,
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p99_ms": 0.0,
                "jitter_ms": 0.0,
                "loss_pct": 0.0,
                "total_wan_bytes": 0,
                "wan_data_str": "0.0 KB",
                "verdict_title": "CLICK SCAN NOOT — PICK A SERVER NOOT",
                "verdict_color": STATUS_GREEN,
                "root_cause_summary": "Select your target datacenter and genre profile above, then click Start Noot Scan.",
            }

        valid_rtts = [s.server_rtt_ms for s in self.samples if s.server_rtt_ms is not None]
        timeouts = sum(1 for s in self.samples if s.is_timeout)

        # Basic latency metrics
        current_ms = self.samples[-1].server_rtt_ms
        if valid_rtts:
            avg_ms = round(sum(valid_rtts) / len(valid_rtts), 2)
            min_ms = round(min(valid_rtts), 2)
            max_ms = round(max(valid_rtts), 2)

            # P99 calculation
            sorted_rtts = sorted(valid_rtts)
            p99_idx = int(round(0.99 * (len(sorted_rtts) - 1)))
            p99_ms = round(sorted_rtts[p99_idx], 2)

            # Jitter: Mean absolute difference between consecutive valid samples
            if len(valid_rtts) > 1:
                diffs = [
                    abs(valid_rtts[i] - valid_rtts[i - 1])
                    for i in range(1, len(valid_rtts))
                ]
                jitter_ms = round(sum(diffs) / len(diffs), 2)
            else:
                jitter_ms = 0.0
        else:
            avg_ms = 0.0
            min_ms = 0.0
            max_ms = 0.0
            p99_ms = 0.0
            jitter_ms = 0.0

        loss_pct = round((timeouts / total_count) * 100.0, 1)
        wan_data_str = format_wan_bytes(self.total_wan_bytes)

        # Noot-O-Meter Verdict Determination
        # Strict gaming readiness criteria
        is_angry = (
            loss_pct >= 2.0
            or (valid_rtts and p99_ms >= 180.0)
            or (valid_rtts and avg_ms >= 130.0)
            or jitter_ms >= 15.0
            or (len(valid_rtts) == 0 and timeouts > 0)
        )
        is_suspicious = (
            (0.0 < loss_pct < 2.0)
            or (valid_rtts and p99_ms >= 100.0)
            or (valid_rtts and avg_ms >= 80.0)
            or (jitter_ms >= 6.0)
        )

        if is_angry:
            verdict_title = "ANGRY NOOT NOOT!! (Do Not Queue)"
            verdict_color = STATUS_RED
        elif is_suspicious:
            verdict_title = "SUSPICIOUS NOOT... (Casual Only)"
            verdict_color = STATUS_YELLOW
        else:
            verdict_title = "HAPPY NOOT! (Competitive Ready)"
            verdict_color = STATUS_GREEN

        # Root Cause Analysis based on verdict and recent sample tags
        recent_window = list(self.samples)[-100:]
        igloo_spikes = sum(1 for s in recent_window if s.diagnosis_tag == "LOCAL_IGLOO_SPIKE")
        bufferbloat_spikes = sum(1 for s in recent_window if s.diagnosis_tag == "BUFFERBLOAT_SPIKE")
        isp_spikes = sum(1 for s in recent_window if s.diagnosis_tag == "ISP_BLIZZARD_SPIKE")
        packet_drops = sum(1 for s in recent_window if s.diagnosis_tag == "PACKET_LOST")

        if is_angry:
            if packet_drops > 0 and loss_pct >= 2.0:
                root_cause = (
                    f"Critical Packet Loss ({loss_pct:.1f}%)! Multiple packets dropped in transit. "
                    "Check physical Ethernet cables or contact your ISP to inspect line noise."
                )
            elif igloo_spikes >= 2 or (igloo_spikes > 0 and igloo_spikes >= isp_spikes):
                root_cause = (
                    "Problem Inside Your Igloo! Severe local router/Wi-Fi latency spikes. "
                    "Switch to Ethernet or disconnect high-bandwidth LAN devices before playing."
                )
            elif bufferbloat_spikes >= 2:
                root_cause = (
                    "Heavy Fish Load! Background downloads caused your router queue to overflow (Bufferbloat). "
                    "Enable SQM / QoS on your router to prioritize gaming traffic."
                )
            elif isp_spikes >= 2 or isp_spikes > 0:
                root_cause = (
                    "Blizzard Outside! Your local Igloo router is solid, "
                    f"but severe latency spikes (P99: {p99_ms:.1f}ms) occurred across external ISP routing or game server hops."
                )
            elif jitter_ms >= 15.0:
                root_cause = (
                    f"Severe Micro-Jitter ({jitter_ms:.1f}ms)! Packet delivery is erratic, "
                    "causing micro-stutters and rubber-banding. Do not queue ranked games."
                )
            elif avg_ms >= 130.0:
                root_cause = (
                    f"High Latency ({avg_ms:.1f}ms)! Ping is too high for competitive responsiveness. "
                    "Select a closer server datacenter."
                )
            else:
                root_cause = (
                    f"Instability Warning! High latency spikes detected (P99: {p99_ms:.1f}ms). "
                    "Wait for network conditions to stabilize before queuing."
                )
        elif is_suspicious:
            if packet_drops > 0:
                root_cause = (
                    f"Minor packet drop detected ({loss_pct:.1f}%). Most packets arrived safely, "
                    "but monitor stability before joining competitive ranked matches."
                )
            elif igloo_spikes > 0:
                root_cause = (
                    "Slight Wi-Fi/Igloo congestion detected. Local latency blips seen on router. "
                    "Acceptable for casual gaming."
                )
            elif isp_spikes > 0:
                root_cause = (
                    f"Occasional external blips on ISP route (P99: {p99_ms:.1f}ms). "
                    "Acceptable for casual play, but expect occasional delay."
                )
            else:
                root_cause = (
                    f"Moderate latency ({avg_ms:.1f}ms) or micro-jitter ({jitter_ms:.1f}ms) detected. "
                    "Acceptable for casual play, but expect occasional delay in fast-paced shooters."
                )
        else:
            # HAPPY NOOT
            root_cause = (
                "Arctic Smooth! Both your local Igloo router and ISP routing are icy stable. "
                "Competitive queue ready. NOOT NOOT!"
            )

        return {
            "sample_count": total_count,
            "current_ms": current_ms,
            "avg_ms": avg_ms,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "p99_ms": p99_ms,
            "jitter_ms": jitter_ms,
            "loss_pct": loss_pct,
            "total_wan_bytes": self.total_wan_bytes,
            "wan_data_str": wan_data_str,
            "verdict_title": verdict_title,
            "verdict_color": verdict_color,
            "root_cause_summary": root_cause,
        }
