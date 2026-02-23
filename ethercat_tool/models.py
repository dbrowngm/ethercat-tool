"""Data types for topology scan and report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ethercat_tool.adapter_info import AdapterInfo

# EtherCAT state machine states (EC_STATE_* values from SOEM)
EC_STATE_NAMES: dict[int, str] = {
    0: "NONE",
    1: "INIT",
    2: "PRE-OP",
    3: "BOOT",
    4: "SAFE-OP",
    8: "OP",
}


@dataclass(frozen=True)
class SlaveInfo:
    """Per-slave information for the report (SII + optional CoE)."""

    name: str
    manufacturer_id: int
    product_code: int
    revision: int
    device_name: str  # CoE 0x1008 or N/A
    hardware_version: str
    firmware_version: str
    bootloader_version: str
    serial_number: str
    diagnostics: dict[str, str] | None  # best-effort link/error counters
    # State machine
    state: str  # e.g. PRE-OP, OP
    al_status_code: int  # raw AL status
    al_status_text: str  # human-readable from al_status_code_to_string
    # Port status: {"A": "carrier"|"no carrier"|"open"|"closed"|"N/A", ...}
    port_status: dict[str, str] | None


@dataclass(frozen=True)
class TopologySummary:
    """Summary of the scan (adapter, count, init status)."""

    adapter_name: str
    slave_count: int
    init_ok: bool  # True if config_init found at least one slave and no fatal error
    adapter_info: AdapterInfo | None = None  # Optional NIC details (MAC, link speed, etc.)


@dataclass(frozen=True)
class LinkIssue:
    """A link or init issue (optional slave index)."""

    slave_index: int | None  # None = master/global
    message: str
