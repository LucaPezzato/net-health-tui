"""Network interfaces, local routing, Wi-Fi status, and public IP detection."""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NetworkInterface:
    name: str
    status: str
    mac: str = ""
    ipv4: list[str] = field(default_factory=list)
    ipv6: list[str] = field(default_factory=list)
    mtu: int = 1500
    is_up: bool = False
    is_wifi: bool = False
    is_default: bool = False
    flags: list[str] = field(default_factory=list)


@dataclass
class WifiDetails:
    ssid: str = ""
    bssid: str = ""
    signal_percent: int = 0
    frequency: str = ""
    rate: str = ""
    security: str = ""


@dataclass
class PublicInfo:
    ip: str = "Unavailable"
    isp: str = "Unknown"
    city: str = ""
    country: str = ""
    asn: str = ""
    colo: str = ""


@dataclass
class NetworkSummary:
    default_iface: str = ""
    gateway: str = ""
    dns_servers: list[str] = field(default_factory=list)
    primary_ip: str = ""
    primary_mac: str = ""
    wifi: WifiDetails | None = None
    public: PublicInfo | None = None
    interfaces: list[NetworkInterface] = field(default_factory=list)


def get_default_route() -> tuple[str, str]:
    """Returns (gateway_ip, default_interface_name)."""
    try:
        res = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2)
        match = re.search(r"default via ([\d\.]+) dev (\S+)", res.stdout)
        if match:
            return match.group(1), match.group(2)
    except Exception:
        pass
    return "", ""


def get_dns_servers() -> list[str]:
    """Reads configured DNS nameservers from /etc/resolv.conf."""
    servers: list[str] = []
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split()
                if parts and parts[0] == "nameserver" and len(parts) > 1:
                    servers.append(parts[1])
    except Exception:
        pass
    return servers


def get_wifi_details() -> WifiDetails | None:
    """Attempts to query NetworkManager (nmcli) for the currently active Wi-Fi connection."""
    try:
        res = subprocess.run(
            ["nmcli", "-t", "-f", "active,ssid,bssid,signal,freq,rate,security", "dev", "wifi"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if res.returncode == 0:
            for raw_line in res.stdout.splitlines():
                clean_line = raw_line.replace(r"\:", "__COLON__")
                parts = clean_line.split(":")
                if parts and parts[0] == "yes" and len(parts) >= 7:
                    ssid = parts[1]
                    bssid = parts[2].replace("__COLON__", ":")
                    signal_str = parts[3]
                    freq = parts[4]
                    rate = parts[5]
                    sec = parts[6]
                    try:
                        sig = int(signal_str)
                    except ValueError:
                        sig = 0
                    return WifiDetails(
                        ssid=ssid,
                        bssid=bssid,
                        signal_percent=sig,
                        frequency=freq,
                        rate=rate,
                        security=sec,
                    )
    except Exception:
        pass
    return None


def get_interfaces(default_iface: str = "") -> list[NetworkInterface]:
    """Returns a list of all network interfaces parsed from `ip -j addr`."""
    interfaces: list[NetworkInterface] = []
    try:
        res = subprocess.run(["ip", "-j", "addr"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            for item in data:
                ifname = item.get("ifname", "")
                operstate = item.get("operstate", "UNKNOWN").upper()
                mac = item.get("address", "")
                mtu = item.get("mtu", 1500)
                flags = item.get("flags", [])
                is_up = ("UP" in flags) or (operstate == "UP")
                is_wifi = ifname.startswith("wl") or "wlan" in ifname
                is_def = (ifname == default_iface)

                ipv4_list: list[str] = []
                ipv6_list: list[str] = []
                for a in item.get("addr_info", []):
                    local = a.get("local", "")
                    plen = a.get("prefixlen", "")
                    cidr = f"{local}/{plen}" if plen else local
                    if a.get("family") == "inet":
                        ipv4_list.append(cidr)
                    elif a.get("family") == "inet6":
                        ipv6_list.append(cidr)

                interfaces.append(
                    NetworkInterface(
                        name=ifname,
                        status=operstate,
                        mac=mac,
                        ipv4=ipv4_list,
                        ipv6=ipv6_list,
                        mtu=mtu,
                        is_up=is_up,
                        is_wifi=is_wifi,
                        is_default=is_def,
                        flags=flags,
                    )
                )
    except Exception:
        pass
    return interfaces


def get_public_ip_info() -> PublicInfo:
    """Fetches public IP, ISP, location, and ASN."""
    pub = PublicInfo()
    # 1. Try ip-api.com
    try:
        req = urllib.request.Request(
            "http://ip-api.com/json",
            headers={"User-Agent": "net-health-tui/0.1.0"},
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                pub.ip = data.get("query", "Unavailable")
                pub.isp = data.get("isp", "Unknown")
                pub.city = data.get("city", "")
                pub.country = data.get("country", "")
                pub.asn = data.get("as", "")
                return pub
    except Exception:
        pass

    # 2. Fallback to Cloudflare trace
    try:
        req = urllib.request.Request(
            "https://1.1.1.1/cdn-cgi/trace",
            headers={"User-Agent": "curl/8.0"},
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            text = resp.read().decode("utf-8")
            for line in text.splitlines():
                if line.startswith("ip="):
                    pub.ip = line[3:]
                elif line.startswith("loc="):
                    pub.country = line[4:]
                elif line.startswith("colo="):
                    pub.colo = line[5:]
    except Exception:
        pass

    return pub


def get_network_summary(fetch_public: bool = True) -> NetworkSummary:
    """Builds a comprehensive snapshot of local and WAN network health."""
    gw, def_iface = get_default_route()
    dns = get_dns_servers()
    ifaces = get_interfaces(default_iface=def_iface)
    wifi = get_wifi_details()
    public = get_public_ip_info() if fetch_public else None

    primary_ip = ""
    primary_mac = ""
    for ifc in ifaces:
        if ifc.is_default or ifc.name == def_iface:
            if ifc.ipv4:
                primary_ip = ifc.ipv4[0]
            primary_mac = ifc.mac
            break

    if not primary_ip:
        # Fallback to first non-loopback UP interface
        for ifc in ifaces:
            if ifc.name != "lo" and ifc.is_up and ifc.ipv4:
                primary_ip = ifc.ipv4[0]
                primary_mac = ifc.mac
                break

    return NetworkSummary(
        default_iface=def_iface,
        gateway=gw,
        dns_servers=dns,
        primary_ip=primary_ip,
        primary_mac=primary_mac,
        wifi=wifi,
        public=public,
        interfaces=ifaces,
    )
