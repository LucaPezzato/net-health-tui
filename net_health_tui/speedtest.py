"""Lightweight, accurate Speedtest engine using Cloudflare's global Anycast edge CDN."""

from __future__ import annotations

import datetime
import statistics
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable


@dataclass
class SpeedtestProgress:
    phase: str = "idle"  # latency, download, upload, complete, error
    current_mbps: float = 0.0
    progress_percent: float = 0.0
    status_text: str = "Ready"


@dataclass
class SpeedtestResult:
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    server_edge: str = "Cloudflare Edge"
    client_ip: str = ""
    timestamp: str = ""


class CloudflareSpeedtest:
    """Performs low-latency, high-throughput network benchmarking."""

    def __init__(self) -> None:
        self._canceled = False

    def cancel(self) -> None:
        self._canceled = True

    def run(
        self,
        progress_cb: Callable[[SpeedtestProgress], None] | None = None,
    ) -> SpeedtestResult:
        self._canceled = False
        res = SpeedtestResult(timestamp=datetime.datetime.now().strftime("%H:%M:%S"))

        def report(phase: str, mbps: float, pct: float, msg: str) -> None:
            if progress_cb:
                progress_cb(SpeedtestProgress(phase=phase, current_mbps=mbps, progress_percent=pct, status_text=msg))

        # ----------------------------------------------------
        # 1. Latency & Jitter Check
        # ----------------------------------------------------
        report("latency", 0.0, 5.0, "Misurazione latenza verso edge Cloudflare...")
        latencies: list[float] = []
        for i in range(5):
            if self._canceled:
                return res
            try:
                t0 = time.perf_counter()
                req = urllib.request.Request(
                    "https://speed.cloudflare.com/__down?bytes=0",
                    headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"},
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    _ = resp.read()
                dt_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(dt_ms)
                pct = 5.0 + ((i + 1) / 5.0) * 15.0
                report("latency", 0.0, pct, f"Ping server edge: {dt_ms:.1f} ms ({i+1}/5)")
            except Exception:
                pass
            time.sleep(0.05)

        if latencies:
            res.latency_ms = statistics.median(latencies)
            if len(latencies) > 1:
                res.jitter_ms = statistics.stdev(latencies)

        # ----------------------------------------------------
        # 2. Download Speed Test
        # ----------------------------------------------------
        report("download", 0.0, 22.0, "Avvio test download...")
        download_sizes = [2_000_000, 6_000_000, 12_000_000, 25_000_000]
        total_dl_bytes = 0
        dl_start_time = time.perf_counter()
        rolling_speeds: list[float] = []

        total_target_bytes = sum(download_sizes)
        cum_bytes = 0

        for idx, sz in enumerate(download_sizes):
            if self._canceled:
                return res
            url = f"https://speed.cloudflare.com/__down?bytes={sz}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"},
            )
            try:
                chunk_t0 = time.perf_counter()
                chunk_bytes = 0
                with urllib.request.urlopen(req, timeout=10) as resp:
                    while True:
                        if self._canceled:
                            return res
                        buf = resp.read(65536)
                        if not buf:
                            break
                        n = len(buf)
                        chunk_bytes += n
                        cum_bytes += n
                        total_dl_bytes += n

                        now = time.perf_counter()
                        elapsed = now - dl_start_time
                        if elapsed > 0.05:
                            cur_mbps = (total_dl_bytes * 8) / (elapsed * 1_000_000)
                            progress_pct = 22.0 + (min(1.0, cum_bytes / total_target_bytes) * 38.0)
                            report("download", cur_mbps, progress_pct, f"Download in corso: {cur_mbps:.1f} Mbps")

                chunk_dt = time.perf_counter() - chunk_t0
                if chunk_dt > 0:
                    rolling_speeds.append((chunk_bytes * 8) / (chunk_dt * 1_000_000))
            except Exception as e:
                pass

        if rolling_speeds:
            # Use top speeds to discard connection ramp-up overhead
            top_speeds = sorted(rolling_speeds, reverse=True)[:max(1, len(rolling_speeds) // 2)]
            res.download_mbps = statistics.mean(top_speeds)
        elif total_dl_bytes > 0:
            total_dt = time.perf_counter() - dl_start_time
            res.download_mbps = (total_dl_bytes * 8) / (total_dt * 1_000_000)

        report("download", res.download_mbps, 60.0, f"Download completato: {res.download_mbps:.1f} Mbps")
        time.sleep(0.3)

        # ----------------------------------------------------
        # 3. Upload Speed Test
        # ----------------------------------------------------
        report("upload", 0.0, 62.0, "Avvio test upload...")
        upload_sizes = [1_000_000, 3_000_000, 6_000_000]
        total_up_bytes = 0
        up_start_time = time.perf_counter()
        up_rolling_speeds: list[float] = []

        total_up_target = sum(upload_sizes)
        cum_up_bytes = 0

        for idx, sz in enumerate(upload_sizes):
            if self._canceled:
                return res
            payload = b"X" * sz
            req = urllib.request.Request(
                "https://speed.cloudflare.com/__up",
                data=payload,
                method="POST",
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
                    "Origin": "https://speed.cloudflare.com",
                    "Referer": "https://speed.cloudflare.com/",
                },
            )
            try:
                t_up0 = time.perf_counter()
                with urllib.request.urlopen(req, timeout=12) as resp:
                    _ = resp.read()
                t_up1 = time.perf_counter()
                dt = t_up1 - t_up0
                cum_up_bytes += sz
                total_up_bytes += sz

                if dt > 0:
                    cur_mbps = (sz * 8) / (dt * 1_000_000)
                    up_rolling_speeds.append(cur_mbps)
                    progress_pct = 62.0 + (min(1.0, cum_up_bytes / total_up_target) * 36.0)
                    report("upload", cur_mbps, progress_pct, f"Upload in corso: {cur_mbps:.1f} Mbps")
            except Exception:
                pass

        if up_rolling_speeds:
            top_up = sorted(up_rolling_speeds, reverse=True)[:max(1, len(up_rolling_speeds) // 2)]
            res.upload_mbps = statistics.mean(top_up)
        elif total_up_bytes > 0:
            total_dt = time.perf_counter() - up_start_time
            res.upload_mbps = (total_up_bytes * 8) / (total_dt * 1_000_000)

        report("complete", 0.0, 100.0, "Speedtest completato con successo!")
        return res
