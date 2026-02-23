"""CLI: list adapters or scan and print markdown report."""

import argparse
import os
import sys
from datetime import datetime
from typing import NoReturn

import pysoem

from ethercat_tool.esi_data import (
    fetch_esi_data,
    has_esi_data,
    load_esi_lookup,
)
from ethercat_tool.config_parser import parse_config, validate_scan
from ethercat_tool.report import build_markdown
from ethercat_tool.scanner import scan


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        prog="ethercat-tool",
        description="EtherCAT troubleshooting: scan devices, topology map, link diagnostics.",
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
        "--print",
        dest="print_results",
        action="store_true",
        help="Print scan results to stdout instead of writing to a file.",
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
    p.add_argument(
        "--fetch-esi",
        action="store_true",
        help="Download ESI device database (linuxcnc-ethercat/esi-data).",
    )
    p.add_argument(
        "--no-esi-prompt",
        action="store_true",
        help="Do not prompt to fetch ESI when missing; use raw IDs only.",
    )
    p.add_argument(
        "--validate-config",
        metavar="PATH",
        dest="validate_config",
        help="Validate scan against TwinCAT EtherCAT config XML (checks Device Name vs ProductRevision).",
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


def _ensure_esi_data(args: argparse.Namespace) -> bool:
    """Ensure ESI data exists. Fetch if --fetch-esi, prompt if missing. Return True to proceed."""
    if has_esi_data():
        return True
    if args.fetch_esi:
        print(
            "Downloading ESI device database (may take 1–2 minutes)...",
            file=sys.stderr,
        )
        if fetch_esi_data():
            print("ESI data downloaded successfully.", file=sys.stderr)
            return True
        print("Warning: Failed to download ESI data. Proceeding with raw IDs.", file=sys.stderr)
        return True  # proceed anyway
    if args.no_esi_prompt:
        return True  # user opted out of prompt
    if sys.stdin.isatty():
        try:
            reply = input(
                "No ESI device data found. Decode manufacturer/product names? [y/N] "
            ).strip().lower()
            if reply in ("y", "yes"):
                print(
                    "Downloading ESI device database (may take 1–2 minutes)...",
                    file=sys.stderr,
                )
                if fetch_esi_data():
                    return True
        except EOFError:
            pass
    return True  # proceed with raw IDs


def _run_scan(args: argparse.Namespace, user_argv: list[str]) -> int:
    if not args.adapter:
        print(
            "Error: --adapter is required for scan. Use --list-adapters to see adapters.",
            file=sys.stderr,
        )
        return 1

    _ensure_esi_data(args)
    esi_lookup = load_esi_lookup()

    device_infos, summary, link_issues = scan(
        args.adapter,
        verbose=args.verbose,
        coe=not args.no_coe,
        timeout_ms=args.timeout_ms,
    )

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

    output_path: str | None = None
    if not args.print_results:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = f"ethercat-scan-{timestamp}.md"

    config_validation = None
    if args.validate_config:
        try:
            expected_types = parse_config(args.validate_config)
            config_validation = validate_scan(device_infos, expected_types, esi_lookup)
            for pos, expected, found in config_validation.mismatches:
                print(
                    f"ethercat-tool: Position {pos}: Expected: {expected}, Found: {found}",
                    file=sys.stderr,
                )
            if config_validation.count_expected != config_validation.count_found:
                print(
                    f"ethercat-tool: Device count: Expected {config_validation.count_expected}, "
                    f"Found {config_validation.count_found}",
                    file=sys.stderr,
                )
                for pos, expected in config_validation.missing:
                    print(
                        f"ethercat-tool: Missing: {expected} (position {pos})",
                        file=sys.stderr,
                    )
        except ValueError as e:
            print(f"ethercat-tool: Config validation failed: {e}", file=sys.stderr)

    md = build_markdown(
        summary,
        device_infos,
        link_issues,
        output_path=output_path,
        esi_lookup=esi_lookup,
        config_validation=config_validation,
    )
    if args.print_results:
        print(md)
    else:
        print(f"Report saved to {output_path}", file=sys.stderr)
    return 0


def _run_fetch_esi() -> int:
    """Fetch ESI data and exit. Replaces any existing data."""
    print(
        "Downloading ESI device database (may take 1–2 minutes)...",
        file=sys.stderr,
    )
    if fetch_esi_data():
        print("ESI data downloaded and indexed.", file=sys.stderr)
        return 0
    print("Error: Failed to download ESI data.", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    """Entrypoint: parse args, list adapters or scan and report."""
    args = parse_args(argv)
    user_argv = argv if argv is not None else sys.argv[1:]
    if args.list_adapters:
        return _list_adapters()
    if args.fetch_esi and not args.adapter:
        return _run_fetch_esi()
    return _run_scan(args, user_argv)


def main_or_exit() -> NoReturn:
    """Run main and exit with its return code."""
    sys.exit(main())
