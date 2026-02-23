"""Unit tests for report builder."""

from ethercat_tool.adapter_info import AdapterInfo
from ethercat_tool.esi_data import EsiLookupResult
from ethercat_tool.models import DeviceInfo, LinkIssue, TopologySummary
from ethercat_tool.report import build_markdown


def test_build_markdown_empty_chain() -> None:
    """Report with no devices and init failed."""
    summary = TopologySummary(adapter_name="eth0", device_count=0, init_ok=False)
    md = build_markdown(summary, [], [LinkIssue(None, "No devices found")])
    assert "EtherCAT Topology Report" in md
    assert "eth0" in md
    assert "**Devices found:** 0" in md
    assert "**Init status:** Failed" in md
    assert "No devices in chain" in md
    assert "Link / init issues" in md
    assert "No devices found" in md


def test_build_markdown_one_device_no_issues() -> None:
    """Report with one device and no link issues."""
    summary = TopologySummary(adapter_name="en0", device_count=1, init_ok=True)
    device = DeviceInfo(
        name="EL1008",
        manufacturer_id=0x00000002,
        product_code=0x03F03052,
        revision=0x00110000,
        device_name="EL1008",
        hardware_version="1",
        firmware_version="01",
        bootloader_version="00",
        serial_number="",
        diagnostics=None,
        state="PRE-OP",
        al_status_code=0,
        al_status_text="OK",
        port_status={"A": "carrier", "B": "no carrier"},
    )
    md = build_markdown(summary, [device], [])
    assert "**Devices found:** 1" in md
    assert "**Init status:** OK" in md
    assert "Master → [EL1008]" in md
    assert "Device 0: EL1008" in md
    assert "EL1008" in md
    assert "00000002" in md or "2" in md
    assert "Link / init issues" not in md


def test_build_markdown_multiple_devices_with_issues() -> None:
    """Report with multiple devices and link issues."""
    summary = TopologySummary(adapter_name="eth0", device_count=2, init_ok=True)
    devices = [
        DeviceInfo(
            name="AX5000",
            manufacturer_id=0x00000001,
            product_code=0x0,
            revision=0,
            device_name="AX5000",
            hardware_version="",
            firmware_version="",
            bootloader_version="",
            serial_number="123",
            diagnostics=None,
            state="OP",
            al_status_code=0,
            al_status_text="OK",
            port_status=None,
        ),
        DeviceInfo(
            name="EL1008",
            manufacturer_id=0x2,
            product_code=0x3F03052,
            revision=0x110000,
            device_name="EL1008",
            hardware_version="1",
            firmware_version="01",
            bootloader_version="00",
            serial_number="",
            diagnostics={"RX errors": "0"},
            state="PRE-OP",
            al_status_code=0,
            al_status_text="OK",
            port_status={"A": "carrier", "B": "carrier"},
        ),
    ]
    issues = [LinkIssue(1, "Device did not reach OP")]
    md = build_markdown(summary, devices, issues)
    assert "**Devices found:** 2" in md
    assert "[AX5000] → [EL1008]" in md
    assert "Device 0: AX5000" in md
    assert "Device 1: EL1008" in md
    assert "RX errors" in md
    assert "Link / init issues" in md
    assert "Device 1:" in md
    assert "Device did not reach OP" in md


def test_build_markdown_writes_file(tmp_path: str) -> None:
    """build_markdown with output_path writes file and returns same string."""
    summary = TopologySummary(adapter_name="eth0", device_count=0, init_ok=False)
    out = tmp_path / "report.md"
    md = build_markdown(summary, [], [], output_path=str(out))
    assert out.read_text() == md
    assert "EtherCAT Topology Report" in md


def test_build_markdown_with_esi_lookup() -> None:
    """Report decodes manufacturer and product when ESI lookup available."""
    summary = TopologySummary(adapter_name="eth0", device_count=1, init_ok=True)
    device = DeviceInfo(
        name="EL1008",
        manufacturer_id=0x00000002,
        product_code=0x044C2C52,
        revision=0x00100000,
        device_name="EL1008",
        hardware_version="",
        firmware_version="",
        bootloader_version="",
        serial_number="",
        diagnostics=None,
        state="PRE-OP",
        al_status_code=0,
        al_status_text="OK",
        port_status=None,
    )
    esi_lookup = {
        (2, 0x044C2C52, 0x00100000): EsiLookupResult(
            manufacturer_name="Beckhoff Automation GmbH & Co. KG",
            product_name="EL1008 8-channel digital input",
            device_type="EL1008",
            url=None,
        ),
    }
    md = build_markdown(summary, [device], [], esi_lookup=esi_lookup)
    assert "Beckhoff Automation GmbH & Co. KG" in md
    assert "EL1008 8-channel digital input" in md


def test_build_markdown_includes_adapter_details() -> None:
    """Report includes adapter details when available."""
    adapter_info = AdapterInfo(
        name="en7",
        mac_address="AA:BB:CC:DD:EE:FF",
        link_state="active",
        link_speed="1000 Mb/s full-duplex",
        hardware_port="Thunderbolt Ethernet",
        mtu="1500",
    )
    summary = TopologySummary(
        adapter_name="en7",
        device_count=0,
        init_ok=False,
        adapter_info=adapter_info,
    )
    md = build_markdown(summary, [], [])
    assert "**Adapter:** en7" in md
    assert "Adapter details:" in md
    assert "MAC Address: AA:BB:CC:DD:EE:FF" in md
    assert "Link State: active" in md
    assert "Link Speed: 1000 Mb/s full-duplex" in md
    assert "Hardware Port: Thunderbolt Ethernet" in md
