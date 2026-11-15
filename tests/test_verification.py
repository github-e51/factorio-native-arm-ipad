"""Reject incomplete benchmark evidence and assets from the wrong source."""

import json
import plistlib
import struct
from dataclasses import replace
from pathlib import Path

import pytest
from source_profiles import BASE_2077
from verify import (
    MEMORY_LIMIT_ENTITLEMENT,
    benchmark_checksum,
    parse_signature_entitlements,
    verify_assets,
)


def test_requires_a_complete_single_benchmark() -> None:
    """Accept a complete result and reject crashes or ambiguous repeated checksums."""
    log = "Performed 120 updates\n  checksum: 123\nGoodbye\n"
    assert benchmark_checksum(log) == "123"
    for invalid in (
        "checksum: 123",
        log + "checksum: 999\n",
        log + "Factorio crashed.",
    ):
        with pytest.raises(RuntimeError):
            benchmark_checksum(invalid)


def test_requires_expansion_assets_and_matching_source(tmp_path: Path) -> None:
    """Require the selected DLC as well as base data and an executable identity."""
    profile = replace(BASE_2077, mods=(("base", "2.0.77"), ("space-age", "2.0.77")))
    (tmp_path / "data/base").mkdir(parents=True)
    (tmp_path / "data/base/info.json").write_text('{"version":"2.0.77"}')
    with pytest.raises(RuntimeError, match="space-age"):
        verify_assets(tmp_path, profile)
    (tmp_path / "data/space-age").mkdir()
    (tmp_path / "data/space-age/info.json").write_text('{"version":"2.0.77"}')
    marker = tmp_path / "data/.factorio-source.json"
    marker.write_text(json.dumps({"source_sha256": "wrong"}))
    with pytest.raises(RuntimeError, match="another executable"):
        verify_assets(tmp_path, profile)
    marker.write_text(json.dumps({"source_sha256": profile.sha256}))
    verify_assets(tmp_path, profile)


def test_reads_memory_capability_from_signed_executable_blob() -> None:
    """Decode the same XML entitlement format embedded in the real signed Mach-O."""
    xml = plistlib.dumps({MEMORY_LIMIT_ENTITLEMENT: True, "get-task-allow": True})
    blob = struct.pack(">II", 0xFADE7171, 8 + len(xml)) + xml
    signature = struct.pack(">IIIII", 0xFADE0CC0, 20 + len(blob), 1, 5, 20) + blob
    assert parse_signature_entitlements(signature)[MEMORY_LIMIT_ENTITLEMENT] is True
    with pytest.raises(RuntimeError, match="Invalid code signature container"):
        parse_signature_entitlements(signature[:-1])


@pytest.mark.parametrize(
    "signature",
    [
        b"",
        bytes(12),
        struct.pack(">III", 0xFADE0CC0, 12, 1),
        struct.pack(">IIIII", 0xFADE0CC0, 20, 1, 5, 1000),
    ],
)
def test_rejects_invalid_signed_entitlement_ranges(signature: bytes) -> None:
    """Reject truncated or out-of-bounds signing metadata before reading it."""
    with pytest.raises(RuntimeError):
        parse_signature_entitlements(signature)
