"""Tests for ESI data module."""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from ethercat_tool.esi_data import (
    EsiLookupResult,
    _build_lookup_from_yaml,
    _parse_hex,
    get_esi_paths,
    has_esi_data,
    load_esi_lookup,
    lookup_device,
)


def test_parse_hex() -> None:
    assert _parse_hex("0x00000002") == 2
    assert _parse_hex("0x044C2C52") == 0x044C2C52
    assert _parse_hex(42) == 42
    assert _parse_hex("invalid") == -1


def test_lookup_device_exact_match() -> None:
    lookup = {
        (2, 0x044C2C52, 0x00100000): EsiLookupResult(
            "Beckhoff", "EL1008", "EL1008", None
        ),
    }
    r = lookup_device(lookup, 2, 0x044C2C52, 0x00100000)
    assert r is not None
    assert r.manufacturer_name == "Beckhoff"
    assert r.product_name == "EL1008"


def test_lookup_device_fallback() -> None:
    lookup = {
        (2, 0x044C2C52, 0x00100000): EsiLookupResult(
            "Beckhoff", "EL1008", "EL1008", None
        ),
        (2, 0x044C2C52, 0): EsiLookupResult(
            "Beckhoff", "EL1008", "EL1008", None
        ),
    }
    r = lookup_device(lookup, 2, 0x044C2C52, 0x00110000)
    assert r is not None
    assert r.product_name == "EL1008"


def test_lookup_device_no_match() -> None:
    lookup = {(2, 0x044C2C52, 0x00100000): EsiLookupResult("B", "E", "E", None)}
    assert lookup_device(lookup, 999, 0, 0) is None


def test_build_lookup_from_yaml() -> None:
    data = [
        {
            "IDs": [
                {
                    "VendorID": "0x00000002",
                    "ProductCode": "0x044C2C52",
                    "RevisionNo": "0x00100000",
                    "Name": "EL1008",
                    "Vendor": "Beckhoff Automation GmbH & Co. KG",
                },
            ],
        },
    ]
    lookup = _build_lookup_from_yaml(data)
    assert (2, 0x044C2C52, 0x00100000) in lookup
    assert (2, 0x044C2C52, 0) in lookup
    r = lookup[(2, 0x044C2C52, 0x00100000)]
    assert r.manufacturer_name == "Beckhoff Automation GmbH & Co. KG"
    assert r.product_name == "EL1008"


def test_get_esi_paths() -> None:
    esi_path, cache_path = get_esi_paths()
    assert "ethercat-tool" in str(esi_path)
    assert esi_path.name == "esi.yml"
    assert cache_path.name == "esi_cache.json"


def test_has_esi_data_when_missing(tmp_path: Path) -> None:
    with patch("ethercat_tool.esi_data._get_data_dir", return_value=tmp_path):
        assert has_esi_data() is False


def test_has_esi_data_when_present(tmp_path: Path) -> None:
    (tmp_path / "esi_cache.json").write_text("{}")
    with patch("ethercat_tool.esi_data._get_data_dir", return_value=tmp_path):
        assert has_esi_data() is True


def test_has_esi_data_false_when_only_esi_yml(tmp_path: Path) -> None:
    """Cache is required; esi.yml alone is not sufficient."""
    (tmp_path / "esi.yml").write_text("[]")
    with patch("ethercat_tool.esi_data._get_data_dir", return_value=tmp_path):
        assert has_esi_data() is False


def test_load_esi_lookup_warns_when_cache_missing(tmp_path: Path) -> None:
    """When cache is missing, warn and return None (never parse esi.yml at scan time)."""
    with patch("ethercat_tool.esi_data._get_data_dir", return_value=tmp_path):
        with patch("sys.stderr", new_callable=StringIO) as err:
            lookup = load_esi_lookup()
    assert lookup is None
    assert "fetch-esi" in err.getvalue()


def test_load_esi_lookup_from_cache(tmp_path: Path) -> None:
    # 0x044C2C52 = 72100946, 0x01000000 = 16777216
    cache = {
        "2,72100946,16777216": {
            "manufacturer_name": "B",
            "product_name": "E",
            "device_type": None,
            "url": None,
        }
    }
    (tmp_path / "esi_cache.json").write_text(__import__("json").dumps(cache))
    with patch("ethercat_tool.esi_data._get_data_dir", return_value=tmp_path):
        lookup = load_esi_lookup()
    assert lookup is not None
    r = lookup_device(lookup, 2, 0x044C2C52, 0x01000000)
    assert r is not None
    assert r.manufacturer_name == "B"
