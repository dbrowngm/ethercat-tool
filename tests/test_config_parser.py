"""Unit tests for config parser and validation."""

import tempfile
from pathlib import Path

from ethercat_tool.config_parser import parse_config, validate_scan
from ethercat_tool.models import DeviceInfo


def test_parse_config_extracts_device_types() -> None:
    """parse_config returns expected device types from ProductRevision."""
    with tempfile.TemporaryDirectory() as d:
        config = Path(d) / "config.xml"
        config.write_text(
            """<?xml version="1.0"?>
<EtherCATConfig>
  <Config>
    <Slave><Info><ProductRevision>EK1100-0000-0018</ProductRevision></Info></Slave>
    <Slave><Info><ProductRevision>EL1014-0000-0018</ProductRevision></Info></Slave>
    <Slave><Info><ProductRevision>EL9011</ProductRevision></Info></Slave>
  </Config>
</EtherCATConfig>"""
        )
        types = parse_config(config)
        assert types == ["EK1100", "EL1014", "EL9011"]


def test_parse_config_nonexistent_raises() -> None:
    """parse_config raises ValueError for missing file."""
    try:
        parse_config("/nonexistent/path/config.xml")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "not found" in str(e)


def test_validate_scan_match() -> None:
    """validate_scan returns no mismatches when devices match config."""
    devices = [
        DeviceInfo("EK1100", 2, 0, 0, "N/A", "", "", "", "", None, "PRE-OP", 0, "OK", None),
        DeviceInfo("EL1014", 2, 0, 0, "N/A", "", "", "", "", None, "PRE-OP", 0, "OK", None),
    ]
    expected = ["EK1100", "EL1014"]
    result = validate_scan(devices, expected)
    assert result.mismatches == []
    assert result.count_expected == 2
    assert result.count_found == 2


def test_validate_scan_mismatch() -> None:
    """validate_scan flags (position, expected, found) on mismatch."""
    devices = [
        DeviceInfo("EK1100", 2, 0, 0, "N/A", "", "", "", "", None, "PRE-OP", 0, "OK", None),
        DeviceInfo("EL2904", 2, 0, 0, "EL2904", "", "", "", "", None, "PRE-OP", 0, "OK", None),
    ]
    expected = ["EK1100", "EL1014"]
    result = validate_scan(devices, expected)
    assert result.mismatches == [(1, "EL1014", "EL2904")]


def test_validate_scan_count_mismatch() -> None:
    """validate_scan reports count difference and missing device types."""
    devices = [
        DeviceInfo("EK1100", 2, 0, 0, "N/A", "", "", "", "", None, "PRE-OP", 0, "OK", None),
    ]
    expected = ["EK1100", "EL1014"]
    result = validate_scan(devices, expected)
    assert result.count_expected == 2
    assert result.count_found == 1
    assert result.missing == [(1, "EL1014")]
