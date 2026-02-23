"""Best-effort read of link/diagnostic CoE objects.

Many EtherCAT devices do not expose link lost or RX error counters via CoE;
the main link health signal is init success and working counter.
When present, device-specific indices may be tried here.
"""

from typing import Any


def read_diagnostics(device: Any, timeout_ms: int = 300) -> dict[str, str] | None:
    """Read best-effort diagnostic counters from device via CoE.

    Returns a dict of label -> value when any read succeeds, or None.
    Many devices do not support these objects; treat as optional.
    """
    _ = timeout_ms  # reserved for per-call timeout when supported
    result: dict[str, str] = {}

    # Optional: try common or vendor-specific diagnostic indices.
    # Example placeholders (not all devices implement these):
    # - Some use 0x10F3 subindex 2 for "Link loss count" (uint32)
    # - Device-specific objects vary; extend as needed.
    candidates: list[tuple[int, int, str]] = [
        # (index, subindex, label)
        (0x10F3, 2, "Link loss count"),
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
