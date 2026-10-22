"""Dracula theme palette, retro router artwork, and Unicode half-block visual graphics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.style import Style
from rich.text import Text


@dataclass(frozen=True)
class ThemePalette:
    name: str
    bg_main: str
    bg_panel: str
    bg_highlight: str
    primary: str      # #bd93f9
    secondary: str    # #ff79c6
    accent_green: str # #50fa7b
    accent_cyan: str  # #8be9fd
    accent_yellow: str# #f1fa8c
    accent_orange: str# #ffb86c
    alert_red: str    # #ff5555
    fg: str           # #f8f8f2
    fg_muted: str     # #6272a4


DRACULA_PALETTE = ThemePalette(
    name="Dracula NetHealth",
    bg_main="#1e1f29",
    bg_panel="#282a36",
    bg_highlight="#44475a",
    primary="#bd93f9",
    secondary="#ff79c6",
    accent_green="#50fa7b",
    accent_cyan="#8be9fd",
    accent_yellow="#f1fa8c",
    accent_orange="#ffb86c",
    alert_red="#ff5555",
    fg="#f8f8f2",
    fg_muted="#6272a4",
)


def render_retro_router(
    wifi_percent: int = 0,
    is_online: bool = True,
    download_mbps: float | None = None,
    palette: ThemePalette = DRACULA_PALETTE,
) -> Text:
    """Renders a stylized retro network router/antenna card in Dracula colors."""
    t = Text()

    # Determine status colors
    c_p = palette.primary
    c_s = palette.secondary
    c_g = palette.accent_green if is_online else palette.alert_red
    c_c = palette.accent_cyan
    c_y = palette.accent_yellow
    c_m = palette.fg_muted

    # Signal bars
    if wifi_percent >= 80:
        sig_icon = "▂▄▆█"
        sig_style = palette.accent_green
    elif wifi_percent >= 50:
        sig_icon = "▂▄▆_"
        sig_style = palette.accent_cyan
    elif wifi_percent >= 25:
        sig_icon = "▂▄__"
        sig_style = palette.accent_yellow
    elif wifi_percent > 0:
        sig_icon = "▂___"
        sig_style = palette.accent_orange
    else:
        sig_icon = "ETH "
        sig_style = palette.accent_cyan

    # Line 1: Waves & Top Header
    t.append("   ((•))       ((•))\n", style=f"bold {c_s}")
    # Line 2: Antenna shafts
    t.append("     │   ┌───┐   │  \n", style=f"{c_p}")
    # Line 3: Top plate
    t.append(" ┌───┴───┤NET├───┴───┐\n", style=f"bold {c_p}")
    # Line 4: Router Faceplate with LEDs
    t.append(" │ ", style=f"{c_p}")
    t.append("●", style=f"bold {c_g}")
    t.append(" ", style=f"{c_p}")
    t.append("●", style=f"bold {c_c}")
    t.append(" ", style=f"{c_p}")
    t.append("●", style=f"bold {c_s}")
    t.append(" ", style=f"{c_p}")
    t.append("●", style=f"bold {c_y}")
    t.append("  ", style=f"{c_p}")
    t.append(sig_icon, style=f"bold {sig_style}")
    t.append(" │\n", style=f"{c_p}")

    # Line 5: Ports / Grille
    t.append(" │ ══ ══ ══ ══ ══ ══ │\n", style=f"{c_m}")
    # Line 6: Bottom chassis
    t.append(" └─┬───────────────┬─┘\n", style=f"{c_p}")
    t.append("   └───         ───┘  ", style=f"{c_m}")

    return t
