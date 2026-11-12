"""Small, strict reader for the ARM64 slice of this local Mach-O research target."""

import struct
from pathlib import Path
from typing import NotRequired, TypedDict


class Section(TypedDict):
    """Describe the original address and file range of a Mach-O section."""

    name: str
    segment: str
    address: int
    size: int
    offset: int


class Symbol(TypedDict):
    """Describe one defined or imported Mach-O symbol."""

    name: str
    type: int
    section: int
    desc: int
    address: int
    library: NotRequired[str]
    weak: NotRequired[bool]


DYLIB_COMMANDS = {0xC, 0x80000018, 0x8000001F, 0x80000023}


def cstring(data: bytes | bytearray, offset: int) -> str:
    """Read a terminated UTF-8 string from the supplied binary buffer."""
    end = data.find(b"\0", offset)
    if end < 0:
        raise ValueError("Unterminated Mach-O string")
    return bytes(data[offset:end]).decode("utf-8")


class MachO:
    """Read and retarget the ARM64 slice while preserving original sections."""

    def __init__(self, path: Path | str) -> None:
        """Read a thin or universal executable and inventory its ARM64 commands."""
        self.path = Path(path)
        data = self.path.read_bytes()
        if data[:4] == b"\xca\xfe\xba\xbe":
            count = struct.unpack_from(">I", data, 4)[0]
            for i in range(count):
                cpu, _sub, off, size, _align = struct.unpack_from(
                    ">IIIII", data, 8 + 20 * i
                )
                if cpu == 0x100000C:
                    data = data[off : off + size]
                    break
            else:
                raise ValueError("No ARM64 slice")
        if data[:4] != b"\xcf\xfa\xed\xfe":
            raise ValueError("Expected little-endian 64-bit Mach-O")
        if struct.unpack_from("<I", data, 4)[0] != 0x100000C:
            raise ValueError("Expected ARM64")
        self.data = bytearray(data)
        self.commands: list[tuple[int, int, int]] = []
        self.libraries: list[str] = []
        self.sections: list[Section] = []
        count, size = struct.unpack_from("<II", data, 16)
        pos = 32
        for i in range(count):
            cmd, length = struct.unpack_from("<II", data, pos)
            if length < 8 or pos + length > 32 + size:
                raise ValueError("Malformed load command")
            self.commands.append((cmd, pos, length))
            if cmd in DYLIB_COMMANDS:
                self.libraries.append(
                    cstring(data, pos + struct.unpack_from("<I", data, pos + 8)[0])
                )
            if cmd == 0x19:
                nsects = struct.unpack_from("<I", data, pos + 64)[0]
                for j in range(nsects):
                    sp = pos + 72 + 80 * j
                    name = data[sp : sp + 16].rstrip(b"\0").decode()
                    seg = data[sp + 16 : sp + 32].rstrip(b"\0").decode()
                    addr, sz, off = struct.unpack_from("<QQI", data, sp + 32)
                    self.sections.append(
                        {
                            "name": name,
                            "segment": seg,
                            "address": addr,
                            "size": sz,
                            "offset": off,
                        }
                    )
            pos += length
        assert pos == 32 + size

    def symbols(self) -> list[Symbol]:
        """Read defined symbols and resolve the library ordinals of imports."""
        _cmd, pos, _length = next(c for c in self.commands if c[0] == 2)
        symoff, count, stroff, strsize = struct.unpack_from("<IIII", self.data, pos + 8)
        strings = self.data[stroff : stroff + strsize]
        result: list[Symbol] = []
        for i in range(count):
            name, typ, sect, desc, value = struct.unpack_from(
                "<IBBHQ", self.data, symoff + 16 * i
            )
            if not name or typ & 0xE0:
                continue
            symbol: Symbol = {
                "name": cstring(strings, name),
                "type": typ,
                "section": sect,
                "desc": desc,
                "address": value,
            }
            if typ & 0x0E == 0 and typ & 1:
                ordinal = desc >> 8
                symbol["library"] = (
                    self.libraries[ordinal - 1]
                    if 0 < ordinal <= len(self.libraries)
                    else f"ordinal:{ordinal}"
                )
                symbol["weak"] = bool(desc & 0x40)
            result.append(symbol)
        return result

    def retarget(
        self, destination: Path | str, platform: int, replacements: dict[str, str]
    ) -> None:
        """Change platform and install names on a COPY; do not alter instructions."""
        result = bytearray(self.data)
        commands = []
        for cmd, pos, size in self.commands:
            chunk = bytes(result[pos : pos + size])
            if cmd in DYLIB_COMMANDS:
                old = cstring(chunk, struct.unpack_from("<I", chunk, 8)[0])
                name = replacements.get(old, old).encode() + b"\0"
                newsize = (24 + len(name) + 7) & ~7
                chunk = (
                    struct.pack("<IIIIII", cmd, newsize, 24, 0, 0x10000, 0x10000) + name
                )
                chunk += bytes(newsize - len(chunk))
            elif cmd == 0x32:
                chunk = bytearray(chunk)
                struct.pack_into(
                    "<III", chunk, 8, platform, 26 << 16, (26 << 16) | (2 << 8)
                )
            elif cmd == 0x24:
                chunk = struct.pack(
                    "<IIIIII", 0x32, 24, platform, 26 << 16, (26 << 16) | (2 << 8), 0
                )
            elif cmd == 0x1D:  # signature is regenerated by codesign
                continue
            commands.append(chunk)
        payload = b"".join(commands)
        first_section = min(s["offset"] for s in self.sections if s["offset"] > 0)
        if 32 + len(payload) > first_section:
            raise ValueError("Not enough load-command space")
        oldsize = struct.unpack_from("<I", result, 20)[0]
        result[32 : 32 + max(oldsize, len(payload))] = payload + bytes(
            max(oldsize, len(payload)) - len(payload)
        )
        struct.pack_into("<II", result, 16, len(commands), len(payload))
        destination = Path(destination)
        destination.write_bytes(result)
        destination.chmod(0o755)
