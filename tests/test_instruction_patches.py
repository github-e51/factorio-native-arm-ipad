"""Check patch provenance using synthetic code rather than game binaries."""

import struct
from pathlib import Path

import pytest
from entrypoint import apply_instruction_patch, bind_end, reserve_zero_fill, uleb
from macho import MachO, Symbol
from source_profiles import InstructionPatch


class PatchFixture(MachO):
    """Provide a small code section for checking exact instruction patches."""

    def __init__(self) -> None:
        """Initialize an untouched instruction in a synthetic text section."""
        self.path = Path("test-only")
        self.data = bytearray(32) + bytearray.fromhex("e00314aa1f2003d5")
        self.sections = [
            {
                "name": "__text",
                "segment": "__TEXT",
                "address": 0x1000,
                "size": 8,
                "offset": 32,
            }
        ]
        self.commands = []
        self.libraries = []

    def symbols(self) -> list[Symbol]:
        """Expose one named function at the start of the text section."""
        return [
            {
                "name": "_function",
                "type": 0xF,
                "section": 1,
                "desc": 0,
                "address": 0x1000,
            }
        ]


def test_patch_checks_and_records_both_instructions() -> None:
    """Record enough information to verify and reverse an exact patch."""
    macho = PatchFixture()
    patch = InstructionPatch(
        "_function", 0, bytes.fromhex("e00314aa"), bytes.fromhex("daffff17")
    )
    record = apply_instruction_patch(macho, patch, "display")
    assert record == {
        "name": "display",
        "offset": 32,
        "original_bytes": "e00314aa",
        "patched_bytes": "daffff17",
    }
    assert macho.data[32:36] == patch.replacement


def test_wrong_instruction_is_never_patched() -> None:
    """Refuse to apply a known offset to a different instruction sequence."""
    macho = PatchFixture()
    before = bytes(macho.data)
    patch = InstructionPatch("_function", 0, b"wrong", b"new!!")
    with pytest.raises(ValueError, match="Unexpected original instruction"):
        apply_instruction_patch(macho, patch, "display")
    assert bytes(macho.data) == before


def test_patch_cannot_extend_outside_section() -> None:
    """Refuse an offset beyond the named function's file-backed section."""
    patch = InstructionPatch("_function", 8, bytes(4), bytes(4))
    with pytest.raises(ValueError, match="outside"):
        apply_instruction_patch(PatchFixture(), patch, "display")


def test_binding_parser_does_not_stop_at_operand_zero() -> None:
    """Treat zero bytes in symbol names and SLEB operands as data."""
    stream = b"\x11\x40_SDL_Init\x00\x51\x60\x00\x72\x00\x90\x00"
    assert bind_end(stream) == len(stream) - 1
    assert uleb(128) == b"\x80\x01"
    with pytest.raises(ValueError, match="nonnegative"):
        uleb(-1)


def segment_fixture() -> MachO:
    """Create adjacent data and loader segments with stable file offsets."""
    macho = PatchFixture()
    macho.data = bytearray(176)
    macho.sections = []
    macho.commands = [(0x19, 32, 72), (0x19, 104, 72)]
    for position, name, address, size, file_offset, file_size in (
        (32, b"__DATA", 0x100000, 0x4000, 0x1000, 0x2000),
        (104, b"__LINKEDIT", 0x104000, 0x4000, 0x3000, 0x4000),
    ):
        macho.data[position + 8 : position + 24] = name.ljust(16, b"\0")
        struct.pack_into(
            "<QQQQ", macho.data, position + 24, address, size, file_offset, file_size
        )
    return macho


def test_zero_fill_growth_preserves_file_ranges() -> None:
    """Grow only virtual zero-fill and move the loader mapping past the new end."""
    macho = segment_fixture()
    record = reserve_zero_fill(macho, 0x105000)
    assert record["data_vm_size_after"] == 0x8000
    assert record["linkedit_vm_after"] == 0x108000
    assert struct.unpack_from("<QQ", macho.data, 32 + 40) == (0x1000, 0x2000)
    assert struct.unpack_from("<QQ", macho.data, 104 + 40) == (0x3000, 0x4000)


def test_zero_fill_does_not_relocate_a_segment_with_sections() -> None:
    """Refuse to move an unusual loader segment containing addressable sections."""
    macho = segment_fixture()
    macho.sections = [
        {
            "name": "unexpected",
            "segment": "__LINKEDIT",
            "address": 0x104000,
            "size": 4,
            "offset": 0x3000,
        }
    ]
    original = bytes(macho.data)
    with pytest.raises(ValueError, match="containing sections"):
        reserve_zero_fill(macho, 0x105000)
    assert bytes(macho.data) == original
