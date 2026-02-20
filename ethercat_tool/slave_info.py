"""Collect slave info from SII and optional CoE (device name, firmware, etc.)."""

from typing import Any

from ethercat_tool.models import SlaveInfo

# CoE standard object indices (CANopen over EtherCAT)
COE_DEVICE_NAME = 0x1008
COE_HARDWARE_VERSION = 0x1009
COE_SOFTWARE_VERSION = 0x100A
COE_BOOTLOADER_VERSION = 0x100B
COE_IDENTITY = 0x1018  # subindex 1=vendor, 2=product, 3=revision, 4=serial

_NA = "N/A"


def _decode_string(raw: bytes) -> str:
    """Decode CoE string (strip nulls and decode)."""
    if not raw:
        return _NA
    try:
        return raw.rstrip(b"\x00").decode("utf-8", errors="replace").strip() or _NA
    except Exception:
        return _NA


def _sdo_read_string(
    slave: Any,
    index: int,
    subindex: int = 0,
    timeout_us: int = 500_000,
) -> str:
    """Read SDO as string; return N/A on any error."""
    try:
        raw = slave.sdo_read(index, subindex, size=128)
        if not raw:
            return _NA
        return _decode_string(bytes(raw))
    except Exception:
        return _NA


def _sdo_read_uint32(slave: Any, index: int, subindex: int, timeout_us: int = 500_000) -> str:
    """Read SDO as uint32 and return as string; return N/A on error."""
    try:
        raw = slave.sdo_read(index, subindex, size=4)
        if not raw or len(raw) < 4:
            return _NA
        val = int.from_bytes(bytes(raw)[:4], "little")
        return str(val)
    except Exception:
        return _NA


def collect_slave_info(
    slave: Any,
    *,
    coe: bool = True,
    timeout_ms: int = 500,
    diagnostics: dict[str, str] | None = None,
) -> SlaveInfo:
    """Build SlaveInfo from a PySOEM CdefSlave-like object (SII + optional CoE)."""
    timeout_us = timeout_ms * 1000
    name = getattr(slave, "name", "") or _NA
    manufacturer_id = int(getattr(slave, "man", 0))
    product_code = int(getattr(slave, "id", 0))
    revision = int(getattr(slave, "rev", 0))

    device_name = _NA
    hardware_version = _NA
    firmware_version = _NA
    bootloader_version = _NA
    serial_number = _NA

    if coe:
        device_name = _sdo_read_string(slave, COE_DEVICE_NAME, 0, timeout_us)
        hardware_version = _sdo_read_string(slave, COE_HARDWARE_VERSION, 0, timeout_us)
        firmware_version = _sdo_read_string(slave, COE_SOFTWARE_VERSION, 0, timeout_us)
        bootloader_version = _sdo_read_string(slave, COE_BOOTLOADER_VERSION, 0, timeout_us)
        # 0x1018 subindex 4 = serial number (uint32 often)
        serial_number = _sdo_read_uint32(slave, COE_IDENTITY, 4, timeout_us)
        if serial_number == _NA:
            # Some devices use a string for serial
            serial_number = _sdo_read_string(slave, COE_IDENTITY, 4, timeout_us)

    return SlaveInfo(
        name=name,
        manufacturer_id=manufacturer_id,
        product_code=product_code,
        revision=revision,
        device_name=device_name,
        hardware_version=hardware_version,
        firmware_version=firmware_version,
        bootloader_version=bootloader_version,
        serial_number=serial_number,
        diagnostics=diagnostics,
    )
