---
name: Bug report
about: Report a problem or regression in ethercat-tool
labels: bug
---

## Summary

Briefly describe the bug.

## Environment

- OS: (e.g. Windows 11, Ubuntu 22.04, macOS 15)
- Python version: (`python --version`)
- ethercat-tool version: (`python -m ethercat_tool --version` or `pip show ethercat-tool`)
- How installed: (pip / editable `pip install -e .` / other)

## EtherCAT setup

- Adapter type/name (e.g. USB NIC model, `en7`, `eth0`, adapter index on Windows)
- Approximate device chain (e.g. EK1100 → EL1014 → EL2004 → …)
- TwinCAT or other configuration file used? (`--validate-config`), if applicable

## Steps to reproduce

1. …
2. …
3. …

## Expected behaviour

What you expected to happen.

## Actual behaviour

What actually happened (include full error message or traceback if available).

```text
<paste traceback or error output here>
```

## Additional context

Attach or paste:

- Relevant excerpts from a report (see `EXAMPLE-REPORT.md` for structure)
- Sanitised configuration snippets (with any sensitive names redacted)
- Screenshots, if helpful

