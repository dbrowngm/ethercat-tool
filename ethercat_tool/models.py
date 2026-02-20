"""Data types for topology scan and report."""

from dataclasses import dataclass


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


@dataclass(frozen=True)
class TopologySummary:
    """Summary of the scan (adapter, count, init status)."""

    adapter_name: str
    slave_count: int
    init_ok: bool  # True if config_init found at least one slave and no fatal error


@dataclass(frozen=True)
class LinkIssue:
    """A link or init issue (optional slave index)."""

    slave_index: int | None  # None = master/global
    message: str
