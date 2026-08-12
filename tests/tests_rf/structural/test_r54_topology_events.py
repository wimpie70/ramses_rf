"""Test R54: Topology event flow (BIND_DEVICE, CREATE_CONTROLLER).

Verifies that the ramses_rf TopologyBuilder correctly emits
``TopologyChangedEvent`` events when processing 1FC9 (rf_bind) packets
and CODES_ONLY_FROM_CTL broadcasts.

Converted from ha_sim_test recipe R54 (structural) to a pytest unit test.

See: https://github.com/ramses-rf/ramses_rf/issues/767
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from ramses_rf.enums import TopologyAction
from ramses_rf.models import TopologyChangedEvent
from ramses_rf.pipeline.topology_builder import TopologyBuilder
from ramses_tx.const import Code

CTL = "01:150000"
FAN = "32:150000"
REM = "37:170000"
TRV = "04:150003"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def emitted_events() -> list[TopologyChangedEvent]:
    """A list that a TopologyBuilder callback can append events to."""
    return []


@pytest.fixture
def builder(emitted_events: list[TopologyChangedEvent]) -> TopologyBuilder:
    """A TopologyBuilder with a callback that collects emitted events."""

    def emit_cb(event: TopologyChangedEvent) -> None:
        emitted_events.append(event)

    return TopologyBuilder(emit_event_cb=emit_cb, enable_eavesdrop=True)


# ── 1. TopologyChangedEvent ───────────────────────────────────────────


def test_event_action_is_bind_device() -> None:
    """event action is BIND_DEVICE."""
    event = TopologyChangedEvent(
        action=TopologyAction.BIND_DEVICE,
        parent_id=FAN,
        child_id=REM,
        metadata={"zone_idx": "01"},
    )
    assert str(event.action) == "bind_device"


def test_event_parent_id_is_fan() -> None:
    """event parent_id is FAN."""
    event = TopologyChangedEvent(
        action=TopologyAction.BIND_DEVICE,
        parent_id=FAN,
        child_id=REM,
        metadata={},
    )
    assert str(event.parent_id) == FAN


def test_event_child_id_is_rem() -> None:
    """event child_id is REM."""
    event = TopologyChangedEvent(
        action=TopologyAction.BIND_DEVICE,
        parent_id=FAN,
        child_id=REM,
        metadata={},
    )
    assert str(event.child_id) == REM


def test_event_has_metadata() -> None:
    """event has metadata."""
    event = TopologyChangedEvent(
        action=TopologyAction.BIND_DEVICE,
        parent_id=FAN,
        child_id=REM,
        metadata={"zone_idx": "01"},
    )
    assert "zone_idx" in event.metadata


def test_event_has_uuid() -> None:
    """event has UUID (event_id)."""
    event = TopologyChangedEvent(
        action=TopologyAction.BIND_DEVICE,
        parent_id=FAN,
        child_id=REM,
        metadata={},
    )
    assert hasattr(event, "event_id")


def test_event_is_immutable() -> None:
    """event is immutable (frozen dataclass)."""
    event = TopologyChangedEvent(
        action=TopologyAction.BIND_DEVICE,
        parent_id=FAN,
        child_id=REM,
        metadata={},
    )
    with pytest.raises((AttributeError, Exception)):
        event.action = TopologyAction.CREATE_CONTROLLER  # type: ignore[misc]


# ── 2. TopologyAction enum ────────────────────────────────────────────


def test_all_topology_actions_present() -> None:
    """all TopologyAction values present."""
    expected = {"update_traits", "bind_device", "create_controller", "create_circuit"}
    actual = {str(a) for a in TopologyAction}
    assert expected.issubset(actual), f"missing: {expected - actual}"


def test_has_promote_or_update_class() -> None:
    """has promote_class or update_device_class (PR 914 rename)."""
    actual = {str(a) for a in TopologyAction}
    assert "promote_class" in actual or "update_device_class" in actual


# ── 3. TopologyBuilder creation ───────────────────────────────────────


def test_builder_created(builder: TopologyBuilder) -> None:
    """TopologyBuilder created with callback."""
    assert builder is not None


# ── 4. 1FC9 rf_bind processing ────────────────────────────────────────


def _make_1fc9_msg() -> MagicMock:
    """Build a mock 1FC9 message from a CTL binding a TRV."""
    bind_payload = f"0104{TRV.replace(':', '')}"
    mock_dto = MagicMock()
    mock_dto.payload = bind_payload
    mock_msg = MagicMock()
    mock_msg.header.verb = " I"
    mock_msg.header.code = Code._1FC9
    mock_msg.src.id = CTL
    mock_msg.src.type = "01"
    mock_msg.dst.id = "18:765432"
    mock_msg.dst.type = "18"
    mock_msg._dto = mock_dto
    return mock_msg


def test_1fc9_emits_events(builder: TopologyBuilder, emitted_events: list) -> None:
    """1FC9 packet emits at least 1 event."""
    asyncio.run(builder.consume(_make_1fc9_msg()))
    assert len(emitted_events) > 0


def test_1fc9_from_ctl_emits_create_controller(
    builder: TopologyBuilder, emitted_events: list
) -> None:
    """1FC9 from CTL emits CREATE_CONTROLLER."""
    asyncio.run(builder.consume(_make_1fc9_msg()))
    create_ctrl = [
        e for e in emitted_events if e.action == TopologyAction.CREATE_CONTROLLER
    ]
    assert len(create_ctrl) > 0


def test_create_controller_device_is_ctl(
    builder: TopologyBuilder, emitted_events: list
) -> None:
    """CREATE_CONTROLLER device is CTL."""
    asyncio.run(builder.consume(_make_1fc9_msg()))
    create_ctrl = [
        e for e in emitted_events if e.action == TopologyAction.CREATE_CONTROLLER
    ]
    assert create_ctrl
    assert str(create_ctrl[0].device_id) == CTL


# ── 5. CODES_ONLY_FROM_CTL broadcast ──────────────────────────────────


def _make_ctl_broadcast_msg() -> MagicMock:
    """Build a mock CTL broadcast message (1F09 system mode)."""
    mock_msg = MagicMock()
    mock_msg.header.verb = " I"
    mock_msg.header.code = Code._1F09
    mock_msg.src.id = CTL
    mock_msg.dst.id = "18:765432"
    mock_msg._pkt = MagicMock()
    mock_msg._pkt.payload = "000E003545C8"
    return mock_msg


def test_ctl_broadcast_emits_create_controller(
    builder: TopologyBuilder, emitted_events: list
) -> None:
    """CTL broadcast emits CREATE_CONTROLLER."""
    asyncio.run(builder.consume(_make_ctl_broadcast_msg()))
    ctl_events = [
        e for e in emitted_events if e.action == TopologyAction.CREATE_CONTROLLER
    ]
    assert len(ctl_events) > 0


def test_ctl_broadcast_device_is_ctl(
    builder: TopologyBuilder, emitted_events: list
) -> None:
    """CTL broadcast device is CTL."""
    asyncio.run(builder.consume(_make_ctl_broadcast_msg()))
    ctl_events = [
        e for e in emitted_events if e.action == TopologyAction.CREATE_CONTROLLER
    ]
    assert ctl_events
    assert str(ctl_events[0].device_id) == CTL


def test_ctl_broadcast_causation_is_evohome(
    builder: TopologyBuilder, emitted_events: list
) -> None:
    """CTL broadcast causation is Evohome rule."""
    asyncio.run(builder.consume(_make_ctl_broadcast_msg()))
    ctl_events = [
        e for e in emitted_events if e.action == TopologyAction.CREATE_CONTROLLER
    ]
    assert ctl_events
    assert "Evohome" in str(ctl_events[0].causation)
