"""CLI tests with mocked scanner and pysoem."""

from io import StringIO
from unittest.mock import MagicMock, patch

from ethercat_tool.cli import main, parse_args


def test_parse_args_list_adapters() -> None:
    """--list-adapters sets list_adapters and does not require adapter."""
    args = parse_args(["--list-adapters"])
    assert args.list_adapters is True
    assert args.adapter is None


def test_parse_args_adapter_and_options() -> None:
    """--adapter with --output and --no-coe and --timeout-ms."""
    args = parse_args(
        ["--adapter", "eth0", "--output", "out.md", "--no-coe", "--timeout-ms", "300"]
    )
    assert args.adapter == "eth0"
    assert args.output == "out.md"
    assert args.no_coe is True
    assert args.timeout_ms == 300


def test_main_list_adapters_prints_and_returns_0() -> None:
    """With --list-adapters, main prints adapter list and returns 0."""
    fake_adapter = MagicMock()
    fake_adapter.name = "eth0"
    fake_adapter.desc = "Ethernet"

    with patch("ethercat_tool.cli.pysoem") as m_pysoem:
        m_pysoem.find_adapters.return_value = [fake_adapter]

        with patch("sys.stdout", new_callable=StringIO) as out:
            rc = main(["--list-adapters"])

    assert rc == 0
    assert "eth0" in out.getvalue()
    assert "Ethernet" in out.getvalue()


def test_main_adapter_required_without_list() -> None:
    """Without --adapter and without --list-adapters, main returns 1 and prints error."""
    with patch("sys.stderr", new_callable=StringIO) as err:
        rc = main([])
    assert rc == 1
    assert "adapter" in err.getvalue().lower() or "required" in err.getvalue().lower()


def test_main_scan_produces_markdown() -> None:
    """With --adapter and mocked scan, main produces markdown with topology."""
    mock_slave = MagicMock()
    mock_slave.name = "EL1008"
    mock_slave.man = 2
    mock_slave.id = 0
    mock_slave.rev = 0

    with patch("ethercat_tool.cli.scan") as m_scan:
        from ethercat_tool.models import TopologySummary

        m_scan.return_value = (
            [mock_slave],
            TopologySummary(adapter_name="eth0", slave_count=1, init_ok=True),
            [],
        )

        with patch("sys.stdout", new_callable=StringIO) as out:
            rc = main(["--adapter", "eth0", "--no-coe"])

    assert rc == 0
    md = out.getvalue()
    assert "EtherCAT Topology Report" in md
    assert "eth0" in md
    assert "EL1008" in md


def test_main_scan_with_output_file(tmp_path: str) -> None:
    """With --output, report is written to file and not printed to stdout."""
    out_file = tmp_path / "report.md"

    with patch("ethercat_tool.cli.scan") as m_scan:
        from ethercat_tool.models import TopologySummary

        m_scan.return_value = ([], TopologySummary("eth0", 0, False), [])

        with patch("sys.stdout", new_callable=StringIO) as out:
            rc = main(["--adapter", "eth0", "--output", str(out_file)])

    assert rc == 0
    content = out_file.read_text()
    assert content
    assert "EtherCAT" in content
    assert out.getvalue() == ""


def test_main_permission_error_reexecs_with_sudo_unless_no_elevate() -> None:
    """Permission-like init error and not root: we try to re-exec with sudo."""
    from ethercat_tool.models import LinkIssue, TopologySummary

    with patch("ethercat_tool.cli.scan") as m_scan:
        m_scan.return_value = (
            [],
            TopologySummary("en7", 0, False),
            [LinkIssue(None, "Init failed: could not open interface en7")],
        )
        with patch("ethercat_tool.cli.os.geteuid", return_value=500):
            with patch("ethercat_tool.cli.os.execvp") as m_exec:
                m_exec.side_effect = OSError(2, "No such file or directory: sudo")
                with patch("sys.stderr", new_callable=StringIO) as err:
                    with patch("sys.stdout", new_callable=StringIO):
                        rc = main(["--adapter", "en7"])
        m_exec.assert_called_once()
        assert "sudo" in str(m_exec.call_args[0][1])
        assert "en7" in str(m_exec.call_args[0][1])
    assert "could not open" in err.getvalue()
    assert rc == 0


def test_main_permission_error_no_reexec_with_no_elevate() -> None:
    """With --no-elevate we do not re-exec on permission error."""
    from ethercat_tool.models import LinkIssue, TopologySummary

    with patch("ethercat_tool.cli.scan") as m_scan:
        m_scan.return_value = (
            [],
            TopologySummary("en7", 0, False),
            [LinkIssue(None, "Init failed: could not open interface en7")],
        )
        with patch("ethercat_tool.cli.os.geteuid", return_value=500):
            with patch("ethercat_tool.cli.os.execvp") as m_exec:
                with patch("sys.stderr", new_callable=StringIO):
                    with patch("sys.stdout", new_callable=StringIO) as out:
                        main(["--adapter", "en7", "--no-elevate"])
        m_exec.assert_not_called()
    assert "could not open" in out.getvalue() or "Init failed" in out.getvalue()
