"""Modern Truecolor Textual TUI for Network Health, Packet Loss, Speedtest and Interface Diagnostics."""

from __future__ import annotations

import time
from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, Static

from .artwork import DRACULA_PALETTE, render_retro_router
from .network import NetworkSummary, get_network_summary
from .ping_tester import PingResult, make_sparkline, ping_target
from .speedtest import CloudflareSpeedtest, SpeedtestProgress, SpeedtestResult


SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class NetHealthApp(App[None]):
    """Dracula-themed Network Health & Diagnostics TUI."""

    CSS = """
    Screen {
        background: #1e1f29;
        color: #f8f8f2;
        padding: 0 1;
    }

    #top-bar {
        height: 1;
        width: 100%;
        margin-top: 0;
        content-align: left middle;
    }

    #hero-card {
        height: 12;
        width: 100%;
        background: #282a36;
        border: round #bd93f9;
        padding: 0 1;
    }

    #artwork-box {
        width: 26;
        height: 10;
        margin-right: 2;
        content-align: center middle;
    }

    #hero-info-box {
        width: 1fr;
        height: 10;
        padding-top: 0;
    }

    #search-bar {
        dock: top;
        height: 3;
        margin: 0 0 1 0;
        background: #282a36;
        color: #f8f8f2;
        border: round #ff79c6;
        display: none;
    }

    #search-bar.visible {
        display: block;
    }

    #workspace-card {
        width: 100%;
        height: 1fr;
        background: #282a36;
        border: round #6272a4;
        padding: 0 1;
    }

    #content-view {
        width: 100%;
        height: 1fr;
    }

    #footer-bar {
        height: 1;
        width: 100%;
        content-align: center middle;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("escape", "dismiss_search_or_quit", "Back", show=False),
        Binding("1", "tab_overview", "Overview", show=False),
        Binding("2", "tab_loss", "Packet Loss", show=False),
        Binding("3", "tab_speed", "Speedtest", show=False),
        Binding("tab", "cycle_tab", "Next Tab", show=False),
        Binding("shift+tab", "prev_tab", "Prev Tab", show=False),
        Binding("r", "refresh_network", "Refresh", show=False),
        Binding("s", "run_speedtest", "Speedtest", show=False),
        Binding("p", "run_ping_check", "Ping Check", show=False),
        Binding("slash", "open_search", "Filter", show=False),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("enter", "activate_action", "Action", show=False),
    ]

    active_tab = reactive(0)  # 0: Overview/Interfaces, 1: Packet Loss, 2: Speedtest
    is_loading = reactive(False)
    flash_message = reactive("")
    spinner_idx = reactive(0)
    filter_query = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self.summary: NetworkSummary = NetworkSummary()
        self.ping_results: list[PingResult] = []
        self.speed_engine = CloudflareSpeedtest()
        self.speed_progress: SpeedtestProgress | None = None
        self.last_speed_result: SpeedtestResult | None = None
        self.custom_ping_target = ""
        self.selected_row = 0

    def compose(self) -> ComposeResult:
        yield Static(id="top-bar")
        with Horizontal(id="hero-card"):
            yield Static(id="artwork-box")
            yield Static(id="hero-info-box")
        yield Input(placeholder="Filtra interfacce o inserisci host da pingare (Invio)...", id="search-bar")
        with VerticalScroll(id="workspace-card"):
            yield Static(id="content-view")
        yield Static(id="footer-bar")

    def on_mount(self) -> None:
        self.set_interval(0.12, self._tick_spinner)
        self.set_interval(15.0, self._periodic_ping_refresh)
        self.flash_status("Caricamento configurazione di rete...")
        self.fetch_network_data()

    def _tick_spinner(self) -> None:
        if self.is_loading:
            self.spinner_idx = (self.spinner_idx + 1) % len(SPINNER_FRAMES)
            self._render_top_bar()

    def flash_status(self, msg: str) -> None:
        self.flash_message = msg
        self._render_footer()

    # ----------------------------------------------------
    # Data Fetching Workers
    # ----------------------------------------------------
    @work(thread=True, exclusive=True, group="network_refresh")
    def fetch_network_data(self) -> None:
        self.is_loading = True
        self.call_from_thread(self._render_top_bar)
        try:
            summary = get_network_summary(fetch_public=True)
            self.summary = summary

            # Run initial ping check
            self._execute_ping_checks(summary)

            self.call_from_thread(self.flash_status, "Informazioni di rete aggiornate con successo")
        except Exception as e:
            self.call_from_thread(self.flash_status, f"Errore scansione rete: {e}")
        finally:
            self.is_loading = False
            self.call_from_thread(self._render_all)

    def _execute_ping_checks(self, summary: NetworkSummary) -> None:
        targets = []
        if summary.gateway:
            targets.append((summary.gateway, f"Gateway Locale ({summary.gateway})"))
        targets.append(("1.1.1.1", "Cloudflare DNS (1.1.1.1)"))
        targets.append(("8.8.8.8", "Google DNS (8.8.8.8)"))
        targets.append(("9.9.9.9", "Quad9 Security (9.9.9.9)"))
        if self.custom_ping_target:
            targets.append((self.custom_ping_target, f"Custom Host ({self.custom_ping_target})"))

        results: list[PingResult] = []
        for host, label in targets:
            res = ping_target(host, label=label, count=5, interval=0.15)
            results.append(res)
        self.ping_results = results

    @work(thread=True, exclusive=True, group="ping_check")
    def action_run_ping_check(self) -> None:
        self.is_loading = True
        self.call_from_thread(self.flash_status, "Esecuzione test pacchetti persi e latenza...")
        self.call_from_thread(self._render_top_bar)
        try:
            self._execute_ping_checks(self.summary)
            self.call_from_thread(self.flash_status, "Test pacchetti persi completato")
        except Exception as e:
            self.call_from_thread(self.flash_status, f"Errore test ping: {e}")
        finally:
            self.is_loading = False
            self.call_from_thread(self._render_all)

    def _periodic_ping_refresh(self) -> None:
        if not self.is_loading and self.active_tab == 1:
            self.action_run_ping_check()

    @work(thread=True, exclusive=True, group="speedtest")
    def action_run_speedtest(self) -> None:
        self.is_loading = True
        self.active_tab = 2
        self.call_from_thread(self.flash_status, "Avvio Cloudflare Speedtest...")
        self.call_from_thread(self._render_all)

        def on_prog(prog: SpeedtestProgress) -> None:
            self.speed_progress = prog
            self.call_from_thread(self._render_workspace)

        try:
            res = self.speed_engine.run(progress_cb=on_prog)
            self.last_speed_result = res
            self.call_from_thread(
                self.flash_status,
                f"Speedtest: ↓ {res.download_mbps:.1f} Mbps  ↑ {res.upload_mbps:.1f} Mbps  Ping {res.latency_ms:.1f}ms",
            )
        except Exception as e:
            self.call_from_thread(self.flash_status, f"Errore durante lo speedtest: {e}")
        finally:
            self.is_loading = False
            self.speed_progress = None
            self.call_from_thread(self._render_all)

    # ----------------------------------------------------
    # UI Renderers
    # ----------------------------------------------------
    def _render_all(self) -> None:
        self._render_top_bar()
        self._render_hero()
        self._render_workspace()
        self._render_footer()

    def _render_top_bar(self) -> None:
        t = Text()
        spin = SPINNER_FRAMES[self.spinner_idx] if self.is_loading else "●"
        spin_style = "bold #50fa7b" if not self.is_loading else "bold #ff79c6"
        t.append(f" {spin} ", style=spin_style)
        t.append("net-health-tui", style="bold #bd93f9")
        t.append(" │ ", style="#6272a4")

        # Tabs
        tab_names = ["1 Interfacce", "2 Packet Loss & Ping", "3 Speedtest"]
        for idx, name in enumerate(tab_names):
            if idx == self.active_tab:
                t.append(f"[{name}] ", style="bold #ff79c6 underline")
            else:
                t.append(f" {name}  ", style="#6272a4")

        t.append("│ ", style="#6272a4")

        # Gateway badge
        gw = self.summary.gateway or "None"
        t.append(f"GW: {gw} ", style="#8be9fd")

        # Public IP badge
        if self.summary.public and self.summary.public.ip:
            t.append(f"│ WAN: {self.summary.public.ip} ", style="#50fa7b")

        self.query_one("#top-bar", Static).update(t)

    def _render_hero(self) -> None:
        # 1. Render Artwork Box
        wifi_sig = self.summary.wifi.signal_percent if self.summary.wifi else 0
        is_online = bool(self.summary.gateway)
        router_art = render_retro_router(wifi_percent=wifi_sig, is_online=is_online)
        self.query_one("#artwork-box", Static).update(router_art)

        # 2. Render Hero Info Box
        info = Text()
        info.append("Panoramica Connessione Attiva\n", style="bold #bd93f9")

        # Wi-Fi or Ethernet
        if self.summary.wifi and self.summary.wifi.ssid:
            w = self.summary.wifi
            info.append("  Rete Wi-Fi:   ", style="#6272a4")
            info.append(f"{w.ssid} ", style="bold #50fa7b")
            info.append(f"({w.signal_percent}% - {w.frequency} • {w.rate})\n", style="#8be9fd")
        elif self.summary.default_iface:
            info.append("  Interfaccia:  ", style="#6272a4")
            info.append(f"{self.summary.default_iface} (Ethernet/Cablata)\n", style="bold #50fa7b")
        else:
            info.append("  Stato Rete:   ", style="#6272a4")
            info.append("Disconnesso\n", style="bold #ff5555")

        # Local IP & MAC
        info.append("  IP Locale:    ", style="#6272a4")
        info.append(f"{self.summary.primary_ip or 'N/A'}", style="bold #f8f8f2")
        info.append("   MAC: ", style="#6272a4")
        info.append(f"{self.summary.primary_mac or 'N/A'}\n", style="#f1fa8c")

        # Gateway & DNS
        info.append("  Default GW:   ", style="#6272a4")
        info.append(f"{self.summary.gateway or 'N/A'}", style="#8be9fd")
        dns_str = ", ".join(self.summary.dns_servers[:2]) if self.summary.dns_servers else "N/A"
        info.append("   DNS: ", style="#6272a4")
        info.append(f"{dns_str}\n", style="#ffb86c")

        # Public IP & ISP
        info.append("  IP Pubblico:  ", style="#6272a4")
        pub = self.summary.public
        if pub and pub.ip != "Unavailable":
            info.append(f"{pub.ip}", style="bold #50fa7b")
            loc = f" ({pub.city}, {pub.country})" if pub.city else ""
            info.append(f" • {pub.isp}{loc}\n", style="#8be9fd")
        else:
            info.append("Non disponibile\n", style="#ff5555")

        # Health quick glance
        if self.ping_results:
            p_gw = self.ping_results[0]
            loss_style = "bold #50fa7b" if p_gw.packet_loss == 0 else "bold #ff5555"
            info.append("  Stato Rete:   ", style="#6272a4")
            info.append(f"Loss: {p_gw.packet_loss:.0f}%", style=loss_style)
            info.append(f"  •  Avg RTT: {p_gw.avg_rtt:.1f}ms  •  Jitter: {p_gw.jitter:.1f}ms", style="#f8f8f2")
            if self.last_speed_result:
                s = self.last_speed_result
                info.append(f"  •  Speed: ↓ {s.download_mbps:.1f} / ↑ {s.upload_mbps:.1f} Mbps", style="bold #ff79c6")

        self.query_one("#hero-info-box", Static).update(info)

    def _render_workspace(self) -> None:
        if self.active_tab == 0:
            content = self._render_interfaces_view()
        elif self.active_tab == 1:
            content = self._render_packet_loss_view()
        else:
            content = self._render_speedtest_view()

        self.query_one("#content-view", Static).update(content)

    def _render_interfaces_view(self) -> Table:
        table = Table(
            expand=True,
            box=None,
            header_style="bold #bd93f9",
            border_style="#6272a4",
            padding=(0, 1),
        )
        table.add_column("Stato", width=8)
        table.add_column("Interfaccia", width=14, style="bold #f8f8f2")
        table.add_column("Tipo", width=10)
        table.add_column("Indirizzo MAC", width=20, style="#f1fa8c")
        table.add_column("Indirizzo IPv4", width=20, style="#50fa7b")
        table.add_column("Indirizzo IPv6", width=28, style="#8be9fd")
        table.add_column("MTU", width=8, style="#6272a4")

        filtered = self.summary.interfaces
        if self.filter_query:
            q = self.filter_query.lower()
            filtered = [
                i for i in filtered
                if q in i.name.lower() or any(q in ip.lower() for ip in i.ipv4) or q in i.mac.lower()
            ]

        for idx, ifc in enumerate(filtered):
            # Highlight selected row
            is_sel = (idx == self.selected_row)
            row_style = "on #44475a" if is_sel else ""

            # State badge
            if ifc.is_up:
                state_txt = Text("● UP", style="bold #50fa7b")
            else:
                state_txt = Text("○ DOWN", style="#6272a4")

            # Interface label with badges
            iface_lbl = ifc.name
            if ifc.is_default:
                iface_lbl += " [GW]"

            # Type
            if ifc.name == "lo":
                itype = "Loopback"
            elif ifc.is_wifi:
                itype = "Wi-Fi"
            elif ifc.name.startswith("en") or ifc.name.startswith("eth"):
                itype = "Ethernet"
            elif "docker" in ifc.name or "br-" in ifc.name:
                itype = "Bridge"
            elif ifc.name.startswith("gpd") or "vpn" in ifc.name or "tun" in ifc.name:
                itype = "VPN/Tunnel"
            else:
                itype = "Virtual"

            v4_str = ifc.ipv4[0] if ifc.ipv4 else "—"
            v6_str = ifc.ipv6[0] if ifc.ipv6 else "—"
            mac_str = ifc.mac or "—"

            table.add_row(
                state_txt,
                iface_lbl,
                itype,
                mac_str,
                v4_str,
                v6_str,
                str(ifc.mtu),
                style=row_style,
            )

        return table

    def _render_packet_loss_view(self) -> Group:
        table = Table(
            expand=True,
            box=None,
            header_style="bold #bd93f9",
            border_style="#6272a4",
            padding=(0, 1),
        )
        table.add_column("Salute", width=12)
        table.add_column("Destinazione / Host", width=30, style="bold #f8f8f2")
        table.add_column("Loss %", width=10)
        table.add_column("Avg RTT", width=10, style="#50fa7b")
        table.add_column("Min/Max", width=16, style="#8be9fd")
        table.add_column("Jitter", width=10, style="#ffb86c")
        table.add_column("Latenze Recenti (Sparkline)", width=24)

        for res in self.ping_results:
            # Health badge style
            if res.status == "EXCELLENT":
                badge = Text("● ECCELLENTE", style="bold #50fa7b")
            elif res.status == "GOOD":
                badge = Text("● BUONO", style="#50fa7b")
            elif res.status == "FAIR":
                badge = Text("▲ DISCRETO", style="bold #f1fa8c")
            elif res.status == "POOR":
                badge = Text("✖ DEGRADATO", style="bold #ff5555")
            else:
                badge = Text("○ OFFLINE", style="#6272a4")

            # Loss style
            if res.packet_loss == 0.0:
                loss_txt = Text("0.0%", style="bold #50fa7b")
            elif res.packet_loss <= 2.0:
                loss_txt = Text(f"{res.packet_loss:.1f}%", style="#f1fa8c")
            else:
                loss_txt = Text(f"{res.packet_loss:.1f}%", style="bold #ff5555")

            min_max = f"{res.min_rtt:.1f} / {res.max_rtt:.1f} ms" if res.received > 0 else "—"
            avg_str = f"{res.avg_rtt:.1f} ms" if res.received > 0 else "—"
            jit_str = f"{res.jitter:.1f} ms" if res.received > 0 else "—"
            spark = make_sparkline(res.samples)

            table.add_row(
                badge,
                res.label,
                loss_txt,
                avg_str,
                min_max,
                jit_str,
                Text(spark, style="bold #ff79c6"),
            )

        instructions = Text()
        instructions.append("\n  [p]", style="bold #ff79c6")
        instructions.append(" Esegui nuovo test ping completo  │  ", style="#6272a4")
        instructions.append("[/]", style="bold #ff79c6")
        instructions.append(" Aggiungi target personalizzato  │  ", style="#6272a4")
        instructions.append("Intervallo auto-refresh: ", style="#6272a4")
        instructions.append("15s\n", style="#50fa7b")

        return Group(table, instructions)

    def _render_speedtest_view(self) -> Group:
        t = Text()
        t.append("⚡ Cloudflare Anycast Edge Speedtest\n", style="bold #bd93f9")
        t.append("Misurazione diretta della larghezza di banda reale tramite CDN edge Cloudflare.\n\n", style="#6272a4")

        # Current live progress or last result
        if self.speed_progress:
            prog = self.speed_progress
            t.append(f"  Fase attiva: ", style="#6272a4")
            t.append(f"{prog.status_text}\n", style="bold #ff79c6")

            # Visual progress bar
            pct = max(0, min(100, int(prog.progress_percent)))
            filled = pct // 2
            empty = 50 - filled
            t.append("  [", style="#bd93f9")
            t.append("━" * filled, style="bold #50fa7b")
            t.append("─" * empty, style="#44475a")
            t.append(f"]  {pct}%\n\n", style="bold #f8f8f2")

            if prog.current_mbps > 0:
                t.append("  Velocità istantanea: ", style="#6272a4")
                t.append(f"{prog.current_mbps:.2f} Mbps\n\n", style="bold #50fa7b")

        elif self.last_speed_result:
            s = self.last_speed_result
            t.append("  Ultimo risultato completato alle ", style="#6272a4")
            t.append(f"{s.timestamp}:\n\n", style="#f1fa8c")

            # Result cards / layout
            t.append("    ╔══════════════════════════════════════════════════════════════╗\n", style="#bd93f9")
            t.append("    ║  ", style="#bd93f9")
            t.append(f"DOWNLOAD: {s.download_mbps:>7.1f} Mbps", style="bold #50fa7b")
            t.append("   │   ", style="#6272a4")
            t.append(f"UPLOAD: {s.upload_mbps:>7.1f} Mbps", style="bold #ff79c6")
            t.append("   ║\n", style="#bd93f9")
            t.append("    ║  ", style="#bd93f9")
            t.append(f"LATENZA:  {s.latency_ms:>7.1f} ms  ", style="#8be9fd")
            t.append("   │   ", style="#6272a4")
            t.append(f"JITTER: {s.jitter_ms:>7.1f} ms  ", style="#ffb86c")
            t.append("   ║\n", style="#bd93f9")
            t.append("    ╚══════════════════════════════════════════════════════════════╝\n\n", style="#bd93f9")
        else:
            t.append("  Nessun test eseguito nella sessione corrente.\n", style="#6272a4")
            t.append("  Premi ", style="#6272a4")
            t.append("[s]", style="bold #ff79c6")
            t.append(" o ", style="#6272a4")
            t.append("[Invio]", style="bold #ff79c6")
            t.append(" per avviare il test di Download e Upload.\n\n", style="#6272a4")

        t.append("  [s / Invio]", style="bold #ff79c6")
        t.append(" Avvia Speedtest  │  ", style="#6272a4")
        t.append("[r]", style="bold #ff79c6")
        t.append(" Aggiorna panoramica  │  ", style="#6272a4")
        t.append("[q]", style="bold #ff79c6")
        t.append(" Esci", style="#6272a4")

        return Group(t)

    def _render_footer(self) -> None:
        t = Text()
        if self.flash_message:
            t.append(f" 󰋼 {self.flash_message} ", style="bold #f1fa8c")
        else:
            t.append(" [1-3] Schede  [p] Ping  [s] Speedtest  [r] Refresh  [/] Filtra/Host  [q] Esci ", style="#6272a4")
        self.query_one("#footer-bar", Static).update(t)

    # ----------------------------------------------------
    # Action Handlers
    # ----------------------------------------------------
    def action_tab_overview(self) -> None:
        self.active_tab = 0
        self._render_all()

    def action_tab_loss(self) -> None:
        self.active_tab = 1
        self._render_all()

    def action_tab_speed(self) -> None:
        self.active_tab = 2
        self._render_all()

    def action_cycle_tab(self) -> None:
        self.active_tab = (self.active_tab + 1) % 3
        self._render_all()

    def action_prev_tab(self) -> None:
        self.active_tab = (self.active_tab - 1) % 3
        self._render_all()

    def action_cursor_down(self) -> None:
        if self.active_tab == 0:
            count = len(self.summary.interfaces)
            if count > 0:
                self.selected_row = min(count - 1, self.selected_row + 1)
                self._render_workspace()

    def action_cursor_up(self) -> None:
        if self.active_tab == 0:
            self.selected_row = max(0, self.selected_row - 1)
            self._render_workspace()

    def action_refresh_network(self) -> None:
        self.flash_status("Aggiornamento dati di rete...")
        self.fetch_network_data()

    def action_open_search(self) -> None:
        search_box = self.query_one("#search-bar", Input)
        search_box.classes = "visible"
        search_box.focus()

    def action_dismiss_search_or_quit(self) -> None:
        search_box = self.query_one("#search-bar", Input)
        if "visible" in search_box.classes:
            search_box.classes = ""
            search_box.value = ""
            self.filter_query = ""
            self._render_workspace()
        else:
            self.exit()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-bar":
            self.filter_query = event.value
            self._render_workspace()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-bar":
            val = event.value.strip()
            if val and "." in val:
                # Custom host entered
                self.custom_ping_target = val
                self.flash_status(f"Target custom impostato: {val}")
                self.action_run_ping_check()
            event.input.classes = ""
            self._render_workspace()

    def action_activate_action(self) -> None:
        if self.active_tab == 2:
            self.action_run_speedtest()
        elif self.active_tab == 1:
            self.action_run_ping_check()


def run_tui() -> None:
    app = NetHealthApp()
    app.run()
