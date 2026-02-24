# ethercat-tool

EtherCAT network troubleshooting: scan devices, topology map (markdown), and link diagnostics.

- **Cross-platform:** macOS, Windows (with Npcap), Linux (with privileges)
- **One-shot CLI:** list adapters, scan an adapter, print or save a markdown report, then exit

**Tested with:** Python 3.13.12 on Windows • Python 3.12.9 on macOS

## Install

### 1. Install Python

If you don’t have Python installed:

- **Windows:** Download the installer from [python.org/downloads](https://www.python.org/downloads/). Run it and check **“Add Python to PATH”** before finishing.
- **macOS:** Use Homebrew (`brew install python`) or download from [python.org/downloads](https://www.python.org/downloads/).
- **Linux:** Use your package manager (e.g. `sudo apt install python3 python3-pip` on Ubuntu/Debian).

Check the install:

```bash
python --version
```

You should see Python 3.10 or newer.

### 2. Clone the repository

```bash
git clone https://github.com/dbrowngm/ethercat-tool.git
cd ethercat-tool
```

### 3. (Recommended) Create a virtual environment

A virtual environment keeps this project’s dependencies separate from your system Python.

```bash
python -m venv venv
```

Then activate it:

- **Windows (Command Prompt):** `venv\Scripts\activate`
- **Windows (PowerShell):** `venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source venv/bin/activate`

You’ll see `(venv)` at the start of your prompt when it’s active.

### 4. Install the tool

With the virtual environment activated (or using your system Python):

```bash
pip install -e .
```

`pip` installs the Python packages. The `-e` flag installs the tool in “editable” mode so changes in the source take effect without reinstalling.

### Platform requirements

- **Windows:** [Npcap](https://nmap.org/npcap/) or WinPcap (for raw Ethernet). Use `--list-adapters` to see adapters. You can use the **index** (0, 1, 2…) instead of the full device ID: `--adapter 0`.
- **Linux:** Run with sufficient privileges (e.g. root or `cap_net_raw`). Adapter names: `eth0`, etc.
- **macOS:** PySOEM 1.1.5+; a compatible NIC/driver may be needed (e.g. USB-Ethernet). Use `--list-adapters` to see available interfaces.

If opening the adapter fails with a permission-style error, the tool will **automatically re-run once under `sudo`** (you may be prompted for your password). Use `--no-elevate` to disable this and see the raw error instead.

## Usage

List available network adapters:

```bash
python -m ethercat_tool --list-adapters
```

Output shows index, description, and device path. On Windows, use the index (e.g. `--adapter 0`) instead of copying the full GUID.

Scan an adapter (report is saved to `ethercat-scan-{timestamp}.md`):

```bash
python -m ethercat_tool --adapter eth0
# Windows: python -m ethercat_tool --adapter 0
```

Print the report to stdout instead of saving to a file:

```bash
python -m ethercat_tool --adapter eth0 --print
```

Faster scan (topology and SII only, no CoE reads):

```bash
python -m ethercat_tool --adapter eth0 --no-coe
```

SDO read timeout (default 500 ms):

```bash
python -m ethercat_tool --adapter eth0 --timeout-ms 300
```

Validate scan against a TwinCAT EtherCAT config file (checks Device Name vs ProductRevision):

```bash
python -m ethercat_tool --adapter eth0 --validate-config config.xml
```

Mismatches are reported as `Expected: EL1014, Found: EL2904` (for example) and included in the report.

**To obtain the config XML from TwinCAT:** Double-click the EtherCAT master under I/O and Devices, go to the EtherCAT tab, then click **Export Configuration File**.

More detail when init fails (traceback and hints):

```bash
python -m ethercat_tool --adapter eth0 -v
# or --verbose
```

### ESI device database (decode manufacturer / product names)

The scan report can decode manufacturer ID and product code to human-readable names (e.g. "2 — Beckhoff Automation GmbH", "0x044C2C52 — EL1008") using the EtherCAT device database (ESI data) from [linuxcnc-ethercat/esi-data](https://github.com/linuxcnc-ethercat/esi-data).

**First-time setup:** Download the ESI database (one-time, ~44 MB). Re-running replaces any existing data:

```bash
python -m ethercat_tool --fetch-esi
```

**Automatic prompt:** If no ESI data is present and you run a scan interactively, the tool will prompt: "No ESI device data found. Decode manufacturer/product names? [y/N]". Answer `y` to download.

**Without prompt:** Use `--no-esi-prompt` to skip the prompt and always use raw IDs only.

Data is stored in `~/.local/share/ethercat-tool/` (or `%LOCALAPPDATA%\ethercat-tool` on Windows). The device index (cache) is built when you run `--fetch-esi`, not during scan. If the cache is missing at scan time, a warning is printed but the scan continues with raw IDs.

## Report contents

- **Summary:** adapter name, timestamp, device count, init status
- **Topology:** chain order (Master → [Device0] → [Device1] → …) and per-device details:
  - Manufacturer ID, Product Code, Revision (decoded to names when ESI data is available)
  - Device name, hardware/firmware/bootloader version, serial (from CoE when available)
  - **State** (INIT, PRE-OP, SAFE-OP, OP) and **AL Status** (Application Layer status code)
  - **Port status** (A/B/C/D: carrier/closed vs no carrier/open) when available
  - **Per-port CRC counters** (RXERR and Fwd CRC for ports A/B/C/D) and link-loss count, read from ESC registers—same data TwinCAT shows
  - Optional CoE diagnostic objects when the device exposes them
- **Link / init issues:** init failures, “no devices found”, or other errors

## Troubleshooting init errors (e.g. on USB NIC / en0, en7)

If you see an init error (e.g. "could not open interface en7" or "No devices found"):

1. **Permissions (macOS / Linux):** The tool will normally re-run under `sudo` automatically when it gets a permission error. If you prefer to run sudo yourself or disable auto-elevate, use `--no-elevate`.
2. **Interface name:** Confirm the name with `--list-adapters` (e.g. `en7`). On macOS, USB Ethernet often shows as `en` + number.
3. **USB NICs on macOS:** Some USB Ethernet adapters or drivers do not expose raw sockets to the OS. If `sudo` doesn’t help, the adapter may be unsupported for EtherCAT on macOS; try a different USB NIC or a built-in Ethernet port if available.
4. **Cabling and devices:** "No devices found" can mean the adapter opened but no devices replied: check cable, power, and that devices are in PRE-OP (power cycle the chain if needed).

The exact error is always in the report under **Link / init issues** and is also printed to stderr. Use **`-v` / `--verbose`** to include a full traceback and extra hints when init fails.

**“No devices found” with working counter -1:** The master got **no valid reply** from the segment (frame didn’t come back or was invalid). Usually means: nothing is connected to the adapter’s port, the cable is unplugged or wrong port, devices have no power, or you’re plugged into a **switch** (EtherCAT is a line—no switches). Fix: connect the NIC directly to the first device's upstream port; power the chain; ensure the first device is in PRE-OP (power-cycle if needed).

**“No devices found” with working counter 0:** The frame went out and back but **no devices responded**. Check cabling and that all devices are powered and in PRE-OP.

## Limitations

- **Link/CRC diagnostics:** Per-port CRC counters (RXERR, Fwd CRC) and link-loss are read from ESC registers via FPRD—available on all standard EtherCAT slaves, same as TwinCAT. Some older or custom ESC implementations may not support this; the tool falls back gracefully. Optional CoE diagnostic objects are also read when present (best-effort).
- **Port status:** Port A/B/C/D (carrier/closed vs no carrier/open) is read from the device when PySOEM exposes `activeports` or the device supports CoE 0xF030; otherwise it is omitted.
- **Real-time:** This tool is for troubleshooting only. It does not provide real-time cycle or distributed clock sync.
