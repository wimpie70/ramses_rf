"""Test R57: Schema polling traits — polling_interval + is_battery (Phase 4c.1).

Verifies that the schema accepts the new polling-related traits:
- SZ_POLLING_INTERVAL and SZ_IS_BATTERY constants exist
- strip_and_map_schema maps _polling_interval and _is_battery
- _-prefixed keys are stripped from gateway schema
- DeviceBase has polling_interval and is_battery properties
- Gateway config has disable_polling (and retains disable_discovery alias)
- SCH_POLLING_INTERVAL validates dict[str, int] and rejects negatives

Converted from ha_sim_test recipe R57 (structural) to a pytest unit test.

See: https://github.com/ramses-rf/ramses_rf/pull/924 (Phase 4c.1)
"""

from __future__ import annotations

import pytest

from ramses_rf.config import SCH_POLLING_INTERVAL, strip_and_map_schema
from ramses_rf.const import SZ_IS_BATTERY, SZ_POLLING_INTERVAL
from ramses_rf.devices.dev_base import DeviceBase
from ramses_rf.schemas import SCH_GATEWAY_DICT

# ── 1. Constants ──────────────────────────────────────────────────────


def test_sz_polling_interval_constant() -> None:
    """SZ_POLLING_INTERVAL constant is 'polling_interval'."""
    assert SZ_POLLING_INTERVAL == "polling_interval"


def test_sz_is_battery_constant() -> None:
    """SZ_IS_BATTERY constant is 'is_battery'."""
    assert SZ_IS_BATTERY == "is_battery"


# ── 2. Schema validation + mapping ────────────────────────────────────

_TEST_SCHEMA = {
    "01:150000": {
        "_class": "CTL",
        "_alias": "Test CTL",
        "_polling_interval": {"10E0": 7200},
        "_is_battery": False,
    },
}
_STRIPPED = strip_and_map_schema(_TEST_SCHEMA)
_CTL_ENTRY = _STRIPPED.get("01:150000", {})


def test_strip_and_map_schema_maps_polling_interval() -> None:
    """strip_and_map_schema maps _polling_interval."""
    assert SZ_POLLING_INTERVAL in _CTL_ENTRY


def test_strip_and_map_schema_maps_is_battery() -> None:
    """strip_and_map_schema maps _is_battery."""
    assert SZ_IS_BATTERY in _CTL_ENTRY


def test_polling_interval_value_is_dict() -> None:
    """polling_interval value is the dict."""
    assert _CTL_ENTRY.get(SZ_POLLING_INTERVAL) == {"10E0": 7200}


def test_is_battery_value_is_false() -> None:
    """is_battery value is False."""
    assert _CTL_ENTRY.get(SZ_IS_BATTERY) is False


def test_polling_interval_stripped() -> None:
    """_polling_interval stripped from gateway schema."""
    assert "_polling_interval" not in _CTL_ENTRY


def test_is_battery_stripped() -> None:
    """_is_battery stripped from gateway schema."""
    assert "_is_battery" not in _CTL_ENTRY


# ── 3. DeviceBase properties ──────────────────────────────────────────


def test_device_has_polling_interval_property() -> None:
    """DeviceBase has polling_interval property."""
    assert hasattr(DeviceBase, "polling_interval")


def test_device_has_is_battery_property() -> None:
    """DeviceBase has is_battery property."""
    assert hasattr(DeviceBase, "is_battery")


# ── 4. Gateway config ─────────────────────────────────────────────────


def test_config_has_disable_polling() -> None:
    """Gateway config has disable_polling option."""
    gw_keys = [str(k) for k in SCH_GATEWAY_DICT]
    assert any("disable_polling" in k for k in gw_keys)


def test_config_retains_disable_discovery() -> None:
    """Gateway config retains disable_discovery (deprecated alias)."""
    gw_keys = [str(k) for k in SCH_GATEWAY_DICT]
    assert any("disable_discovery" in k for k in gw_keys)


# ── 5. SCH_POLLING_INTERVAL validation ────────────────────────────────


def test_sch_polling_interval_validates_dict() -> None:
    """SCH_POLLING_INTERVAL validates dict[str, int]."""
    validated = SCH_POLLING_INTERVAL({"10E0": 3600, "1F41": 1800})
    assert validated == {"10E0": 3600, "1F41": 1800}


def test_sch_polling_interval_rejects_negative() -> None:
    """SCH_POLLING_INTERVAL rejects negative intervals."""
    with pytest.raises(Exception):  # noqa: B017
        SCH_POLLING_INTERVAL({"10E0": -1})
