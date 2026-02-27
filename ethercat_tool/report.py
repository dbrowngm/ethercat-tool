"""Build markdown report from topology and device info."""

from datetime import datetime

from ethercat_tool.config_parser import ConfigValidationResult
from ethercat_tool.esi_data import EsiLookupResult, lookup_device
from ethercat_tool.models import DeviceInfo, LinkIssue, TopologySummary

_PORT_LABELS = ("A", "B", "C", "D")

# Diagnostic keys we parse for per-port table; others go to main table
_CRC_KEY = "CRC (Port A/B/C/D)"
_FWD_CRC_KEY = "Fwd CRC (Port A/B/C/D)"
_LINK_LOSS_KEY = "Link loss"


def _parse_port_values(value_str: str) -> dict[str, str] | None:
    """Parse '0 / 1 / 2 / 3' into {A: 0, B: 1, C: 2, D: 3}."""
    parts = [p.strip() for p in value_str.split("/")]
    if len(parts) != 4:
        return None
    return dict(zip(_PORT_LABELS, parts))


def _extract_port_diagnostics(
    diagnostics: dict[str, str] | None,
) -> tuple[dict[str, str] | None, dict[str, str] | None, str | None, dict[str, str]]:
    """Extract per-port CRC/Fwd CRC, link loss, and remaining diagnostics.

    Returns:
        (crc_by_port, fwd_crc_by_port, link_loss, other_diagnostics)
    """
    if not diagnostics:
        return None, None, None, {}

    crc_by_port = (
        _parse_port_values(diagnostics[_CRC_KEY]) if _CRC_KEY in diagnostics else None
    )
    fwd_crc_by_port = (
        _parse_port_values(diagnostics[_FWD_CRC_KEY])
        if _FWD_CRC_KEY in diagnostics
        else None
    )
    link_loss = diagnostics.get(_LINK_LOSS_KEY)

    other = {
        k: v for k, v in diagnostics.items()
        if k not in (_CRC_KEY, _FWD_CRC_KEY, _LINK_LOSS_KEY)
    }
    return crc_by_port, fwd_crc_by_port, link_loss, other


def _render_port_table(
    port_status: dict[str, str] | None,
    crc_by_port: dict[str, str] | None,
    fwd_crc_by_port: dict[str, str] | None,
) -> list[str]:
    """Build per-port subtable lines. Returns empty if no port data."""
    has_status = port_status is not None
    has_crc = bool(crc_by_port)
    has_fwd_crc = bool(fwd_crc_by_port)
    if not (has_status or has_crc or has_fwd_crc):
        return []

    ports: set[str] = set()
    if port_status:
        ports.update(port_status)
    if crc_by_port:
        ports.update(crc_by_port)
    if fwd_crc_by_port:
        ports.update(fwd_crc_by_port)
    sorted_ports = sorted(
        ports, key=lambda p: _PORT_LABELS.index(p) if p in _PORT_LABELS else 99
    )

    cols = ["Port"]
    if has_status and port_status is not None:
        cols.append("Status")
    if has_crc:
        cols.append("CRC")
    if has_fwd_crc:
        cols.append("Fwd CRC")

    lines = ["", "**Port diagnostics**", ""]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join("---" for _ in cols) + " |")
    for p in sorted_ports:
        row = [p]
        if has_status and port_status is not None:
            row.append(port_status.get(p, "—"))
        if has_crc:
            row.append(crc_by_port.get(p, "—") if crc_by_port else "—")
        if has_fwd_crc:
            row.append(fwd_crc_by_port.get(p, "—") if fwd_crc_by_port else "—")
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return lines


def _format_manufacturer(
    s: DeviceInfo,
    esi_lookup: dict[tuple[int, int, int], EsiLookupResult] | None,
) -> str:
    base = f"{s.manufacturer_id} (0x{s.manufacturer_id:08X})"
    if esi_lookup:
        res = lookup_device(
            esi_lookup, s.manufacturer_id, s.product_code, s.revision
        )
        if res and res.manufacturer_name:
            return f"{base} — {res.manufacturer_name}"
    return base


def _format_product_code(
    s: DeviceInfo,
    esi_lookup: dict[tuple[int, int, int], EsiLookupResult] | None,
) -> str:
    base = f"{s.product_code} (0x{s.product_code:08X})"
    if esi_lookup:
        res = lookup_device(
            esi_lookup, s.manufacturer_id, s.product_code, s.revision
        )
        if res and res.product_name:
            return f"{base} — {res.product_name}"
    return base


