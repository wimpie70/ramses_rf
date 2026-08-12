"""Test R48: strip_and_map_traits — schema pre-validation pipeline (issue 767).

Verifies that ``strip_and_map_traits()`` correctly removes ``_``-prefixed
keys that ramses_rf doesn't need (``_commands``, ``_disabled``, ``_name``,
``_note``, ``_owner``, ``_comment``, ``_skipped``) and maps known ones to
their native names (``_bound``→``bound``, ``_scheme``→``scheme``,
``_alias``→``alias``, ``_faked``→``faked``, ``_class``→``class``).

Converted from ha_sim_test recipe R48 (structural) to a pytest unit test.

See: https://github.com/ramses-rf/ramses_cc/issues/767
"""

from __future__ import annotations

from ramses_rf.schemas import strip_and_map_traits

# Test traits dict — per-device, with _-prefixed keys to strip/map
TEST_TRAITS = {
    "01:150003": {
        "_class": "THM",
        "_alias": "Lounge Sensor",
        "_faked": True,
        "_bound": "01:150000",
        "_scheme": "itho",
        "_disabled": True,
        "_commands": {"off": {"code": "2309", "payload": "0000FF"}},
        "_name": "Lounge",
        "_note": "test device",
    },
    "04:150003": {
        "_class": "TRV",
        "_disabled": True,
        "_commands": {"off": {"code": "2309", "payload": "0000FF"}},
    },
    "01:150000": {
        "zones": {
            "03": {
                "sensor": "01:150003",
                "actuators": ["04:150003"],
                "_name": "Lounge",
            },
        },
        "stored_hotwater": {"sensor": "07:150000"},
    },
}


def _find_underscore_keys(obj: object, path: str = "") -> list[str]:
    """Recursively find _-prefixed keys (except _name, preserved per 919)."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith("_") and k != "_name":
                found.append(f"{path}.{k}" if path else k)
            found.extend(_find_underscore_keys(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(_find_underscore_keys(v, f"{path}[{i}]"))
    return found


# Apply strip_and_map_traits to all test devices once at module level
_RESULTS = {
    dev_id: strip_and_map_traits(traits) for dev_id, traits in TEST_TRAITS.items()
}
_THM = _RESULTS["01:150003"]
_TRV = _RESULTS["04:150003"]
_CTL = _RESULTS["01:150000"]
_ZONES = _CTL.get("zones", {})
_ZONE_03 = _ZONES.get("03", {})
_DHW = _CTL.get("stored_hotwater", {})


def test_strip_and_map_traits_runs_without_error() -> None:
    """strip_and_map_traits runs without error on all test traits."""
    assert len(_RESULTS) == 3


def test_no_underscore_keys_remain() -> None:
    """No _-prefixed keys remain after strip_and_map_traits (except _name)."""
    all_underscore: list[str] = []
    for dev_id, mapped in _RESULTS.items():
        all_underscore.extend(_find_underscore_keys(mapped, dev_id))
    assert not all_underscore, f"found _ keys: {all_underscore[:5]}"


def test_class_mapped() -> None:
    """_class mapped to class (THM)."""
    assert _THM.get("class") == "THM"


def test_alias_mapped() -> None:
    """_alias mapped to alias."""
    assert _THM.get("alias") == "Lounge Sensor"


def test_faked_mapped() -> None:
    """_faked mapped to faked."""
    assert _THM.get("faked") is True


def test_bound_mapped() -> None:
    """_bound mapped to bound."""
    assert _THM.get("bound") == "01:150000"


def test_scheme_mapped() -> None:
    """_scheme mapped to scheme."""
    assert _THM.get("scheme") == "itho"


def test_disabled_stripped() -> None:
    """_disabled stripped (not mapped to disabled)."""
    assert "disabled" not in _THM


def test_commands_stripped() -> None:
    """_commands stripped (not mapped to commands)."""
    assert "commands" not in _THM


def test_name_not_mapped_to_native() -> None:
    """_name not mapped to native 'name' (preserved as _name, issue 919)."""
    assert "name" not in _THM


def test_name_preserved_as_underscore() -> None:
    """_name preserved as _name in device traits (issue 919)."""
    assert "_name" in _THM


def test_note_stripped() -> None:
    """_note stripped from device traits."""
    assert "note" not in _THM


def test_trv_class_mapped() -> None:
    """TRV _class mapped to class."""
    assert _TRV.get("class") == "TRV"


def test_trv_disabled_stripped() -> None:
    """TRV _disabled stripped."""
    assert "disabled" not in _TRV


def test_trv_commands_stripped() -> None:
    """TRV _commands stripped."""
    assert "commands" not in _TRV


def test_ctl_zones_preserved() -> None:
    """CTL zones topology preserved."""
    assert "03" in _ZONES


def test_ctl_dhw_preserved() -> None:
    """CTL DHW topology preserved."""
    assert isinstance(_DHW, dict)
    assert "sensor" in _DHW


def test_zone_name_preserved() -> None:
    """zone _name preserved in nested zone dict (issue 919)."""
    assert isinstance(_ZONE_03, dict)
    assert "_name" in _ZONE_03


def test_zone_sensor_preserved() -> None:
    """zone sensor preserved after stripping."""
    assert isinstance(_ZONE_03, dict)
    assert _ZONE_03.get("sensor") == "01:150003"
