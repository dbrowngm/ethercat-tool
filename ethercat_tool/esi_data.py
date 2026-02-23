"""ESI (EtherCAT device information) data: load, lookup, download.

Decodes manufacturer ID, product code, revision to human-readable names
using data from linuxcnc-ethercat/esi-data (YAML from ESI XML files).
"""

from dataclasses import dataclass
from pathlib import Path
import json
import sys

ESI_YAML_URL = "https://raw.githubusercontent.com/linuxcnc-ethercat/esi-data/main/esi.yml"
CACHE_FILENAME = "esi_cache.json"


@dataclass(frozen=True)
class EsiLookupResult:
    """Decoded device info from ESI data."""

    manufacturer_name: str
    product_name: str
    device_type: str | None
    url: str | None


def _get_data_dir() -> Path:
    """Return the directory for ESI data (XDG_DATA_HOME or ~/.local/share)."""
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".local" / "share"
    return base / "ethercat-tool"


def _parse_hex(value: str | int) -> int:
    """Parse hex string like '0x00000002' or int to int."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.lower().startswith("0x"):
        return int(value, 16)
    try:
        return int(value)
    except (ValueError, TypeError):
        return -1


def _extract_ids_from_device(device: dict) -> list[dict]:
    """Extract ID entries from a device block. Handle both list and single dict."""
    ids = device.get("IDs") or []
    if isinstance(ids, dict):
        return [ids]
    return ids if isinstance(ids, list) else []


def _build_lookup_from_yaml(data: list) -> dict[tuple[int, int, int], EsiLookupResult]:
    """Build (vendor_id, product_code, revision) -> EsiLookupResult from esi.yml structure."""
    lookup: dict[tuple[int, int, int], EsiLookupResult] = {}
    fallback: dict[tuple[int, int], EsiLookupResult] = {}
    for device in data:
        if not isinstance(device, dict):
            continue
        for id_entry in _extract_ids_from_device(device):
            if not isinstance(id_entry, dict):
                continue
            vendor_id = _parse_hex(id_entry.get("VendorID", id_entry.get("VendorId", 0)))
            product_code = _parse_hex(id_entry.get("ProductCode", 0))
            revision = _parse_hex(id_entry.get("RevisionNo", 0))
            if vendor_id < 0 or product_code < 0:
                continue
            if revision < 0:
                revision = 0
            name = id_entry.get("Name") or id_entry.get("Type") or ""
            vendor = id_entry.get("Vendor") or ""
            url = id_entry.get("URL")
            result = EsiLookupResult(
                manufacturer_name=vendor,
                product_name=name,
                device_type=id_entry.get("Type"),
                url=url,
            )
            key = (vendor_id, product_code, revision)
            if key not in lookup:
                lookup[key] = result
            vp = (vendor_id, product_code)
            if vp not in fallback:
                fallback[vp] = result
    # Merge fallback as (v, p, 0) for lookup fallback
    for (v, p), res in fallback.items():
        k = (v, p, 0)
        if k not in lookup:
            lookup[k] = res
    return lookup


def _lookup_to_cache(lookup: dict) -> dict:
    """Convert lookup dict to JSON-serializable form."""
    return {
        f"{v},{p},{r}": {
            "manufacturer_name": res.manufacturer_name,
            "product_name": res.product_name,
            "device_type": res.device_type,
            "url": res.url,
        }
        for (v, p, r), res in lookup.items()
    }


def _cache_to_lookup(cache: dict) -> dict[tuple[int, int, int], EsiLookupResult]:
    """Restore lookup from cached JSON."""
    lookup: dict[tuple[int, int, int], EsiLookupResult] = {}
    for key, val in cache.items():
        try:
            v, p, r = (int(x) for x in key.split(",", 2))
            lookup[(v, p, r)] = EsiLookupResult(
                manufacturer_name=val.get("manufacturer_name", ""),
                product_name=val.get("product_name", ""),
                device_type=val.get("device_type"),
                url=val.get("url"),
            )
        except (ValueError, KeyError):
            continue
    return lookup


def get_esi_paths() -> tuple[Path, Path]:
    """Return (esi_yml_path, cache_path) in data directory."""
    data_dir = _get_data_dir()
    return data_dir / "esi.yml", data_dir / CACHE_FILENAME


def has_esi_data() -> bool:
    """True if ESI cache exists (usable for lookups). Cache is built on --fetch-esi only."""
    _, cache_path = get_esi_paths()
    return cache_path.exists()


def load_esi_lookup() -> dict[tuple[int, int, int], EsiLookupResult] | None:
    """Load ESI lookup from cache. Returns None if cache unavailable; never parses esi.yml at scan time."""
    _, cache_path = get_esi_paths()

    if cache_path.exists():
        try:
            with open(cache_path) as f:
                cache = json.load(f)
            return _cache_to_lookup(cache)
        except (json.JSONDecodeError, OSError):
            pass

    print(
        "Warning: ESI device cache not found. Run 'ethercat-tool --fetch-esi' to download. Proceeding with raw IDs.",
        file=sys.stderr,
    )
    return None


def lookup_device(
    lookup: dict[tuple[int, int, int], EsiLookupResult],
    manufacturer_id: int,
    product_code: int,
    revision: int,
) -> EsiLookupResult | None:
    """Find device info. Tries exact (v,p,r) then (v,p,0) fallback."""
    key = (manufacturer_id, product_code, revision)
    if key in lookup:
        return lookup[key]
    fallback = (manufacturer_id, product_code, 0)
    return lookup.get(fallback)


def _parse_esi_and_save_cache(esi_path: Path, cache_path: Path) -> bool:
    """Parse esi.yml and save cache. Returns True on success."""
    try:
        import yaml

        with open(esi_path) as f:
            data = yaml.safe_load(f)
        if data is None or not isinstance(data, list):
            return False
        lookup = _build_lookup_from_yaml(data)
        esi_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(_lookup_to_cache(lookup), f)
        return True
    except Exception:
        return False


def fetch_esi_data() -> bool:
    """Download esi.yml from internet, parse it, and build cache. Returns True on success."""
    try:
        import urllib.request

        esi_path, cache_path = get_esi_paths()
        data_dir = esi_path.parent
        data_dir.mkdir(parents=True, exist_ok=True)

        with urllib.request.urlopen(ESI_YAML_URL, timeout=120) as resp:
            data = resp.read()
        with open(esi_path, "wb") as f:
            f.write(data)
        # Build cache immediately so first scan is fast (~44MB YAML parse takes 1–2 min)
        return _parse_esi_and_save_cache(esi_path, cache_path)
    except Exception:
        return False
