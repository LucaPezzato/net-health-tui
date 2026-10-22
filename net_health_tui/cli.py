"""CLI entrypoint for net-health-tui (interactive TUI, Waybar JSON widget, and headless diagnostics)."""

from __future__ import annotations

import argparse
import html
import json
import sys

from rich.console import Console
from rich.table import Table

from .network import get_network_summary
from .ping_tester import ping_target
from .speedtest import CloudflareSpeedtest
from .tui import run_tui


def output_waybar() -> None:
    """Emits JSON status for Waybar custom module."""
    try:
        summary = get_network_summary(fetch_public=False)
        gw = summary.gateway

        # Fast ping check to gateway or Cloudflare
        target = gw if gw else "1.1.1.1"
        res = ping_target(target, count=2, interval=0.1, timeout_s=1.0)

        # Icon selection
        if summary.wifi and summary.wifi.ssid:
            sig = summary.wifi.signal_percent
            if sig >= 75:
                icon = "󰤨"
            elif sig >= 50:
                icon = "󰤥"
            elif sig >= 25:
                icon = "󰤢"
            else:
                icon = "󰤟"
            net_name = summary.wifi.ssid
        elif summary.default_iface:
            icon = "󰈀"
            net_name = summary.default_iface
        else:
            icon = "󰤭"
            net_name = "Offline"

        if res.received == 0:
            css_class = "offline"
            label = f"{icon} Offline"
        elif res.packet_loss > 5.0 or res.avg_rtt > 120.0:
            css_class = "poor"
            label = f"{icon} {net_name} ({res.avg_rtt:.0f}ms • {res.packet_loss:.0f}% loss)"
        elif res.packet_loss > 0.0 or res.avg_rtt > 60.0:
            css_class = "fair"
            label = f"{icon} {net_name} ({res.avg_rtt:.0f}ms)"
        else:
            css_class = "excellent"
            label = f"{icon} {net_name} ({res.avg_rtt:.0f}ms)"

        tooltip_lines = [
            f"󰛳 Rete: {net_name}",
            f"󰩟 IP Locale: {summary.primary_ip or 'N/A'}",
            f"󰈀 Interfaccia: {summary.default_iface or 'N/A'}",
            f" Gateway: {summary.gateway or 'N/A'}",
            f"󰀂 Ping ({target}): {res.avg_rtt:.1f}ms (Loss: {res.packet_loss:.0f}%)",
            "─────────────────────────────",
            "Clicca per aprire net-health-tui",
        ]

        out = {
            "text": html.escape(label),
            "tooltip": "\n".join(tooltip_lines),
            "class": css_class,
        }
        print(json.dumps(out))
    except Exception as e:
        print(json.dumps({"text": "󰤭 Net Err", "tooltip": str(e), "class": "offline"}))


def cmd_info() -> None:
    """Prints a clean CLI overview of network interfaces and health."""
    console = Console()
    summary = get_network_summary(fetch_public=True)

    console.print("\n[bold #bd93f9]═══ net-health-tui • Panoramica Rete ═══[/bold #bd93f9]\n")
    if summary.wifi and summary.wifi.ssid:
        w = summary.wifi
        console.print(f"[bold #50fa7b]Wi-Fi:[/bold #50fa7b] {w.ssid} [dim]({w.signal_percent}% segnale, {w.frequency}, {w.rate})[/dim]")
    console.print(f"[bold #8be9fd]Interfaccia Predefinita:[/bold #8be9fd] {summary.default_iface} [dim](MAC: {summary.primary_mac})[/dim]")
    console.print(f"[bold #f8f8f2]IP Locale:[/bold #f8f8f2] {summary.primary_ip}")
    console.print(f"[bold #ffb86c]Gateway:[/bold #ffb86c] {summary.gateway}")
    console.print(f"[dim]DNS:[/dim] {', '.join(summary.dns_servers)}")

    if summary.public and summary.public.ip:
        p = summary.public
        console.print(f"[bold #50fa7b]IP Pubblico (WAN):[/bold #50fa7b] {p.ip} • [cyan]{p.isp}[/cyan] ({p.city}, {p.country})")

    table = Table(title="\nInterfacce Rilevate", border_style="#6272a4", header_style="bold #bd93f9")
    table.add_column("Nome")
    table.add_column("Stato")
    table.add_column("MAC")
    table.add_column("IPv4")
    table.add_column("MTU")

    for ifc in summary.interfaces:
        st = "[bold #50fa7b]UP[/bold #50fa7b]" if ifc.is_up else "[dim]DOWN[/dim]"
        v4 = ifc.ipv4[0] if ifc.ipv4 else "—"
        table.add_row(ifc.name, st, ifc.mac or "—", v4, str(ifc.mtu))

    console.print(table)


def cmd_ping(host: str = "1.1.1.1", count: int = 5) -> None:
    """Runs a standalone ping & packet loss diagnostic."""
    console = Console()
    console.print(f"[bold #bd93f9]Pinging {host} ({count} pacchetti)...[/bold #bd93f9]")
    res = ping_target(host, count=count)
    console.print(f"Trasferiti: {res.transmitted}, Ricevuti: {res.received}, [bold]Packet Loss: {res.packet_loss:.1f}%[/bold]")
    if res.received > 0:
        console.print(f"RTT: Min {res.min_rtt:.1f}ms, Avg {res.avg_rtt:.1f}ms, Max {res.max_rtt:.1f}ms, Jitter: {res.jitter:.1f}ms")
        console.print(f"Stato Salute: [bold #50fa7b]{res.status}[/bold #50fa7b]")


def cmd_speedtest() -> None:
    """Runs a standalone Cloudflare speedtest on CLI."""
    console = Console()
    engine = CloudflareSpeedtest()
    console.print("[bold #bd93f9]Avvio Cloudflare Anycast Speedtest...[/bold #bd93f9]")
    res = engine.run(progress_cb=lambda p: console.print(f"[dim]{p.status_text}[/dim]"))
    console.print("\n[bold #50fa7b]═══ Risultati Speedtest ═══[/bold #50fa7b]")
    console.print(f"  ↓ Download: [bold #50fa7b]{res.download_mbps:.1f} Mbps[/bold #50fa7b]")
    console.print(f"  ↑ Upload:   [bold #ff79c6]{res.upload_mbps:.1f} Mbps[/bold #ff79c6]")
    console.print(f"  • Latenza:  [bold #8be9fd]{res.latency_ms:.1f} ms[/bold #8be9fd] (Jitter: {res.jitter_ms:.1f} ms)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="net-health-tui",
        description="Terminal UI for Network Health, Packet Loss, Speedtest and Interface Diagnostics.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("tui", help="Open interactive Dracula TUI (default)")
    sub.add_parser("waybar", help="Output JSON status for Waybar custom module")
    sub.add_parser("info", help="Print detailed CLI network summary")

    p_ping = sub.add_parser("ping", help="Run packet loss and ping test")
    p_ping.add_argument("host", nargs="?", default="1.1.1.1", help="Target host (default: 1.1.1.1)")
    p_ping.add_argument("-c", "--count", type=int, default=5, help="Number of packets (default: 5)")

    sub.add_parser("speedtest", help="Run non-interactive speed test")

    args = parser.parse_args(argv)
    cmd = args.command or "tui"

    if cmd == "tui":
        run_tui()
        return 0
    elif cmd == "waybar":
        output_waybar()
        return 0
    elif cmd == "info":
        cmd_info()
        return 0
    elif cmd == "ping":
        cmd_ping(host=args.host, count=args.count)
        return 0
    elif cmd == "speedtest":
        cmd_speedtest()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
