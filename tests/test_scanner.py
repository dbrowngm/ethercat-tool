"""Integration-style tests for scanner with mocked PySOEM."""

from unittest.mock import MagicMock, patch

from ethercat_tool.scanner import scan


def test_scan_no_devices() -> None:
    """When config_init finds no devices, summary and issues reflect it."""
    mock_master = MagicMock()
    mock_master.config_init.return_value = 0
    mock_master.slaves = []

    with patch("ethercat_tool.scanner.pysoem") as m_pysoem:
        m_pysoem.Master.return_value = mock_master

        devices, summary, issues = scan("eth0")

    assert devices == []
    assert summary.adapter_name == "eth0"
    assert summary.device_count == 0
    assert summary.init_ok is False
    assert any("No devices found" in i.message for i in issues)
    mock_master.open.assert_called_once_with("eth0")
    mock_master.close.assert_called_once()


def test_scan_two_devices() -> None:
    """When config_init finds devices, they are returned in order."""
    mock_device1 = MagicMock()
    mock_device1.name = "S1"
    mock_device2 = MagicMock()
    mock_device2.name = "S2"
    mock_master = MagicMock()
    mock_master.config_init.return_value = 2
    mock_master.slaves = [mock_device1, mock_device2]

    with patch("ethercat_tool.scanner.pysoem") as m_pysoem:
        m_pysoem.Master.return_value = mock_master

        devices, summary, issues = scan("en0")

    assert len(devices) == 2
    assert devices[0].name == "S1"
    assert devices[1].name == "S2"
    assert summary.device_count == 2
    assert summary.init_ok is True
    assert summary.adapter_name == "en0"
    assert not issues
    mock_master.close.assert_called_once()


def test_scan_open_raises() -> None:
    """When open() raises, we get empty devices, init_ok False, and an issue."""
    mock_master = MagicMock()
    mock_master.open.side_effect = ConnectionError("No such device")

    with patch("ethercat_tool.scanner.pysoem") as m_pysoem:
        m_pysoem.Master.return_value = mock_master

        devices, summary, issues = scan("eth99")

    assert devices == []
    assert summary.device_count == 0
    assert summary.init_ok is False
    assert any("Init failed" in i.message for i in issues)
    mock_master.close.assert_called_once()
