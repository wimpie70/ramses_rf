"""Test R56: L7 PollingManager live cutover (Phase 4c.3).

Verifies the PollingManager infrastructure that replaces legacy
DiscoveryService polling:
- PollingManager module importable from ramses_rf.pipeline.polling
- PollingTask dataclass with required fields
- DEFAULT_POLLING_SCHEDULES (battery=None, mains=active)
- Gateway has polling_manager property
- PollingManager accepts shadow_mode parameter
- Legacy poller deactivated (DiscoveryService.start_poller is no-op)
- Lifecycle integration (start calls pm.start, stop calls pm.stop)
- poll_due_commands dispatches via async_send_cmd (not raw CommandDTO)
- GatewayConfig has disable_polling option

Converted from ha_sim_test recipe R56 (structural) to a pytest unit test.

See: https://github.com/ramses-rf/ramses_rf/pull/926 (Phase 4c.3)
     https://github.com/ramses-rf/ramses_rf/pull/925 (Phase 4c.2)
"""

from __future__ import annotations

import inspect

import pytest

from ramses_rf.const import DevType
from ramses_rf.gateway import Gateway
from ramses_rf.lifecycle import GatewayLifecycle
from ramses_rf.pipeline.polling import (
    DEFAULT_POLLING_SCHEDULES,
    PollingManager,
    PollingTask,
)

# ── 1. PollingTask dataclass ──────────────────────────────────────────


def test_polling_task_is_dataclass() -> None:
    """PollingTask is a dataclass."""
    assert hasattr(PollingTask, "__dataclass_fields__")


@pytest.mark.parametrize("field", ["device_id", "code", "interval", "next_due"])
def test_polling_task_has_field(field: str) -> None:
    """PollingTask has the expected field."""
    assert field in PollingTask.__dataclass_fields__


# ── 2. DEFAULT_POLLING_SCHEDULES ──────────────────────────────────────


@pytest.mark.parametrize("dev_type", [DevType.CTL, DevType.FAN, DevType.TRV])
def test_schedules_include_dev_type(dev_type: DevType) -> None:
    """Schedules include the expected device type."""
    assert dev_type in DEFAULT_POLLING_SCHEDULES


def test_schedules_include_default_fallback() -> None:
    """Schedules include DEFAULT fallback."""
    assert "DEFAULT" in DEFAULT_POLLING_SCHEDULES


def test_trv_has_none_interval() -> None:
    """TRV (battery) has None interval (polling disabled)."""
    trv_schedule = DEFAULT_POLLING_SCHEDULES.get(DevType.TRV, {})
    assert any(v is None for v in trv_schedule.values())


def test_ctl_has_active_interval() -> None:
    """CTL (mains) has active interval."""
    ctl_schedule = DEFAULT_POLLING_SCHEDULES.get(DevType.CTL, {})
    assert any(v is not None and v > 0 for v in ctl_schedule.values())


# ── 3. Gateway property ───────────────────────────────────────────────


def test_gateway_has_polling_manager_property() -> None:
    """Gateway has polling_manager property."""
    assert hasattr(Gateway, "polling_manager")


# ── 4. PollingManager constructor ─────────────────────────────────────


def test_pm_has_shadow_mode_param() -> None:
    """PollingManager accepts shadow_mode parameter."""
    sig = inspect.signature(PollingManager.__init__)
    assert "shadow_mode" in sig.parameters


# ── 5. Legacy poller deactivated ──────────────────────────────────────


def test_legacy_poller_is_noop() -> None:
    """Legacy start_poller is deprecated/no-op or DiscoveryService removed."""
    try:
        from ramses_rf.discovery import DiscoveryService
    except ImportError:
        # DiscoveryService fully removed — stronger than no-op
        return

    poller_src = inspect.getsource(DiscoveryService.start_poller)
    assert "deprecated" in poller_src.lower() or "disabled" in poller_src.lower()


def test_legacy_poller_no_schedule_task() -> None:
    """Legacy start_poller does not call schedule_task."""
    try:
        from ramses_rf.discovery import DiscoveryService
    except ImportError:
        return

    poller_src = inspect.getsource(DiscoveryService.start_poller)
    assert "schedule_task" not in poller_src


# ── 6. Lifecycle integration ──────────────────────────────────────────


def test_lifecycle_start_calls_pm_start() -> None:
    """GatewayLifecycle.start calls pm.start()."""
    src = inspect.getsource(GatewayLifecycle.start)
    assert "polling_manager" in src and "pm.start" in src


def test_lifecycle_stop_calls_pm_stop() -> None:
    """GatewayLifecycle.stop calls pm.stop()."""
    src = inspect.getsource(GatewayLifecycle.stop)
    assert "polling_manager" in src and "pm.stop" in src


# ── 7. Live command dispatch ──────────────────────────────────────────


def test_poll_dispatches_via_async_send_cmd() -> None:
    """PollingManager.poll_due_commands dispatches via async_send_cmd."""
    src = inspect.getsource(PollingManager.poll_due_commands)
    assert "async_send_cmd" in src


def test_poll_uses_build_rq_cmd() -> None:
    """PollingManager uses build_rq_cmd (correct address convention)."""
    src = inspect.getsource(PollingManager.poll_due_commands)
    assert "build_rq_cmd" in src


def test_poll_no_raw_command_dto() -> None:
    """PollingManager does not construct raw CommandDTO (avoids addr bugs)."""
    src = inspect.getsource(PollingManager.poll_due_commands)
    assert "CommandDTO(" not in src


def test_poll_checks_disable_polling() -> None:
    """PollingManager respects disable_polling config."""
    src = inspect.getsource(PollingManager.poll_due_commands)
    assert "disable_polling" in src


# ── 8. Config ─────────────────────────────────────────────────────────


def test_config_has_disable_polling() -> None:
    """GatewayConfig has disable_polling option."""
    from ramses_rf.config import GatewayConfig

    src = inspect.getsource(GatewayConfig)
    assert "disable_polling" in src
