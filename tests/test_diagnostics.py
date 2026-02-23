"""Unit tests for diagnostics module."""

from unittest.mock import MagicMock

from ethercat_tool.diagnostics import read_diagnostics, read_esc_port_diagnostics


def test_read_esc_port_diagnostics_returns_none_when_no_fprd() -> None:
    """When _fprd is unavailable, return None."""
    device = MagicMock(spec=["name"])  # no _fprd
    assert not hasattr(device, "_fprd") or getattr(device, "_fprd", None) is None
    result = read_esc_port_diagnostics(device)
    assert result is None


def test_read_esc_port_diagnostics_returns_counters_when_fprd_succeeds() -> None:
    """When _fprd returns valid ESC data, parse into per-port counters."""
    device = MagicMock()

    def fprd(addr: int, size: int, timeout_us: int = 2000) -> bytes:
        if addr == 0x0300:
            return b"\x01\x00\x02\x00\x03\x00\x04\x00"  # RXERR: 1,2,3,4
        if addr == 0x0308:
            return b"\x0a\x00\x0b\x00\x0c\x00\x0d\x00"  # FRXERR: 10,11,12,13
        if addr == 0x0310:
            return b"\x05"  # LLCNT: 5
        return b""

    device._fprd = fprd

    result = read_esc_port_diagnostics(device)

    assert result is not None
    assert result["CRC (Port A/B/C/D)"] == "1 / 2 / 3 / 4"
    assert result["Fwd CRC (Port A/B/C/D)"] == "10 / 11 / 12 / 13"
    assert result["Link loss"] == "5"


def test_read_esc_port_diagnostics_returns_none_on_fprd_error() -> None:
    """When _fprd raises, return None."""
    device = MagicMock()
    device._fprd = MagicMock(side_effect=Exception("WkcError"))

    result = read_esc_port_diagnostics(device)

    assert result is None


def test_read_diagnostics_returns_none_when_all_fail() -> None:
    """When ESC and CoE reads all fail, return None."""
    device = MagicMock()
    device._fprd = None
    device.sdo_read.side_effect = Exception("object not found")

    result = read_diagnostics(device)

    assert result is None


def test_read_diagnostics_returns_partial_dict_on_coe_success() -> None:
    """When CoE read succeeds (no ESC), return dict with that value."""
    device = MagicMock()
    device._fprd = None

    def sdo_read(index: int, subindex: int, size: int = 0) -> bytes:
        if index == 0x10F3 and subindex == 2:
            return (42).to_bytes(4, "little")
        raise Exception("not found")

    device.sdo_read = sdo_read

    result = read_diagnostics(device)

    assert result is not None
    assert result.get("Link loss (CoE)") == "42"


def test_read_diagnostics_prefers_esc_over_coe() -> None:
    """ESC diagnostics are included; CoE supplements when different keys."""
    device = MagicMock()

    def fprd(addr: int, size: int, timeout_us: int = 2000) -> bytes:
        if addr == 0x0300:
            return b"\x00\x00\x00\x00\x00\x00\x00\x00"
        if addr == 0x0308:
            return b"\x00\x00\x00\x00\x00\x00\x00\x00"
        if addr == 0x0310:
            return b"\x00"
        return b""

    device._fprd = fprd
    device.sdo_read.return_value = (99).to_bytes(4, "little")

    result = read_diagnostics(device)

    assert result is not None
    assert "CRC (Port A/B/C/D)" in result
    assert result.get("Link loss (CoE)") == "99"


def test_read_diagnostics_returns_none_when_no_candidates_succeed() -> None:
    """When ESC fails and no CoE candidates succeed, return None."""
    device = MagicMock()
    device._fprd = None
    device.sdo_read.side_effect = Exception("nope")

    result = read_diagnostics(device)

    assert result is None


def test_read_diagnostics_handles_short_response() -> None:
    """Response shorter than 4 bytes is skipped, no crash."""
    device = MagicMock()
    device._fprd = None
    device.sdo_read.return_value = b"\x01\x02"  # too short

    result = read_diagnostics(device)

    assert result is None or "Link loss (CoE)" not in result
