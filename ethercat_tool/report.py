"""Build markdown report from topology and slave info."""

from datetime import datetime, timezone

from ethercat_tool.models import LinkIssue, SlaveInfo, TopologySummary


def build_markdown(
    summary: TopologySummary,
    slave_infos: list[SlaveInfo],
    link_issues: list[LinkIssue],
    *,
    output_path: str | None = None,
) -> str:
    """Build markdown report string; optionally write to file."""
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Title and meta
    lines.append("# EtherCAT Topology Report")
    lines.append("")
    lines.append(f"- **Adapter:** {summary.adapter_name}")
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
            lines.append(f"| Manufacturer ID | {s.manufacturer_id} |")
            lines.append(f"| Product Code | {s.product_code} |")
            lines.append(f"| Revision | {s.revision} |")
            lines.append(f"| Device Name | {s.device_name} |")
            lines.append(f"| Hardware Version | {s.hardware_version} |")
            lines.append(f"| Firmware | {s.firmware_version} |")
            lines.append(f"| Bootloader | {s.bootloader_version} |")
            lines.append(f"| Serial | {s.serial_number} |")
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
            lines.append(f"- **{loc}:** {issue.message}")
        lines.append("")

    md = "\n".join(lines)
    if output_path:
        with open(output_path, "w") as f:
            f.write(md)
    return md
