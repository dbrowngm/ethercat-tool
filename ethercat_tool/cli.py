"""CLI: list adapters or scan and print markdown report."""

import argparse
import os
import sys
from typing import NoReturn

import pysoem

from ethercat_tool.diagnostics import read_diagnostics
from ethercat_tool.report import build_markdown
from ethercat_tool.scanner import scan
from ethercat_tool.slave_info import collect_slave_info


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        prog="ethercat-tool",
        description="EtherCAT troubleshooting: scan slaves, topology map, link diagnostics.",
    )
    p.add_argument(
        "--list-adapters",
        action="store_true",
        help="List available network adapters and exit.",
    )
    p.add_argument(
        "--adapter",
        metavar="NAME",
        help="Adapter name (e.g. eth0 or device ID from --list-adapters).",
    )
    p.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        help="Write markdown report to file (default: stdout).",
    )
    p.add_argument(
        "--no-coe",
        action="store_true",
        help="Skip CoE reads (faster, topology and SII only).",
    )
    p.add_argument(
        "--timeout-ms",
        type=int,
        default=500,
        metavar="MS",
        help="SDO read timeout in ms (default: 500).",
    )
    p.add_argument(
        "--no-elevate",
        action="store_true",
        help="Do not re-run with sudo on permission error.",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Include traceback and extra detail when init fails.",
    )
    return p.parse_args(argv)


def _looks_like_permission_error(message: str) -> bool:
    """True if the init error is likely due to missing privileges."""
    lower = message.lower()
    return any(
        phrase in lower
        for phrase in [
            "permission denied",
            "operation not permitted",
            "could not open",
            "access denied",
            "not permitted",
        ]
    )


def _reexec_with_sudo(user_argv: list[str]) -> NoReturn:
    """Re-exec this process with sudo and same arguments; never returns."""
    argv = ["sudo", sys.executable, "-m", "ethercat_tool"] + user_argv
    os.execvp("sudo", argv)


def _list_adapters() -> int:
    adapters = pysoem.find_adapters()
    for a in adapters:
        name = getattr(a, "name", "")
        desc = getattr(a, "desc", "")
        print(f"{name}\t{desc}")
    return 0


def _run_scan(args: argparse.Namespace, user_argv: list[str]) -> int:
    if not args.adapter:
        print(
            "Error: --adapter is required for scan. Use --list-adapters to see adapters.",
            file=sys.stderr,
        )
        return 1

    slaves, summary, link_issues = scan(args.adapter, verbose=args.verbose)

    # On permission-style init failure, re-run once under sudo unless root or --no-elevate.
    if (
        link_issues
        and not args.no_elevate
        and os.geteuid() != 0
        and len(link_issues) == 1
        and _looks_like_permission_error(link_issues[0].message)
    ):
        try:
            _reexec_with_sudo(user_argv)
        except OSError:
            pass  # sudo missing or exec failed; fall through to report original error

    if link_issues:
        for issue in link_issues:
            print(f"ethercat-tool: {issue.message}", file=sys.stderr)
    slave_infos = []
    for s in slaves:
        diag = None
        if not args.no_coe:
            diag = read_diagnostics(s, timeout_ms=args.timeout_ms)
        info = collect_slave_info(
            s,
            coe=not args.no_coe,
            timeout_ms=args.timeout_ms,
            diagnostics=diag,
        )
        slave_infos.append(info)

    md = build_markdown(
        summary,
        slave_infos,
        link_issues,
        output_path=args.output,
    )
    if not args.output:
        print(md)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entrypoint: parse args, list adapters or scan and report."""
    args = parse_args(argv)
    user_argv = argv if argv is not None else sys.argv[1:]
    if args.list_adapters:
        return _list_adapters()
    return _run_scan(args, user_argv)


def main_or_exit() -> NoReturn:
    """Run main and exit with its return code."""
    sys.exit(main())
