"""Collect device info from SII, optional CoE, state machine, and port status."""

from typing import Any

import pysoem

from ethercat_tool.models import EC_STATE_NAMES, DeviceInfo

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
    device: Any,
    index: int,
    subindex: int = 0,
    timeout_us: int = 500_000,
) -> str:
    """Read SDO as string; return N/A on any error."""
    try:
        raw = device.sdo_read(index, subindex, size=128)
        if not raw:
            return _NA
        return _decode_string(bytes(raw))
    except Exception:
        return _NA


def _read_port_status(device: Any) -> dict[str, str] | None:
    """Best-effort port status (A/B/C/D: carrier|no carrier|open|closed|N/A).

    Tries activeports (if exposed by PySOEM) then CoE 0xF030.
    """
    # Try PySOEM device activeports (bitmap: bit0=portA, bit1=portB, ...)
    # Per SOEM: bit set = "port open and communication established" (Carrier / Open)
    #           bit clear = port closed or no link (No Carrier / Closed)
    ap = getattr(device, "activeports", None)
    if ap is not None and isinstance(ap, int):
        result = {}
        for i, label in enumerate(["A", "B", "C", "D"]):
            if ap & (1 << i):
                result[label] = "carrier / open"
            else:
                result[label] = "no carrier / closed"
        return result if result else None

    # Fallback: try CoE 0xF030 Physical Layer (some devices)
    try:
        raw = device.sdo_read(0xF030, 1, size=4)
        if raw and len(raw) >= 4:
            val = int.from_bytes(bytes(raw)[:4], "little")
            result = {}
            for i, label in enumerate(["A", "B", "C", "D"]):
                if val & (1 << i):
                    result[label] = "carrier / open"
                else:
                    result[label] = "no carrier / closed"
            return result
    except Exception:
        pass
    return None


def _sdo_read_uint32(device: Any, index: int, subindex: int, timeout_us: int = 500_000) -> str:
    """Read SDO as uint32 and return as string; return N/A on error."""
    try:
        raw = device.sdo_read(index, subindex, size=4)
        if not raw or len(raw) < 4:
            return _NA
        val = int.from_bytes(bytes(raw)[:4], "little")
        return str(val)
    except Exception:
        return _NA


def collect_device_info(
    device: Any,
    *,
    coe: bool = True,
    timeout_ms: int = 500,
    diagnostics: dict[str, str] | None = None,
) -> DeviceInfo:
    """Build DeviceInfo from a PySOEM CdefSlave-like object (SII + optional CoE)."""
    timeout_us = timeout_ms * 1000
    name = getattr(device, "name", "") or _NA
    manufacturer_id = int(getattr(device, "man", 0))
    product_code = int(getattr(device, "id", 0))
    revision = int(getattr(device, "rev", 0))

    device_name = _NA
    hardware_version = _NA
    firmware_version = _NA
    bootloader_version = _NA
    serial_number = _NA

    if coe:
        device_name = _sdo_read_string(device, COE_DEVICE_NAME, 0, timeout_us)
        hardware_version = _sdo_read_string(device, COE_HARDWARE_VERSION, 0, timeout_us)
        firmware_version = _sdo_read_string(device, COE_SOFTWARE_VERSION, 0, timeout_us)
        bootloader_version = _sdo_read_string(device, COE_BOOTLOADER_VERSION, 0, timeout_us)
        # 0x1018 subindex 4 = serial number (uint32 often)
        serial_number = _sdo_read_uint32(device, COE_IDENTITY, 4, timeout_us)
        if serial_number == _NA:
            # Some devices use a string for serial
            serial_number = _sdo_read_string(device, COE_IDENTITY, 4, timeout_us)

    # State machine (always available from device after master.read_state)
    # Base state is in lower bits; bit 0x10 = EC_STATE_ACK (acknowledgment)
    state_raw = int(getattr(device, "state", 0))
    base_state = state_raw & 0x0F
    state_str = EC_STATE_NAMES.get(base_state, f"0x{state_raw:02X}")
    if state_raw & 0x10:  # EC_STATE_ACK
        state_str += " (ACK)"
    al_code = int(getattr(device, "al_status", 0))
    al_text = pysoem.al_status_code_to_string(al_code) if al_code else "OK"

    # Port status (best-effort)
    port_status = _read_port_status(device) if coe else None

    return DeviceInfo(
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
        state=state_str,
        al_status_code=al_code,
        al_status_text=al_text,
        port_status=port_status,
    )
