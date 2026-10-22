"""Multi-target ping monitor, packet loss calculation, jitter, and sparklines."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Sequence


SPARKLINE_BARS = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


def make_sparkline(values: Sequence[float], max_val: float | None = None) -> str:
    """Generates an 8-level Unicode sparkline string from a sequence of latency numbers."""
    if not values:
        return "──────────"
    valid = [v for v in values if v >= 0]
    if not valid:
        return "··········"
    low = min(valid)
    high = max_val if max_val is not None else max(valid)
    rng = max(1.0, high - low)

    chars = []
    for v in values:
        if v < 0:
            chars.append("·")  # Dropped packet indicator
        else:
            idx = int(((v - low) / rng) * (len(SPARKLINE_BARS) - 1))
            idx = max(0, min(len(SPARKLINE_BARS) - 1, idx))
            chars.append(SPARKLINE_BARS[idx])
    return "".join(chars)


@dataclass
class PingResult:
    target: str
    label: str
    transmitted: int = 0
    received: int = 0
    packet_loss: float = 0.0
    min_rtt: float = 0.0
    avg_rtt: float = 0.0
    max_rtt: float = 0.0
    jitter: float = 0.0
    samples: list[float] = field(default_factory=list)
    status: str = "PENDING"  # EXCELLENT, GOOD, FAIR, POOR, OFFLINE


def ping_target(host: str, label: str = "", count: int = 5, interval: float = 0.2, timeout_s: float = 2.0) -> PingResult:
    """Executes system `ping` and parses packets, loss %, min/avg/max/mdev and sample latencies."""
    lbl = label or host
    result = PingResult(target=host, label=lbl, transmitted=count)

    if not host:
        result.status = "OFFLINE"
        return result

    cmd = ["ping", "-c", str(count), "-i", str(interval), "-W", str(int(timeout_s)), host]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + (count * interval) + 1.0)
        output = proc.stdout

        # Extract individual RTT times
        times: list[float] = []
        for line in output.splitlines():
            m_time = re.search(r"time=([\d\.]+)\s*ms", line)
            if m_time:
                times.append(float(m_time.group(1)))

        # Parse summary: "X packets transmitted, Y received, Z% packet loss"
        m_stat = re.search(r"(\d+)\s+packets transmitted,\s+(\d+)\s+(?:packets\s+)?received.*?(\d+(?:\.\d+)?)%\s+packet loss", output)
        if m_stat:
            tx = int(m_stat.group(1))
            rx = int(m_stat.group(2))
            loss = float(m_stat.group(3))
            result.transmitted = tx
            result.received = rx
            result.packet_loss = loss

        # Parse rtt: "rtt min/avg/max/mdev = min/avg/max/mdev ms"
        m_rtt = re.search(r"rtt min/avg/max/mdev\s*=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)", output)
        if m_rtt:
            result.min_rtt = float(m_rtt.group(1))
            result.avg_rtt = float(m_rtt.group(2))
            result.max_rtt = float(m_rtt.group(3))
            result.jitter = float(m_rtt.group(4))

        result.samples = times

        # Evaluate Health Status
        if result.received == 0 or result.packet_loss >= 100.0:
            result.status = "OFFLINE"
        elif result.packet_loss > 5.0 or result.avg_rtt > 120.0:
            result.status = "POOR"
        elif result.packet_loss > 1.0 or result.avg_rtt > 75.0 or result.jitter > 15.0:
            result.status = "FAIR"
        elif result.avg_rtt <= 30.0 and result.jitter <= 6.0 and result.packet_loss == 0.0:
            result.status = "EXCELLENT"
        else:
            result.status = "GOOD"

    except Exception:
        result.status = "OFFLINE"

    return result
