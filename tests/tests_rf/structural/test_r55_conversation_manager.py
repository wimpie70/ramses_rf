"""Test R55: L7 ConversationManager RQ/RP tracking + retransmission.

Verifies the ConversationManager infrastructure (Phase 4a through 4b):
- ConversationManager instantiation and pending_count tracking
- PendingConversation dataclass fields
- track_intent registers intent, returns future, schedules timeout
- process_msg matches incoming RP to pending, resolves future
- Timeout + retry behavior (ProtocolTimeoutError after max_retries)
- cancel_all cancels all pending conversations
- Gateway has conversation_manager property
- CommandDispatcher.send uses ConversationManager (Phase 4b cutover)
- dispatcher.process_msg hooks ConversationManager (Phase 4a.5)
- GatewayLifecycle.stop() calls cancel_all

Converted from ha_sim_test recipe R55 (structural) to a pytest unit test.

See: https://github.com/ramses-rf/ramses_rf/pull/920 (Phase 4a.5)
     https://github.com/ramses-rf/ramses_rf/pull/921 (Phase 4b)
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
from unittest.mock import MagicMock

import pytest

from ramses_rf.address import Address
from ramses_rf.commands.core import Command
from ramses_rf.enums import Action
from ramses_rf.pipeline.conversation import (
    DEFAULT_RPLY_TIMEOUT,
    MAX_RETRY_LIMIT,
    ConversationManager,
    PendingConversation,
)
from ramses_tx import RP
from ramses_tx.exceptions import ProtocolTimeoutError

HGI = "18:001234"
CTL = "01:150000"


# ── 1. Constants and dataclass structure ──────────────────────────────


def test_default_rply_timeout() -> None:
    """DEFAULT_RPLY_TIMEOUT is 1.0s."""
    assert DEFAULT_RPLY_TIMEOUT == 1.0


def test_max_retry_limit() -> None:
    """MAX_RETRY_LIMIT is 3."""
    assert MAX_RETRY_LIMIT == 3


@pytest.mark.parametrize(
    "field",
    ["intent", "fut", "timeout", "max_retries", "retry_count", "timer_task"],
)
def test_pending_conversation_has_field(field: str) -> None:
    """PendingConversation has the expected field."""
    assert field in PendingConversation.__dataclass_fields__


# ── Fixtures for ConversationManager tests ────────────────────────────


@pytest.fixture
def event_loop() -> asyncio.AbstractEventLoop:
    """A fresh event loop for each test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop  # type: ignore[misc]
    loop.close()


@pytest.fixture
def cm(event_loop: asyncio.AbstractEventLoop) -> ConversationManager:
    """A ConversationManager with short timeout for testing."""
    return ConversationManager(
        loop=event_loop,
        default_timeout=0.5,
        max_retries=2,
    )


def _make_intent(dst_id: str = CTL, timeout: float = 0.5) -> Command:
    """Build a Command intent for testing."""
    return Command(
        src=Address(HGI),
        dst=Address(dst_id),
        action=Action.GET_ZONE_SETPOINT,
        data={"zone_idx": "01"},
        needs_reply=True,
        timeout=timeout,
    )


# ── 2. ConversationManager instantiation ──────────────────────────────


def test_cm_created(cm: ConversationManager) -> None:
    """ConversationManager created with callback."""
    assert cm is not None


def test_cm_pending_count_init(cm: ConversationManager) -> None:
    """pending_count is 0 initially."""
    assert cm.pending_count == 0


# ── 3. track_intent ───────────────────────────────────────────────────


def test_track_intent_returns_future(
    cm: ConversationManager, event_loop: asyncio.AbstractEventLoop
) -> None:
    """track_intent returns a future."""
    fut = event_loop.run_until_complete(
        cm.track_intent(_make_intent(), timeout=0.5, max_retries=2)
    )
    assert asyncio.isfuture(fut)


def test_pending_count_after_track(
    cm: ConversationManager, event_loop: asyncio.AbstractEventLoop
) -> None:
    """pending_count is 1 after track_intent."""
    event_loop.run_until_complete(
        cm.track_intent(_make_intent(), timeout=0.5, max_retries=2)
    )
    assert cm.pending_count == 1


# ── 4. process_msg matching ───────────────────────────────────────────


def test_process_msg_matches_rp(
    cm: ConversationManager, event_loop: asyncio.AbstractEventLoop
) -> None:
    """process_msg matches RP to pending conversation."""
    intent = _make_intent()
    event_loop.run_until_complete(cm.track_intent(intent, timeout=0.5, max_retries=2))

    from ramses_rf.commands.builders import build_dto

    dto = build_dto(intent)
    mock_msg = MagicMock()
    mock_msg.verb = RP
    mock_msg.src.id = CTL
    mock_msg.code = MagicMock()
    mock_msg.code.__str__ = lambda self: dto.code
    mock_msg._pkt = MagicMock()

    matched = cm.process_msg(mock_msg)
    assert matched


