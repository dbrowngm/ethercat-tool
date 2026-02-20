"""EtherCAT scan: open adapter, config_init, return slaves and link issues."""

from typing import Any

import pysoem

from ethercat_tool.models import LinkIssue, TopologySummary


def scan(adapter_name: str) -> tuple[list[Any], TopologySummary, list[LinkIssue]]:
    """Open adapter, run config_init(), return (slaves, summary, link_issues).

    Always closes the master in a finally block. Slaves are in topology order.
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
                issues.append(LinkIssue(None, "No slaves found"))
            else:
                issues.append(LinkIssue(None, f"config_init returned wkc={wkc}"))

        summary = TopologySummary(
            adapter_name=adapter_name,
            slave_count=slave_count,
            init_ok=init_ok,
        )
        return (list(master.slaves), summary, issues)
    except Exception as e:
        issues.append(LinkIssue(None, f"Init failed: {e}"))
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
