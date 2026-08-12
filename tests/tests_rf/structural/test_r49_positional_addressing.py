"""Test R49: Positional addressing — addr1/addr2/addr3 to src/dst (issue 639).

Issue 639 rule 2: "Positional Addressing Only".  DTOs use ``addr1``,
``addr2``, ``addr3`` (positional MAC addresses), not ``src`` or ``dst``.
Translating positional addresses to logical source/destination based on
verbs is an OSI Layer 7 domain responsibility that lives in ``ramses_rf``.

Converted from ha_sim_test recipe R49 (structural) to a pytest unit test.

See: https://github.com/ramses-rf/ramses_rf/issues/639
"""

from __future__ import annotations

import dataclasses

import pytest

from ramses_tx import Packet
from ramses_tx.dtos import CommandDTO, PacketDTO


def test_commanddto_uses_positional_addresses() -> None:
    """CommandDTO uses addr1/addr2/addr3 (not src/dst)."""
    fields = {f.name for f in dataclasses.fields(CommandDTO)}
    assert {"addr1", "addr2", "addr3"} <= fields
    assert "src" not in fields
    assert "dst" not in fields


def test_packetdto_uses_positional_addresses() -> None:
    """PacketDTO uses addr1/addr2/addr3 (not src/dst)."""
    fields = {f.name for f in dataclasses.fields(PacketDTO)}
    assert {"addr1", "addr2", "addr3"} <= fields
    assert "src" not in fields
    assert "dst" not in fields


# Packet parser test cases: (name, frame, expected_src, expected_dst)
# The RAMSES II positional addressing rules:
#   I  broadcast:  addr1=src, addr2=--:------, addr3=src (same device)
#   I  directed:   addr1=src, addr2=dst,      addr3=--:------
#   RQ directed:   addr1=src, addr2=dst,      addr3=--:------
#   RP directed:   addr1=dst, addr2=src,      addr3=--:------
#   W  directed:   addr1=src, addr2=dst,      addr3=--:------
_PACKET_CASES = [
    (
        "I broadcast (sensor announces)",
        " I --- 01:150003 --:------ 01:150003 30C9 003 030AC0",
        "01:150003",
        "01:150003",
    ),
    (
        "I directed (REM sends to FAN)",
        " I --- 37:168270 32:153289 --:------ 22F1 003 000307",
        "37:168270",
        "32:153289",
    ),
    (
        "RQ directed (HGI asks CTL)",
        "RQ --- 18:001234 01:150000 --:------ 0002 001 00",
        "18:001234",
        "01:150000",
    ),
    (
        "RP directed (CTL replies to HGI)",
        "RP --- 01:150000 18:001234 --:------ 0002 002 0000",
        "01:150000",
        "18:001234",
    ),
    (
        "W directed (HGI writes to CTL)",
        " W --- 18:001234 01:150000 --:------ 2E04 008 00FFFFFFFFFFFF00",
        "18:001234",
        "01:150000",
    ),
]


@pytest.mark.parametrize(
    ("name", "frame", "expected_src", "expected_dst"),
    _PACKET_CASES,
    ids=[c[0] for c in _PACKET_CASES],
)
def test_packet_src_dst_resolution(
    name: str, frame: str, expected_src: str, expected_dst: str
) -> None:
    """Packet parser resolves positional addresses to correct src/dst."""
    pkt = Packet.from_dict("2026-01-01T00:00:00", {"rssi": "000", "frame": frame})
    assert pkt.src.id == expected_src, f"{name}: got src={pkt.src.id}"
    assert pkt.dst.id == expected_dst, f"{name}: got dst={pkt.dst.id}"
