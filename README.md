<div align="center">

# 🌐 net-health-tui

**Dracula-themed Terminal User Interface for Network Health, Packet Loss, Speedtest and Interface Diagnostics**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-bd93f9.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Textual](https://img.shields.io/badge/TUI-Textual-ff79c6.svg?style=for-the-badge)](https://textual.textualize.io)
[![Wayland / Hyprland](https://img.shields.io/badge/Hyprland-Waybar-50fa7b.svg?style=for-the-badge&logo=wayland&logoColor=black)](https://hyprland.org)
[![Theme](https://img.shields.io/badge/Theme-Dracula-f1fa8c.svg?style=for-the-badge)](https://draculatheme.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-8be9fd.svg?style=for-the-badge)](LICENSE)

</div>

---

## ✨ Features

- 📊 **Panoramica Rete Completa (Scheda `[1]`)**:
  - Rilevamento in tempo reale di tutte le interfacce di rete (`wlp3s0`, `enp0s...`, `docker0`, VPN/tunnel, bridge).
  - Mostra stato **UP/DOWN**, indirizzo **MAC**, **IPv4**, **IPv6**, **MTU** e carrier.
  - Dettagli Wi-Fi attivi via NetworkManager: **SSID**, **BSSID**, **Frequenza** (2.4/5GHz), **Bitrate** e **% Segnale**.
  - Rilevamento automatico di **Default Gateway**, **Server DNS** e **IP Pubblico (WAN)** con ISP, Città e AS.
- 📉 **Monitor Packet Loss & Latenza con Sparklines (Scheda `[2]`)**:
  - Test multi-target parallelo: Gateway locale (router), Cloudflare DNS (`1.1.1.1`), Google DNS (`8.8.8.8`) e Quad9 (`9.9.9.9`).
  - Calcolo preciso di **% pacchetti persi**, **Jitter** (mdev), **RTT Min**, **Avg** e **Max**.
  - Grafico storico compatto a **Sparkline Unicode** (` ▂▃▄▅▆▇█`) con indicatore di pacchetti scartati (`·`).
  - Badge semantico dello stato di salute (`ECCELLENTE`, `BUONO`, `DISCRETO`, `DEGRADATO`, `OFFLINE`).
  - Supporto per **Host personalizzati** (`/` per inserire qualsiasi IP o dominio).
- ⚡ **Cloudflare Anycast Speedtest (Scheda `[3]`)**:
  - Benchmarking ad alta precisione tramite la rete edge Anycast globale di Cloudflare.
  - Test progressivo di **Download** e **Upload** con visualizzazione in tempo reale della velocità istantanea e barra di avanzamento.
  - Zero dipendenze esterne pesanti o account a pagamento: leggero, rapido e nativo.
- 🎨 **Palette Dracula Ufficiale & Artwork Retrò**:
  - Interfaccia con contrasto nitido (#1e1f29, #282a36, #bd93f9, #50fa7b).
  - Box visivo retrò con router ASCII, indicatori LED e stato antenna Wi-Fi.
- 📊 **Integrazione Waybar & Launcher Desktop**:
  - Sotto-comando `net-health-tui waybar` che emette payload JSON per widget Waybar con icone Nerd Font dinamiche e tooltip ricco.
  - File `.desktop` incluso per avvio rapido con Kitty (`SUPER+D` su Hyprland).

---

## ⌨️ Keybindings

| Tasto | Azione |
| :--- | :--- |
| `1` | Scheda **Panoramica & Interfacce** |
| `2` | Scheda **Packet Loss & Latenza** |
| `3` | Scheda **Cloudflare Speedtest** |
| `Tab` / `Shift+Tab` | Ciclo avanti / indietro tra le schede |
| `j` / `k` oppure `↓` / `↑` | Navigazione righe nella tabella interfacce |
| `p` | Esegui subito test pacchetti persi e latenza |
| `s` oppure `Enter` | Avvia **Speedtest** (in scheda 3) o riesegui test ping (in scheda 2) |
| `r` | Aggiorna forzatamente tutte le informazioni di rete e gateway |
| `/` | Filtra interfacce per nome/IP oppure imposta un **Host personalizzato** da pingare |
| `Esc` | Chiudi campo ricerca / cancella filtro |
| `q` | Esci dall'applicazione |

---

## 🚀 Utilizzo da Riga di Comando (Headless)

Il comando `net-health-tui` offre diversi sotto-comandi utili per terminale e scripting:

```bash
# Apri l'interfaccia interattiva TUI
net-health-tui

# Stampa un riassunto dettagliato della rete
net-health-tui info

# Esegui un ping con calcolo perdita pacchetti e jitter
net-health-tui ping 1.1.1.1 -c 5

# Esegui uno speedtest immediato
net-health-tui speedtest

# Genera JSON per Waybar
net-health-tui waybar
```

---

## 📊 Configurazione Waybar

Aggiungi il modulo al tuo `~/.config/waybar/config.jsonc`:

```jsonc
"custom/nethealth": {
    "exec": "net-health-tui waybar",
    "return-type": "json",
    "interval": 15,
    "on-click": "kitty --class net-health-tui -T 'Net Health TUI' net-health-tui",
    "on-click-right": "net-health-tui speedtest",
    "signal": 12
}
```

E aggiungi lo stile in `~/.config/waybar/style.css`:

```css
#custom-nethealth {
    background-color: #282a36;
    color: #f8f8f2;
    border-radius: 8px;
    padding: 0 10px;
    margin: 3px 4px;
}

#custom-nethealth.excellent {
    color: #50fa7b;
    border-bottom: 2px solid #50fa7b;
}

#custom-nethealth.fair {
    color: #f1fa8c;
    border-bottom: 2px solid #f1fa8c;
}

#custom-nethealth.poor, #custom-nethealth.offline {
    color: #ff5555;
    border-bottom: 2px solid #ff5555;
}
```

---

## 📦 Licenza

Rilasciato sotto licenza MIT.