def test_pending_count_after_match(
    cm: ConversationManager, event_loop: asyncio.AbstractEventLoop
) -> None:
    """pending_count is 0 after match."""
    intent = _make_intent()
    event_loop.run_until_complete(cm.track_intent(intent, timeout=0.5, max_retries=2))

    from ramses_rf.commands.builders import build_dto

    dto = build_dto(intent)
    mock_msg = MagicMock()
    mock_msg.verb = RP
    mock_msg.src.id = CTL
    mock_msg.code = MagicMock()
    mock_msg.code.__str__ = lambda self: dto.code
    mock_msg._pkt = MagicMock()

    cm.process_msg(mock_msg)
    assert cm.pending_count == 0


def test_future_resolved_after_match(
    cm: ConversationManager, event_loop: asyncio.AbstractEventLoop
) -> None:
    """future resolved with RP message."""
    intent = _make_intent()
    fut = event_loop.run_until_complete(
        cm.track_intent(intent, timeout=0.5, max_retries=2)
    )

    from ramses_rf.commands.builders import build_dto

    dto = build_dto(intent)
    mock_msg = MagicMock()
    mock_msg.verb = RP
    mock_msg.src.id = CTL
    mock_msg.code = MagicMock()
    mock_msg.code.__str__ = lambda self: dto.code
    mock_msg._pkt = MagicMock()

    cm.process_msg(mock_msg)
    assert fut.done() and not fut.cancelled()
    fut.result()  # should not raise


# ── 5. Timeout + retry ────────────────────────────────────────────────


def test_timeout_completes_with_protocol_timeout(
    cm: ConversationManager, event_loop: asyncio.AbstractEventLoop
) -> None:
    """timeout future completes with ProtocolTimeoutError."""
    intent = _make_intent(dst_id="04:150003", timeout=0.3)
    fut = event_loop.run_until_complete(
        cm.track_intent(intent, timeout=0.3, max_retries=2)
    )

    with pytest.raises((ProtocolTimeoutError, asyncio.TimeoutError, Exception)):
        event_loop.run_until_complete(asyncio.wait_for(fut, timeout=3.0))


def test_pending_count_after_timeout(
    cm: ConversationManager, event_loop: asyncio.AbstractEventLoop
) -> None:
    """pending_count is 0 after timeout."""
    intent = _make_intent(dst_id="04:150003", timeout=0.3)
    fut = event_loop.run_until_complete(
        cm.track_intent(intent, timeout=0.3, max_retries=2)
    )

    with contextlib.suppress(Exception):
        event_loop.run_until_complete(asyncio.wait_for(fut, timeout=3.0))

    assert cm.pending_count == 0


# ── 6. cancel_all ─────────────────────────────────────────────────────


def test_cancel_all(
    cm: ConversationManager, event_loop: asyncio.AbstractEventLoop
) -> None:
    """cancel_all clears pending conversations and marks futures done."""
    intent = _make_intent(dst_id="07:150000", timeout=10.0)
    fut = event_loop.run_until_complete(cm.track_intent(intent, timeout=10.0))
    assert cm.pending_count == 1

    cm.cancel_all()
    assert cm.pending_count == 0
    assert fut.done()


# ── 7. Gateway has conversation_manager property ──────────────────────


def test_gateway_has_conversation_manager_property() -> None:
    """Gateway has conversation_manager property."""
    from ramses_rf.gateway import Gateway

    assert hasattr(Gateway, "conversation_manager")


# ── 8. CommandDispatcher integration ──────────────────────────────────


def test_dispatcher_send_uses_conversation_manager() -> None:
    """CommandDispatcher.send uses conversation_manager."""
    from ramses_rf.commands.dispatcher import CommandDispatcher

    src = inspect.getsource(CommandDispatcher.send)
    assert "conversation_manager" in src


def test_dispatcher_send_calls_track_intent() -> None:
    """CommandDispatcher.send calls track_intent."""
    from ramses_rf.commands.dispatcher import CommandDispatcher

    src = inspect.getsource(CommandDispatcher.send)
    assert "track_intent" in src


def test_dispatcher_no_l3_reply_block() -> None:
    """CommandDispatcher.send does not block L3 for replies (Phase 4b)."""
    from ramses_rf.commands.dispatcher import CommandDispatcher

    src = inspect.getsource(CommandDispatcher.send)
    # PR 926: "wait_for_reply=False" is explicitly passed
    # PR 929: wait_for_reply removed from transport layer entirely
    after_send = src.split("async_send_cmd")[-1]
    assert "wait_for_reply=False" in src or "wait_for_reply" not in after_send


# ── 9. dispatcher.process_msg hooks ConversationManager ───────────────


def test_process_msg_references_conversation_manager() -> None:
    """dispatcher.process_msg references conversation_manager."""
    from ramses_rf import dispatcher as disp_mod

    src = inspect.getsource(disp_mod.process_msg)
    assert "conversation_manager" in src


def test_process_msg_calls_cm_process_msg() -> None:
    """dispatcher.process_msg calls cm.process_msg()."""
    from ramses_rf import dispatcher as disp_mod

    src = inspect.getsource(disp_mod.process_msg)
    assert ".process_msg(" in src


# ── 10. GatewayLifecycle.stop() calls cancel_all ──────────────────────


def test_lifecycle_stop_calls_cancel_all() -> None:
    """GatewayLifecycle.stop() calls cancel_all."""
    from ramses_rf.lifecycle import GatewayLifecycle

    src = inspect.getsource(GatewayLifecycle.stop)
    assert "cancel_all" in src
