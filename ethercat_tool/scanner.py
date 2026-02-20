"""EtherCAT scan: open adapter, config_init, return slaves and link issues."""

import traceback
from typing import Any

import pysoem

from ethercat_tool.models import LinkIssue, TopologySummary


def scan(
    adapter_name: str,
    *,
    verbose: bool = False,
) -> tuple[list[Any], TopologySummary, list[LinkIssue]]:
    """Open adapter, run config_init(), return (slaves, summary, link_issues).

    Always closes the master in a finally block. Slaves are in topology order.
    When verbose=True, init failure messages include traceback and extra hints.
    """
    master = pysoem.Master()
    issues: list[LinkIssue] = []
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

        summary = TopologySummary(
            adapter_name=adapter_name,
            slave_count=slave_count,
            init_ok=init_ok,
        )
        return (list(master.slaves), summary, issues)
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
