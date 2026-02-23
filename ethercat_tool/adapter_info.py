"""Gather network adapter details for troubleshooting (MAC, link state, speed, etc.)."""

import os
import re
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class AdapterInfo:
    """Network adapter details for report. All fields best-effort; empty string if unavailable."""

    name: str  # interface name (e.g. en7, eth0)
    mac_address: str = ""
    link_state: str = ""  # e.g. "up", "down", "active", "inactive"
    link_speed: str = ""  # e.g. "1000 Mb/s", "100 Mb/s full-duplex"
    driver_or_type: str = ""  # driver (Linux) or device type (macOS)
    hardware_port: str = ""  # macOS: "Thunderbolt Ethernet", Linux: PCI path or empty
    mtu: str = ""
    ip_address: str = ""  # first IPv4 if present (helpful for context)

    def as_dict(self) -> dict[str, str]:
        """Return non-empty fields as dict for display."""
        out: dict[str, str] = {}
        if self.mac_address:
            out["MAC Address"] = self.mac_address
        if self.link_state:
            out["Link State"] = self.link_state
        if self.link_speed:
            out["Link Speed"] = self.link_speed
        if self.driver_or_type:
            out["Driver/Type"] = self.driver_or_type
        if self.hardware_port:
            out["Hardware Port"] = self.hardware_port
        if self.mtu:
            out["MTU"] = self.mtu
        if self.ip_address:
            out["IP Address"] = self.ip_address
        return out


def _run(cmd: list[str], timeout: float = 5.0) -> str:
    """Run command, return stdout or empty string on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _get_adapter_info_macos(ifname: str) -> AdapterInfo:
    """Gather adapter info on macOS via ifconfig and optionally networksetup."""
    info = AdapterInfo(name=ifname)
    out = _run(["ifconfig", ifname])
    if not out:
        return info

    # ether aa:bb:cc:dd:ee:ff
    m = re.search(r"ether\s+([0-9a-fA-F:]{17})", out)
    if m:
        info.mac_address = m.group(1).upper()

    # media: autoselect (1000baseT <full-duplex>) status: active
    # or: media: autoselect (none) status: inactive
    m = re.search(r"media:\s*(\S+(?:\s+\S+)*?)\s+status:\s*(\w+)", out)
    if m:
        media, status = m.group(1), m.group(2)
        info.link_state = "active" if status == "active" else status
        # Parse speed from media, e.g. "1000baseT <full-duplex>" -> "1000 Mb/s full-duplex"
        speed_m = re.search(r"(\d+)baseT(?:\s*<([^>]+)>)?", media)
        if speed_m:
            mb = speed_m.group(1)
            dup = speed_m.group(2) or ""
            info.link_speed = f"{mb} Mb/s {dup}".strip()
        elif "none" not in media:
            info.link_speed = media

    # mtu 1500
    m = re.search(r"mtu\s+(\d+)", out)
    if m:
        info.mtu = m.group(1)

    # inet 192.168.1.1
    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
    if m:
        info.ip_address = m.group(1)

    # Hardware port from networksetup (maps en7 -> "Thunderbolt Ethernet" etc.)
    ports_out = _run(["networksetup", "-listallhardwareports"])
    if ports_out:
        port_name = ""
        for line in ports_out.splitlines():
            line = line.strip()
            if line.startswith("Hardware Port:"):
                port_name = line.split(":", 1)[1].strip()
            elif line.startswith("Device:") and port_name:
                dev = line.split(":", 1)[1].strip()
                if dev == ifname:
                    info.hardware_port = port_name
                    break
                port_name = ""

    # Device type from system_profiler (slower, optional) - skip to avoid delay
    return info


def _get_adapter_info_linux(ifname: str) -> AdapterInfo:
    """Gather adapter info on Linux via ip and ethtool."""
    info = AdapterInfo(name=ifname)

    # ip link show eth0
    out = _run(["ip", "link", "show", ifname])
    if out:
        # link/ether aa:bb:cc:dd:ee:ff
        m = re.search(r"link/ether\s+([0-9a-fA-F:]{17})", out)
        if m:
            info.mac_address = m.group(1).upper()

        # state UP or DOWN
        m = re.search(r"state\s+(\w+)", out)
        if m:
            info.link_state = m.group(1).lower()

        # mtu 1500
        m = re.search(r"mtu\s+(\d+)", out)
        if m:
            info.mtu = m.group(1)

    # ethtool eth0 - for speed, duplex
    ethtool_out = _run(["ethtool", ifname])
    if ethtool_out:
        m = re.search(r"Speed:\s*(\S+)", ethtool_out)
        if m:
            info.link_speed = m.group(1)
        m = re.search(r"Duplex:\s*(\w+)", ethtool_out)
        if m and info.link_speed:
            info.link_speed = f"{info.link_speed} ({m.group(1).lower()}-duplex)"
        elif m:
            info.link_speed = m.group(1).lower() + "-duplex"

        m = re.search(r"Link detected:\s*(\w+)", ethtool_out)
        if m and not info.link_state:
            info.link_state = "up" if m.group(1).lower() == "yes" else "down"

        m = re.search(r"Driver:\s*(\S+)", ethtool_out)
        if m:
            info.driver_or_type = m.group(1)

    # Driver from /sys if ethtool not available
    if not info.driver_or_type:
        try:
            p = f"/sys/class/net/{ifname}/device/driver"
            driver_path = os.path.realpath(p)
            info.driver_or_type = os.path.basename(driver_path)
        except OSError:
            pass

    # IP from ip addr
    addr_out = _run(["ip", "-4", "addr", "show", ifname])
    if addr_out:
        m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", addr_out)
        if m:
            info.ip_address = m.group(1)

    return info


def get_adapter_info(ifname: str) -> AdapterInfo:
    """Gather adapter details for the given interface. Best-effort; missing fields are empty."""
    if sys.platform == "darwin":
        return _get_adapter_info_macos(ifname)
    if sys.platform.startswith("linux"):
        return _get_adapter_info_linux(ifname)
    # Windows: minimal - could add ipconfig / getmac parsing later
    return AdapterInfo(name=ifname)
