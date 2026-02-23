"""Best-effort read of link/diagnostic counters.

- ESC registers (RXERR, FRXERR, LLCNT): read via FPRD from every slave's EtherCAT
  Slave Controller. Always available on standard ESCs; same data TwinCAT shows.
- CoE objects: optional device-specific indices; many devices do not implement these.
"""

from typing import Any

# ESC register addresses (EtherCAT Slave Controller - standard hardware)
_ECT_REG_RXERR = 0x0300   # RX error (CRC) counters, 8 bytes, 4× uint16 for ports A–D
_ECT_REG_FRXERR = 0x0308  # Forwarded RX error counters, 8 bytes
_ECT_REG_LLCNT = 0x0310   # Link loss counter, 1 byte


def read_esc_port_diagnostics(device: Any, timeout_ms: int = 300) -> dict[str, str] | None:
    """Read per-port CRC and link-loss counters from ESC registers via FPRD.

    Uses device._fprd() (PySOEM internal) to read standard EtherCAT Slave Controller
    registers. Same data TwinCAT displays for every device. Returns None if _fprd
    is unavailable or any read fails.
    """
    fprd = getattr(device, "_fprd", None)
    if fprd is None:
        return None
    timeout_us = timeout_ms * 1000
    result: dict[str, str] = {}
    try:
        # RXERR: 8 bytes = 4 × uint16 (ports A, B, C, D)
        raw = fprd(_ECT_REG_RXERR, 8, timeout_us)
        if raw and len(raw) >= 8:
            vals = [int.from_bytes(raw[i : i + 2], "little") for i in range(0, 8, 2)]
            result["CRC (Port A/B/C/D)"] = " / ".join(str(v) for v in vals)
        # FRXERR: 8 bytes = 4 × uint16
        raw = fprd(_ECT_REG_FRXERR, 8, timeout_us)
        if raw and len(raw) >= 8:
            vals = [int.from_bytes(raw[i : i + 2], "little") for i in range(0, 8, 2)]
            result["Fwd CRC (Port A/B/C/D)"] = " / ".join(str(v) for v in vals)
        # LLCNT: 1 byte
        raw = fprd(_ECT_REG_LLCNT, 1, timeout_us)
        if raw and len(raw) >= 1:
            result["Link loss"] = str(raw[0])
    except Exception:
        return None
    return result if result else None


def read_diagnostics(device: Any, timeout_ms: int = 300) -> dict[str, str] | None:
    """Read diagnostic counters: ESC registers (CRC, link loss) and optional CoE objects.

    ESC diagnostics (FPRD) are available on all standard EtherCAT slaves.
    CoE diagnostics are device-specific; many devices do not implement them.
    Merges both sources; ESC takes precedence for overlapping info.
    """
    result: dict[str, str] = {}

    # 1. ESC registers: always try first (same data as TwinCAT)
    esc = read_esc_port_diagnostics(device, timeout_ms)
    if esc:
        result.update(esc)

    # 2. CoE: optional device-specific diagnostic indices
    candidates: list[tuple[int, int, str]] = [
        (0x10F3, 2, "Link loss (CoE)"),  # some devices expose via CoE
    ]
    for index, subindex, label in candidates:
        try:
            raw = device.sdo_read(index, subindex, size=4)
            if raw and len(raw) >= 4:
                val = int.from_bytes(bytes(raw)[:4], "little")
                result[label] = str(val)
        except Exception:
            continue

    return result if result else None
