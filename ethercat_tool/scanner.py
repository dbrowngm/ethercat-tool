"""EtherCAT scan: open adapter, config_init, collect device info (CoE while open), return results."""

import traceback

import pysoem

from ethercat_tool.adapter_info import get_adapter_info
from ethercat_tool.diagnostics import read_diagnostics
from ethercat_tool.models import DeviceInfo, LinkIssue, TopologySummary
from ethercat_tool.device_info import collect_device_info


def scan(
    adapter_name: str,
    *,
    verbose: bool = False,
    coe: bool = True,
    timeout_ms: int = 500,
) -> tuple[list[DeviceInfo], TopologySummary, list[LinkIssue]]:
    """Open adapter, config_init(), collect device info (CoE reads while master is open), return.

    Always closes the master in a finally block. CoE reads (device name, firmware, etc.)
    are done while the master is still open; previously they ran after close, causing N/A.
    """
    master = pysoem.Master()
    issues: list[LinkIssue] = []
    device_infos: list[DeviceInfo] = []
    try:
        master.open(adapter_name)
        wkc = master.config_init()
        device_count = len(master.slaves)
        init_ok = wkc > 0 and device_count > 0

        if not init_ok:
            if device_count == 0:
                # wkc -1 = no valid reply (frame not returned); wkc 0 = reply but no devices
                if wkc == -1:
                    msg = (
                        "No devices found (working counter = -1: no valid reply from the segment). "
                        "The master did not receive a proper response. Check: adapter connected to "
                        "the EtherCAT segment (not a switch); cabling; device power; first device "
                        "in PRE-OP."
                    )
                else:
                    msg = (
                        f"No devices found (working counter = {wkc}). "
                        "Check: cabling, device power, and that devices are in PRE-OP."
                    )
                if verbose:
                    msg += f" [config_init() returned {wkc}]"
                issues.append(LinkIssue(None, msg))
            else:
                issues.append(
                    LinkIssue(None, f"config_init returned wkc={wkc} (expected > 0)")
                )
        else:
            # Refresh device states from network (for state machine and AL status)
            master.read_state()
            # CoE reads must happen while master is open; set SDO timeout
            master.sdo_read_timeout = timeout_ms * 1000  # us
            for device in master.slaves:
                diag = read_diagnostics(device, timeout_ms=timeout_ms) if coe else None
                info = collect_device_info(
                    device,
                    coe=coe,
                    timeout_ms=timeout_ms,
                    diagnostics=diag,
                )
                device_infos.append(info)

        adapter_info = get_adapter_info(adapter_name)
        summary = TopologySummary(
            adapter_name=adapter_name,
            device_count=device_count,
            init_ok=init_ok,
            adapter_info=adapter_info,
        )
        return (device_infos, summary, issues)
    except Exception as e:
        msg = f"Init failed: {e}"
        if verbose:
            msg += "\n\nTraceback:\n" + traceback.format_exc()
        issues.append(LinkIssue(None, msg))
        adapter_info = get_adapter_info(adapter_name)
        summary = TopologySummary(
            adapter_name=adapter_name,
            device_count=0,
            init_ok=False,
            adapter_info=adapter_info,
        )
        return ([], summary, issues)
    finally:
        try:
            master.close()
        except Exception:
            pass
