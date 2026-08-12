"""Test R39: CommandDTO carries no application metadata (issue 639).

Issue 639 rule 1: "No Application Metadata in TX".
``CommandDTO`` must never contain application-layer flags such as
``is_faked``, ``expected_response``, ``device_type``, or ``wait_for_reply``.
If a virtual device should not broadcast, ``ramses_rf`` must simply not send
a ``CommandDTO``.

Converted from ha_sim_test recipe R39 (structural) to a pytest unit test.

See: https://github.com/ramses-rf/ramses_rf/issues/639
"""

from __future__ import annotations

import dataclasses

from ramses_tx.dtos import CommandDTO

# The allowed L2/L3 fields per issue 639
ALLOWED_FIELDS = {
    "verb",
    "addr1",
    "addr2",
    "addr3",
    "code",
    "payload",
    "priority",
    "num_repeats",
}

# Forbidden application-layer fields that must never appear
FORBIDDEN_FIELDS = {
    "is_faked",
    "expected_response",
    "device_type",
    "wait_for_reply",
    "device_class",
    "src",
    "dst",
    "action",
    "data",
    "intent",
}


def test_commanddto_importable() -> None:
    """CommandDTO is importable from ramses_tx.dtos."""
    assert CommandDTO is not None


def test_commanddto_has_exactly_allowed_fields() -> None:
    """CommandDTO has exactly the allowed L2/L3 fields."""
    field_names = {f.name for f in dataclasses.fields(CommandDTO)}
    extra = field_names - ALLOWED_FIELDS
    missing = ALLOWED_FIELDS - field_names
    assert not extra, f"unexpected fields: {extra}"
    assert not missing, f"missing fields: {missing}"


def test_commanddto_no_forbidden_app_fields() -> None:
    """CommandDTO has no forbidden application-layer fields."""
    field_names = {f.name for f in dataclasses.fields(CommandDTO)}
    found = field_names & FORBIDDEN_FIELDS
    assert not found, f"forbidden fields found: {found}"


def test_commanddto_is_frozen() -> None:
    """CommandDTO is frozen (immutable per issue 639 DTO rules)."""
    frozen = getattr(CommandDTO.__dataclass_params__, "frozen", False)
    assert frozen, "CommandDTO is not frozen"
