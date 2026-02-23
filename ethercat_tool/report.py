"""Build markdown report from topology and slave info."""

from datetime import datetime

from ethercat_tool.esi_data import EsiLookupResult, lookup_device
from ethercat_tool.models import LinkIssue, SlaveInfo, TopologySummary


def _format_manufacturer(
    s: SlaveInfo,
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
    s: SlaveInfo,
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
    slave_infos: list[SlaveInfo],
    link_issues: list[LinkIssue],
    *,
    output_path: str | None = None,
    esi_lookup: dict[tuple[int, int, int], EsiLookupResult] | None = None,
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
    lines.append(f"- **Slaves found:** {summary.slave_count}")
    lines.append(f"- **Init status:** {init_status}")
    lines.append("")

    # Topology
    lines.append("## Topology")
    lines.append("")
    if not slave_infos:
        lines.append("No slaves in chain.")
    else:
        chain = " → ".join([f"[{s.name}]" for s in slave_infos])
        lines.append(f"`Master → {chain}`")
        lines.append("")
        for i, s in enumerate(slave_infos):
            lines.append(f"### Slave {i}: {s.name}")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("| --- | --- |")
            man_display = _format_manufacturer(s, esi_lookup)
            prod_display = _format_product_code(s, esi_lookup)
            lines.append(f"| Manufacturer ID | {man_display} |")
            lines.append(f"| Product Code | {prod_display} |")
            lines.append(f"| Revision | {s.revision} |")
            lines.append(f"| Device Name | {s.device_name} |")
            lines.append(f"| Hardware Version | {s.hardware_version} |")
            lines.append(f"| Firmware | {s.firmware_version} |")
            lines.append(f"| Bootloader | {s.bootloader_version} |")
            lines.append(f"| Serial | {s.serial_number} |")
            lines.append(f"| State | {s.state} |")
            lines.append(f"| AL Status | {s.al_status_text} (0x{s.al_status_code:04X}) |")
            if s.port_status:
                port_str = ", ".join(f"{k}: {v}" for k, v in s.port_status.items())
                lines.append(f"| Ports | {port_str} |")
            if s.diagnostics:
                for k, v in s.diagnostics.items():
                    lines.append(f"| {k} | {v} |")
            lines.append("")

    # Link / init issues
    if link_issues:
        lines.append("## Link / init issues")
        lines.append("")
        for issue in link_issues:
            loc = f"Slave {issue.slave_index}" if issue.slave_index is not None else "Master"
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
        with open(output_path, "w") as f:
            f.write(md)
    return md
