"""EtherCAT scan: open adapter, config_init, collect slave info (CoE while open), return results."""

import traceback

import pysoem

from ethercat_tool.diagnostics import read_diagnostics
from ethercat_tool.models import LinkIssue, SlaveInfo, TopologySummary
from ethercat_tool.slave_info import collect_slave_info


def scan(
    adapter_name: str,
    *,
    verbose: bool = False,
    coe: bool = True,
    timeout_ms: int = 500,
) -> tuple[list[SlaveInfo], TopologySummary, list[LinkIssue]]:
    """Open adapter, config_init(), collect slave info (CoE reads while master is open), return.

    Always closes the master in a finally block. CoE reads (device name, firmware, etc.)
    are done while the master is still open; previously they ran after close, causing N/A.
    """
    master = pysoem.Master()
    issues: list[LinkIssue] = []
    slave_infos: list[SlaveInfo] = []
    try:
        master.open(adapter_name)
        wkc = master.config_init()
        slave_count = len(master.slaves)
        init_ok = wkc > 0 and slave_count > 0

        if not init_ok:
            if slave_count == 0:
                # wkc -1 = no valid reply (frame not returned); wkc 0 = reply but no slaves
                if wkc == -1:
                    msg = (
                        "No slaves found (working counter = -1: no valid reply from the segment). "
                        "The master did not receive a proper response. Check: adapter connected to "
                        "the EtherCAT segment (not a switch); cabling; slave power; first slave "
                        "in PRE-OP."
                    )
                else:
                    msg = (
                        f"No slaves found (working counter = {wkc}). "
                        "Check: cabling, slave power, and that slaves are in PRE-OP."
                    )
                if verbose:
                    msg += f" [config_init() returned {wkc}]"
                issues.append(LinkIssue(None, msg))
            else:
                issues.append(
                    LinkIssue(None, f"config_init returned wkc={wkc} (expected > 0)")
                )
        else:
            # CoE reads must happen while master is open; set SDO timeout
            master.sdo_read_timeout = timeout_ms * 1000  # us
            for slave in master.slaves:
                diag = read_diagnostics(slave, timeout_ms=timeout_ms) if coe else None
                info = collect_slave_info(
                    slave,
                    coe=coe,
                    timeout_ms=timeout_ms,
                    diagnostics=diag,
                )
                slave_infos.append(info)

        summary = TopologySummary(
            adapter_name=adapter_name,
            slave_count=slave_count,
            init_ok=init_ok,
        )
        return (slave_infos, summary, issues)
    except Exception as e:
        msg = f"Init failed: {e}"
        if verbose:
            msg += "\n\nTraceback:\n" + traceback.format_exc()
        issues.append(LinkIssue(None, msg))
        summary = TopologySummary(
            adapter_name=adapter_name,
            slave_count=0,
            init_ok=False,
        )
        return ([], summary, issues)
    finally:
        try:
            master.close()
        except Exception:
            pass
