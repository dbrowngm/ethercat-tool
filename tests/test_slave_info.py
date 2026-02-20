"""Unit tests for slave_info module."""

from unittest.mock import MagicMock

from ethercat_tool.slave_info import collect_slave_info


def test_collect_slave_info_no_coe() -> None:
    """Without CoE we only get SII fields; SDO is not called."""
    slave = MagicMock()
    slave.name = "EL1008"
    slave.man = 0x00000002
    slave.id = 0x03F03052
    slave.rev = 0x00110000

    info = collect_slave_info(slave, coe=False)

    assert info.name == "EL1008"
    assert info.manufacturer_id == 0x00000002
    assert info.product_code == 0x03F03052
    assert info.revision == 0x00110000
    assert info.device_name == "N/A"
    assert info.firmware_version == "N/A"
    assert info.serial_number == "N/A"
    assert info.diagnostics is None
    slave.sdo_read.assert_not_called()


def test_collect_slave_info_with_coe_success() -> None:
    """With CoE, SDO reads are used and decoded."""
    slave = MagicMock()
    slave.name = "EL1008"
    slave.man = 2
    slave.id = 0x03F03052
    slave.rev = 0x110000

    def sdo_read(index: int, subindex: int, size: int = 0) -> bytes:
        if index == 0x1008:
            return b"EL1008\x00"
        if index == 0x1009:
            return b"HW1\x00"
        if index == 0x100A:
            return b"01\x00"
        if index == 0x100B:
            return b"00\x00"
        if index == 0x1018 and subindex == 4:
            return (12345).to_bytes(4, "little")
        return b""

    slave.sdo_read = sdo_read

    info = collect_slave_info(slave, coe=True)

    assert info.device_name == "EL1008"
    assert info.hardware_version == "HW1"
    assert info.firmware_version == "01"
    assert info.bootloader_version == "00"
    assert info.serial_number == "12345"


def test_collect_slave_info_sdo_raises_returns_na() -> None:
    """When SDO read raises, we get N/A and no exception."""
    slave = MagicMock()
    slave.name = "X"
    slave.man = 0
    slave.id = 0
    slave.rev = 0
    slave.sdo_read.side_effect = Exception("object not found")

    info = collect_slave_info(slave, coe=True)

    assert info.device_name == "N/A"
    assert info.firmware_version == "N/A"
    assert info.serial_number == "N/A"


def test_collect_slave_info_with_diagnostics_injected() -> None:
    """Optional diagnostics dict is passed through to SlaveInfo."""
    slave = MagicMock()
    slave.name = "S"
    slave.man = 0
    slave.id = 0
    slave.rev = 0

    info = collect_slave_info(
        slave,
        coe=False,
        diagnostics={"RX errors": "0", "Link lost": "1"},
    )

    assert info.diagnostics is not None
    assert info.diagnostics["RX errors"] == "0"
    assert info.diagnostics["Link lost"] == "1"


def test_collect_slave_info_missing_attributes_defaults() -> None:
    """Empty SII name becomes N/A; missing attrs default to 0."""

    class MinimalSlave:
        name = ""
        man = 0
        id = 0
        rev = 0

    info = collect_slave_info(MinimalSlave(), coe=False)
    assert info.name == "N/A"
    assert info.manufacturer_id == 0
    assert info.product_code == 0
    assert info.revision == 0
