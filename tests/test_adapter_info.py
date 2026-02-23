"""Unit tests for adapter_info module."""

from unittest.mock import patch

from ethercat_tool.adapter_info import AdapterInfo, get_adapter_info


def test_adapter_info_as_dict_omits_empty_fields() -> None:
    """as_dict returns only non-empty fields."""
    info = AdapterInfo(name="eth0", mac_address="AA:BB:CC:DD:EE:FF", link_state="up")
    d = info.as_dict()
    assert d["MAC Address"] == "AA:BB:CC:DD:EE:FF"
    assert d["Link State"] == "up"
    assert "Link Speed" not in d
    assert "Driver/Type" not in d


def test_get_adapter_info_macos_parses_ifconfig() -> None:
    """macOS ifconfig output is parsed correctly."""
    ifconfig_out = """
eth0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
	ether aa:bb:cc:dd:ee:ff
	inet 192.168.1.100 netmask 0xffffff00 broadcast 192.168.1.255
	media: autoselect (1000baseT <full-duplex>) status: active
"""
    with patch("sys.platform", "darwin"):
        with patch("ethercat_tool.adapter_info._run") as m_run:
            def run_side_effect(cmd, timeout=5.0):
                if cmd[0] == "ifconfig":
                    return ifconfig_out
                return ""

            m_run.side_effect = run_side_effect
            info = get_adapter_info("eth0")

    assert info.name == "eth0"
    assert info.mac_address == "AA:BB:CC:DD:EE:FF"
    assert info.link_state == "active"
    assert "1000" in info.link_speed
    assert "full-duplex" in info.link_speed
    assert info.mtu == "1500"
    assert info.ip_address == "192.168.1.100"


def test_get_adapter_info_linux_parses_ip_and_ethtool() -> None:
    """Linux ip link and ethtool output is parsed correctly."""
    ip_link = "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP\n    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff"
    ethtool_out = "Speed: 1000Mb/s\nDuplex: Full\nLink detected: yes\nDriver: igb"
    ip_addr = "2: eth0: ...\n    inet 10.0.0.1/24 brd 10.0.0.255 scope global eth0"

    with patch("sys.platform", "linux"):
        with patch("ethercat_tool.adapter_info._run") as m_run:
            def run_side_effect(cmd, timeout=5.0):
                if cmd[:2] == ["ip", "link"]:
                    return ip_link
                if cmd[:2] == ["ip", "-4"]:
                    return ip_addr
                if cmd[0] == "ethtool":
                    return ethtool_out
                return ""

            m_run.side_effect = run_side_effect
            info = get_adapter_info("eth0")

    assert info.name == "eth0"
    assert info.mac_address == "AA:BB:CC:DD:EE:FF"
    assert info.link_state == "up"
    assert "1000Mb/s" in info.link_speed
    assert info.driver_or_type == "igb"
    assert info.mtu == "1500"
    assert info.ip_address == "10.0.0.1"


def test_get_adapter_info_macos_hardware_port() -> None:
    """macOS networksetup maps interface to hardware port."""
    ifconfig_out = "ether aa:bb:cc:dd:ee:ff\nmedia: autoselect status: active"
    networksetup_out = """
Hardware Port: Thunderbolt Ethernet
Device: en7
Ethernet Address: aa:bb:cc:dd:ee:ff

Hardware Port: Wi-Fi
Device: en0
"""
    with patch("sys.platform", "darwin"):
        with patch("ethercat_tool.adapter_info._run") as m_run:
            def run_side_effect(cmd, timeout=5.0):
                if cmd[0] == "ifconfig":
                    return ifconfig_out
                if cmd[0] == "networksetup":
                    return networksetup_out
                return ""

            m_run.side_effect = run_side_effect
            info = get_adapter_info("en7")

    assert info.hardware_port == "Thunderbolt Ethernet"


def test_get_adapter_info_handles_missing_interface() -> None:
    """Missing interface returns minimal info with empty fields."""
    with patch("sys.platform", "darwin"):
        with patch("ethercat_tool.adapter_info._run", return_value=""):
            info = get_adapter_info("nonexistent0")
    assert info.name == "nonexistent0"
    assert info.as_dict() == {}
