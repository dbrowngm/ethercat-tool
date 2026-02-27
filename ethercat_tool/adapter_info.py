"""Gather network adapter details for troubleshooting (MAC, link state, speed, etc.)."""

import os
import re
import subprocess
import sys
from dataclasses import dataclass

try:
    import pysoem
except ImportError:
    pysoem = None


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


def _get_adapter_desc_from_pysoem(ifname: str) -> str:
    """Get adapter description from pysoem/Npcap by matching adapter name."""
    if not pysoem:
        return ""
    try:
        for a in pysoem.find_adapters():
            if getattr(a, "name", "") == ifname:
                desc = getattr(a, "desc", "")
                if isinstance(desc, bytes):
                    return desc.decode("utf-8", errors="replace").strip()
                return str(desc).strip() if desc else ""
    except Exception:
        pass
    return ""


def _parse_ipconfig_adapters(ipconfig_out: str) -> list[dict[str, str]]:
    """Parse ipconfig /all into list of adapter dicts with mac, desc, media_state."""
    adapters: list[dict[str, str]] = []
    current: dict[str, str] = {}
    in_block = False

    for line in ipconfig_out.splitlines():
        # Section header: "Ethernet adapter Name:" or "Wireless LAN adapter Name:"
        # Avoid matching lines like "Description ... : ... Adapter", which refer to
        # the adapter name, not a new adapter block.
        is_adapter_header = (
            "adapter" in line.lower()
            and ":" in line
            and "Description" not in line
            and "Physical Address" not in line
            and "Media State" not in line
        )
        if is_adapter_header:
            if (
                in_block
                and current.get("mac")
                and "loopback" not in current.get("desc", "").lower()
            ):
                adapters.append(current)
            current = {"mac": "", "desc": "", "media_state": ""}
            in_block = True
        elif in_block:
            if "Physical Address" in line and ":" in line:
                m = re.search(r":\s*([0-9a-fA-F\-]{17})", line)
                if m:
                    current["mac"] = m.group(1)
            elif "Description" in line and ":" in line:
                current["desc"] = line.split(":", 1)[1].strip()
            elif "Media State" in line and ":" in line:
                current["media_state"] = line.split(":", 1)[1].strip()

    if in_block and current.get("mac") and "loopback" not in current.get("desc", "").lower():
        adapters.append(current)
    return adapters


def _match_desc(a: str, b: str) -> bool:
    """True if descriptions refer to the same adapter (case-insensitive contains or equals)."""
    if not a or not b:
        return False
    a_norm = a.lower().strip()
    b_norm = b.lower().strip()
    return a_norm == b_norm or a_norm in b_norm or b_norm in a_norm


def _get_adapter_info_windows(ifname: str) -> AdapterInfo:
    """Gather adapter info on Windows via PowerShell Get-NetAdapter or ipconfig.

    Uses pysoem's adapter description (same list user picked from) to match the correct
    adapter in Get-NetAdapter/ipconfig. This avoids wrong matches when GUID differs
    from Windows or when multiple adapters exist (e.g. Parallels + ASIX USB).
    """
    info = AdapterInfo(name=ifname)
    adapter_desc = _get_adapter_desc_from_pysoem(ifname)

    def _apply_adapter(mac: str, desc: str, media: str) -> None:
        if mac:
            info.mac_address = mac.replace("-", ":").upper()
        if desc:
            info.hardware_port = desc
        if media:
            info.link_state = (
                "up" if "disconnected" not in media.lower() else "down"
            )

    # 1. Try PowerShell Get-NetAdapter, match by InterfaceDescription
    ps_script = """
    Get-NetAdapter | ForEach-Object {
        $d = if ($_.InterfaceDescription) {
            $_.InterfaceDescription -replace '\\|', ' '
        } else {
            ''
        }
        "DESC=" + $d + "|MAC=" + $_.MacAddress + "|Status=" + $_.Status +
        "|LinkSpeed=" + $_.LinkSpeed
    }
    """
    ps_out = _run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            ps_script.strip(),
        ]
    )
    if ps_out and adapter_desc:
        for line in ps_out.splitlines():
            parts = dict(p.split("=", 1) for p in line.split("|") if "=" in p)
            desc = parts.get("DESC", "").strip()
            if _match_desc(adapter_desc, desc):
                mac = parts.get("MAC", "").strip()
                status = parts.get("Status", "").strip()
                speed = parts.get("LinkSpeed", "").strip()
                if mac:
                    info.mac_address = mac.replace("-", ":").upper()
                if status:
                    info.link_state = status.lower()
                if speed:
                    info.link_speed = speed
                if desc:
                    info.hardware_port = desc
                return info

    # 2. Fallback: ipconfig /all, match by Description
    ipconfig_out = _run(["ipconfig", "/all"])
    if ipconfig_out:
        for ad in _parse_ipconfig_adapters(ipconfig_out):
            if adapter_desc and _match_desc(adapter_desc, ad.get("desc", "")):
                _apply_adapter(
                    ad.get("mac", ""),
                    ad.get("desc", ""),
                    ad.get("media_state", ""),
                )
                return info

    # 3. No description: try GUID match (Get-NetAdapter by InterfaceGuid)
    guid_match = re.search(
        r"NPF_\{([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\}",
        ifname,
    )
    if guid_match and not info.mac_address:
        guid_normalized = guid_match.group(1).upper().replace("-", "")
        ps_script = f"""
        $adapter = Get-NetAdapter | Where-Object {{
            ($_.InterfaceGuid.ToString() -replace '[{{\\-}}]','').ToUpper() -eq '{guid_normalized}'
        }} | Select-Object -First 1
        if ($adapter) {{
            'MAC=' + $adapter.MacAddress
            'Status=' + $adapter.Status
            'LinkSpeed=' + $adapter.LinkSpeed
            'InterfaceDescription=' + ($adapter.InterfaceDescription -replace '\\|', ' ')
        }}
        """
        out = _run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                ps_script.strip(),
            ]
        )
        if out:
            for line in out.splitlines():
                line = line.strip()
                if "=" in line:
                    key, _, val = line.partition("=")
                    val = val.strip()
                    if key == "MAC" and val:
                        info.mac_address = val.replace("-", ":").upper()
                    elif key == "Status" and val:
                        info.link_state = val.lower()
                    elif key == "LinkSpeed" and val:
                        info.link_speed = val
                    elif key == "InterfaceDescription" and val:
                        info.hardware_port = val

    # 4. Last resort: first non-loopback adapter from ipconfig
    if not info.mac_address and ipconfig_out:
        for ad in _parse_ipconfig_adapters(ipconfig_out):
            _apply_adapter(
                ad.get("mac", ""),
                ad.get("desc", ""),
                ad.get("media_state", ""),
            )
            break

    return info


def get_adapter_info(ifname: str) -> AdapterInfo:
    """Gather adapter details for the given interface. Best-effort; missing fields are empty."""
    if sys.platform == "darwin":
        return _get_adapter_info_macos(ifname)
    if sys.platform.startswith("linux"):
        return _get_adapter_info_linux(ifname)
    if sys.platform == "win32":
        return _get_adapter_info_windows(ifname)
    return AdapterInfo(name=ifname)
