# ethercat-tool

EtherCAT network troubleshooting: scan slaves, topology map (markdown), and link diagnostics.

- **Cross-platform:** macOS, Windows (with Npcap), Linux (with privileges)
- **One-shot CLI:** list adapters, scan an adapter, print or save a markdown report, then exit

## Install

```bash
pip install -e .
# or from PyPI when published:
# pip install ethercat-tool
```

### Platform requirements

- **Windows:** [Npcap](https://nmap.org/npcap/) or WinPcap (for raw Ethernet). Adapter names are device IDs (use `--list-adapters`).
- **Linux:** Run with sufficient privileges (e.g. root or `cap_net_raw`). Adapter names: `eth0`, etc.
- **macOS:** PySOEM 1.1.5+; a compatible NIC/driver may be needed (e.g. USB-Ethernet). Use `--list-adapters` to see available interfaces.

If opening the adapter fails with a permission-style error, the tool will **automatically re-run once under `sudo`** (you may be prompted for your password). Use `--no-elevate` to disable this and see the raw error instead.

## Usage

List available network adapters:

```bash
ethercat-tool --list-adapters
# or: python -m ethercat_tool --list-adapters
```

Scan an adapter and print a markdown report to stdout:

```bash
ethercat-tool --adapter eth0
```

Write the report to a file:

```bash
ethercat-tool --adapter eth0 --output report.md
```

Faster scan (topology and SII only, no CoE reads):

```bash
ethercat-tool --adapter eth0 --no-coe
```

SDO read timeout (default 500 ms):

```bash
ethercat-tool --adapter eth0 --timeout-ms 300
```

## Report contents

- **Summary:** adapter name, timestamp, slave count, init status
- **Topology:** chain order (Master → [Slave0] → [Slave1] → …) and per-slave details:
  - Manufacturer ID, Product Code, Revision
  - Device name, hardware/firmware/bootloader version, serial (from CoE when available)
  - Optional diagnostic counters (link loss, etc.) when the device exposes them
- **Link / init issues:** init failures, “no slaves found”, or other errors

## Troubleshooting init errors (e.g. on USB NIC / en0, en7)

If you see an init error (e.g. "could not open interface en7" or "No slaves found"):

1. **Permissions (macOS / Linux):** The tool will normally re-run under `sudo` automatically when it gets a permission error. If you prefer to run sudo yourself or disable auto-elevate, use `--no-elevate`.
2. **Interface name:** Confirm the name with `--list-adapters` (e.g. `en7`). On macOS, USB Ethernet often shows as `en` + number.
3. **USB NICs on macOS:** Some USB Ethernet adapters or drivers do not expose raw sockets to the OS. If `sudo` doesn’t help, the adapter may be unsupported for EtherCAT on macOS; try a different USB NIC or a built-in Ethernet port if available.
4. **Cabling and slaves:** "No slaves found" can mean the adapter opened but no slaves replied: check cable, power, and that slaves are in PRE-OP (power cycle the chain if needed).

The exact error is always in the report under **Link / init issues** and is also printed to stderr.

## Limitations

- **Link/CRC diagnostics:** Many EtherCAT slaves do not expose link-loss or RX error counters via CoE. The tool reports init success/failure and working counter; optional CoE diagnostic objects are read when present (best-effort).
- **Real-time:** This tool is for troubleshooting only. It does not provide real-time cycle or distributed clock sync.
