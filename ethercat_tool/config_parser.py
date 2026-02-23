"""Parse TwinCAT EtherCAT config XML and validate scan against it."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ethercat_tool.models import DeviceInfo

_NA = "N/A"


def _extract_device_type(product_revision: str) -> str:
    """Extract device type from ProductRevision (e.g. EL1014-0000-0018 -> EL1014)."""
    if not product_revision or not product_revision.strip():
        return ""
    s = product_revision.strip()
    # Prefix before first hyphen; no hyphen = use full string (e.g. EL9011)
    idx = s.find("-")
    return s[:idx] if idx >= 0 else s


def parse_config(config_path: str | Path) -> list[str]:
    """Parse TwinCAT EtherCAT config XML and return expected device types by position.

    Returns a list of device type strings (e.g. ['EK1100', 'EL1014', ...]) in topology order.
    Raises ValueError on parse error or invalid structure.
    """
    path = Path(config_path)
    if not path.exists():
        raise ValueError(f"Config file not found: {path}")

    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML in config file: {e}") from e

    root = tree.getroot()

    def local_tag(elem):
        tag = elem.tag or ""
        return tag.split("}")[-1] if "}" in tag else tag

    def find_child(parent, name: str):
        for c in parent:
            if local_tag(c) == name:
                return c
        return None

    # Find Config element, then all Slave children
    config = None
    for elem in root.iter():
        if local_tag(elem) == "Config":
            config = elem
            break
    if config is None:
        return []

    result: list[str] = []
    for slave in config:
        if local_tag(slave) != "Slave":
            continue
        info = find_child(slave, "Info")
        if info is None:
            continue
        pr_el = find_child(info, "ProductRevision")
        if pr_el is not None and pr_el.text:
            device_type = _extract_device_type(pr_el.text)
            if device_type:
                result.append(device_type)
            else:
                result.append(pr_el.text.strip())
        else:
            result.append("")

    return result


def _get_found_device_type(
    device: "DeviceInfo",
    esi_lookup: dict[tuple[int, int, int], object] | None,
) -> str:
    """Get the device type string for a scanned device.

    Resolution order: device_name (CoE), name (SII), first token of ESI product_name.
    """
    from ethercat_tool.esi_data import lookup_device

    if device.device_name and device.device_name != _NA:
        return device.device_name.strip()
    if device.name and device.name != _NA:
        return device.name.strip()
    if esi_lookup:
        res = lookup_device(
            esi_lookup, device.manufacturer_id, device.product_code, device.revision
        )
        if res and res.product_name:
            first = res.product_name.split()[0] if res.product_name.split() else ""
            if first:
                return first
    return _NA


@dataclass(frozen=True)
class ConfigValidationResult:
    """Result of validating scan against config."""

    count_expected: int
    count_found: int
    mismatches: list[tuple[int, str, str]]  # (position, expected, found)
    missing: list[tuple[int, str]]  # (position, expected_type) when expected > found


def validate_scan(
    device_infos: list["DeviceInfo"],
    expected_types: list[str],
    esi_lookup: dict[tuple[int, int, int], object] | None = None,
) -> ConfigValidationResult:
    """Compare scanned devices to expected types from config.

    Returns ConfigValidationResult with count info and list of (position, expected, found).
    """
    mismatches: list[tuple[int, str, str]] = []
    missing: list[tuple[int, str]] = []
    count_expected = len(expected_types)
    count_found = len(device_infos)

    for i in range(min(count_expected, count_found)):
        expected = expected_types[i]
        if not expected:
            continue
        device = device_infos[i]
        found = _get_found_device_type(device, esi_lookup)
        if not found or found == _NA:
            continue  # Can't compare if we don't have a found type
        if expected.strip().upper() != found.strip().upper():
            mismatches.append((i, expected, found))

    # Missing: config expects more devices than scan found
    for i in range(count_found, count_expected):
        expected = expected_types[i]
        if expected:
            missing.append((i, expected))

    return ConfigValidationResult(
        count_expected=count_expected,
        count_found=count_found,
        mismatches=mismatches,
        missing=missing,
    )
