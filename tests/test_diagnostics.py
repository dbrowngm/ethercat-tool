"""Unit tests for diagnostics module."""

from unittest.mock import MagicMock

from ethercat_tool.diagnostics import read_diagnostics


def test_read_diagnostics_returns_none_when_all_fail() -> None:
    """When every SDO read fails, return None."""
    device = MagicMock()
    device.sdo_read.side_effect = Exception("object not found")

    result = read_diagnostics(device)

    assert result is None


def test_read_diagnostics_returns_partial_dict_on_partial_success() -> None:
    """When at least one read succeeds, return dict with that value."""
    device = MagicMock()

    def sdo_read(index: int, subindex: int, size: int = 0) -> bytes:
        if index == 0x10F3 and subindex == 2:
            return (42).to_bytes(4, "little")
        raise Exception("not found")

    device.sdo_read = sdo_read

    result = read_diagnostics(device)

    assert result is not None
    assert result.get("Link loss count") == "42"


def test_read_diagnostics_returns_none_when_no_candidates_succeed() -> None:
    """When we have no candidates or all raise, return None."""
    device = MagicMock()
    device.sdo_read.side_effect = Exception("nope")

    result = read_diagnostics(device)

    assert result is None


def test_read_diagnostics_handles_short_response() -> None:
    """Response shorter than 4 bytes is skipped, no crash."""
    device = MagicMock()
    device.sdo_read.return_value = b"\x01\x02"  # too short

    result = read_diagnostics(device)

    # No valid 4-byte read, so result may be None or empty
    assert result is None or "Link loss count" not in result
