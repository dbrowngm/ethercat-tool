"""Integration-style tests for scanner with mocked PySOEM."""

from unittest.mock import MagicMock, patch

from ethercat_tool.scanner import scan


def test_scan_no_slaves() -> None:
    """When config_init finds no slaves, summary and issues reflect it."""
    mock_master = MagicMock()
    mock_master.config_init.return_value = 0
    mock_master.slaves = []

    with patch("ethercat_tool.scanner.pysoem") as m_pysoem:
        m_pysoem.Master.return_value = mock_master

        slaves, summary, issues = scan("eth0")

    assert slaves == []
    assert summary.adapter_name == "eth0"
    assert summary.slave_count == 0
    assert summary.init_ok is False
    assert any("No slaves found" in i.message for i in issues)
    mock_master.open.assert_called_once_with("eth0")
    mock_master.close.assert_called_once()


def test_scan_two_slaves() -> None:
    """When config_init finds slaves, they are returned in order."""
    mock_slave1 = MagicMock()
    mock_slave1.name = "S1"
    mock_slave2 = MagicMock()
    mock_slave2.name = "S2"
    mock_master = MagicMock()
    mock_master.config_init.return_value = 2
    mock_master.slaves = [mock_slave1, mock_slave2]

    with patch("ethercat_tool.scanner.pysoem") as m_pysoem:
        m_pysoem.Master.return_value = mock_master

        slaves, summary, issues = scan("en0")

    assert len(slaves) == 2
    assert slaves[0].name == "S1"
    assert slaves[1].name == "S2"
    assert summary.slave_count == 2
    assert summary.init_ok is True
    assert summary.adapter_name == "en0"
    assert not issues
    mock_master.close.assert_called_once()


def test_scan_open_raises() -> None:
    """When open() raises, we get empty slaves, init_ok False, and an issue."""
    mock_master = MagicMock()
    mock_master.open.side_effect = ConnectionError("No such device")

    with patch("ethercat_tool.scanner.pysoem") as m_pysoem:
        m_pysoem.Master.return_value = mock_master

        slaves, summary, issues = scan("eth99")

    assert slaves == []
    assert summary.slave_count == 0
    assert summary.init_ok is False
    assert any("Init failed" in i.message for i in issues)
    mock_master.close.assert_called_once()