def build_markdown(
    summary: TopologySummary,
    device_infos: list[DeviceInfo],
    link_issues: list[LinkIssue],
    *,
    output_path: str | None = None,
    esi_lookup: dict[tuple[int, int, int], EsiLookupResult] | None = None,
    config_validation: ConfigValidationResult | None = None,
) -> str:
    """Build markdown report string; optionally write to file."""
    lines: list[str] = []
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    # Title and meta
    lines.append("# EtherCAT Topology Report")
    lines.append("")
    lines.append(f"- **Adapter:** {summary.adapter_name}")
    if summary.adapter_info:
        details = summary.adapter_info.as_dict()
        if details:
            lines.append("- **Adapter details:**")
            for k, v in details.items():
                lines.append(f"  - {k}: {v}")
    lines.append(f"- **Timestamp:** {now}")
    lines.append("")

    # Summary
    init_status = "OK" if summary.init_ok else "Failed"
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Devices found:** {summary.device_count}")
    lines.append(f"- **Init status:** {init_status}")
    lines.append("")

    # Topology
    lines.append("## Topology")
    lines.append("")
    if not device_infos:
        lines.append("No devices in chain.")
    else:
        chain = " → ".join([f"[{s.name}]" for s in device_infos])
        lines.append(f"`Master → {chain}`")
        lines.append("")
        for i, s in enumerate(device_infos):
            lines.append(f"### Device {i}: {s.name}")
            lines.append("")
            crc_by_port, fwd_crc_by_port, link_loss, other_diag = _extract_port_diagnostics(
                s.diagnostics
            )
            # Main table: identity, state, link loss, other diagnostics
            lines.append("| Field | Value |")
            lines.append("| --- | --- |")
            man_display = _format_manufacturer(s, esi_lookup)
            prod_display = _format_product_code(s, esi_lookup)
            lines.append(f"| Manufacturer ID | {man_display} |")
            lines.append(f"| Product Code | {prod_display} |")
            lines.append(f"| Revision | {s.revision} (0x{s.revision:08X}) |")
            lines.append(f"| Device Name | {s.device_name} |")
            lines.append(f"| Hardware Version | {s.hardware_version} |")
            lines.append(f"| Firmware | {s.firmware_version} |")
            lines.append(f"| Bootloader | {s.bootloader_version} |")
            lines.append(f"| Serial | {s.serial_number} |")
            lines.append(f"| State | {s.state} |")
            lines.append(f"| AL Status | {s.al_status_text} (0x{s.al_status_code:04X}) |")
            if link_loss is not None:
                lines.append(f"| Link loss | {link_loss} |")
            for k, v in other_diag.items():
                lines.append(f"| {k} | {v} |")
            # Per-port subtable when port data exists
            port_table = _render_port_table(s.port_status, crc_by_port, fwd_crc_by_port)
            lines.extend(port_table)
            lines.append("")

    # Config validation
    if config_validation is not None:
        lines.append("## Config validation")
        lines.append("")
        if (
            config_validation.count_expected == config_validation.count_found
            and not config_validation.mismatches
        ):
            lines.append("All devices match config.")
        else:
            if config_validation.count_expected != config_validation.count_found:
                lines.append(
                    f"- **Device count:** Expected {config_validation.count_expected}, "
                    f"Found {config_validation.count_found}"
                )
                if config_validation.missing:
                    missing_types = ", ".join(
                        f"{t} (position {p})" for p, t in config_validation.missing
                    )
                    lines.append(f"- **Missing:** {missing_types}")
                lines.append("")
            for pos, expected, found in config_validation.mismatches:
                lines.append(f"- **Position {pos}:** Expected: {expected}, Found: {found}")
        lines.append("")

    # Link / init issues
    if link_issues:
        lines.append("## Link / init issues")
        lines.append("")
        for issue in link_issues:
            loc = f"Device {issue.device_index}" if issue.device_index is not None else "Master"
            if "\n" in issue.message:
                lines.append(f"- **{loc}:**")
                lines.append("")
                lines.append("```")
                lines.append(issue.message.strip())
                lines.append("```")
            else:
                lines.append(f"- **{loc}:** {issue.message}")
        lines.append("")

    md = "\n".join(lines)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)
    return md
