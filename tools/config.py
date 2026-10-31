"""Machine-local settings; only the example belongs in version control."""
import json
import os
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / '.local-config.json'
SETTINGS = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
DEFAULT_APP = Path(os.environ.get('FACTORIO_APP') or SETTINGS.get('factorio_app') or
                   Path.home() / 'Library/Application Support/Steam/steamapps/common/Factorio/factorio.app').expanduser()
CMAKE = os.environ.get('FACTORIO_CMAKE') or SETTINGS.get('cmake') or 'cmake'
DEFAULT_BUNDLE_ID = 'local.factorio.loaderprobe'
SUPPORTED_SHA256 = '00b014d78df07e05ab1cee853904c8f7b3814ca652c043461a9d49fbad46cdf6'
EXPERIMENTAL_SHA256 = '90e2ebfdb5fd8b3966915f704a0ae99177c2af64ed9267c634ced42bff36d820'
FACTORIO_21_SHA256 = '42218e9676f36687282800e5b6336b049c0f0e45f0f71eb20f90c49ccdec4359'
SUPPORTED_SOURCES = {
    SUPPORTED_SHA256: 'upstream-tested',
    EXPERIMENTAL_SHA256: 'experimental; device testing required',
    FACTORIO_21_SHA256: 'Factorio 2.1.23 Steam; experimental iPhone port',
}
SDL_MAJOR_BY_SHA256 = {SUPPORTED_SHA256: 2, EXPERIMENTAL_SHA256: 2,
                       FACTORIO_21_SHA256: 3}


def validate_patch_layout(macho, sdl_major=2):
    """Check the statically inspected 2.0.77 or 2.1.23 layout without changes.

    This supplements the exact-file allowlist; it does not establish runtime
    compatibility or permit arbitrary binaries with similar instructions.
    """
    def require(condition, message):
        if not condition:
            raise ValueError('Unsupported patch layout: ' + message)

    data = macho.data
    symbols = {s['name']: s for s in macho.symbols() if 'library' not in s}
    segments = {bytes(data[p + 8:p + 24]).rstrip(b'\0'): p
                for c, p, n in macho.commands if c == 0x19}
    require(all(name in segments for name in (b'__TEXT', b'__DATA_CONST', b'__DATA')),
            'missing required segments')
    base = struct.unpack_from('<Q', data, segments[b'__TEXT'] + 24)[0]
    require(base == 0x100000000, 'unexpected image base')
    common = ('_main', '_SDL_Init', '_SDL_CreateWindow', '_SDL_GetVersion')
    version_specific = (('_SDL_GetDisplay', '__ZN9SDLWindow18logDisplayAdaptersEv')
                        if sdl_major == 2 else
                        ('_SDL_GetDisplays', '_SDL_GetVersion_REAL',
                         '__ZN9SDLWindow11logDisplaysEv'))
    require(sdl_major in (2, 3), 'unknown SDL major version')
    for name in common + version_specific:
        require(name in symbols, 'missing symbol ' + name)
        section = symbols[name]['section']
        require(0 < section <= len(macho.sections) and
                macho.sections[section - 1]['name'] == '__text', 'non-code symbol ' + name)
    entry = next((p for c, p, n in macho.commands if c == 0x80000028), None)
    require(entry is not None and struct.unpack_from('<Q', data, entry + 8)[0] ==
            symbols['_main']['address'] - base, 'entrypoint differs from _main')
    require(any(c == 0x80000022 for c, p, n in macho.commands), 'missing classic dyld bindings')

    if sdl_major == 2:
        # Skip only the macOS-specific display-ID logging in SDL2 builds.
        log = symbols['__ZN9SDLWindow18logDisplayAdaptersEv']['address'] - base
        for offset, expected in ((272, '3f0300f1'), (424, 'e00314aa'), (432, '083040f9')):
            require(data[log + offset:log + offset + 4].hex() == expected,
                    'display patch instruction differs at +' + str(offset))
        call = struct.unpack_from('<I', data, log + 428)[0]
        displacement = call & 0x3ffffff
        if displacement & (1 << 25):
            displacement -= 1 << 26
        require(call >> 26 == 0b100101 and base + log + 428 + displacement * 4 ==
                symbols['_SDL_GetDisplay']['address'], 'display patch call target differs')
    else:
        # SDL 3.4.14 is encoded in the game's SDL_GetVersion_REAL function.
        version = symbols['_SDL_GetVersion_REAL']['address'] - base
        require(data[version:version + 8].hex() == 'c0cd9a52a005a072',
                'SDL version instruction differs from 3.4.14')

    first = min(s['offset'] for s in macho.sections if s['offset'] > 0)
    slots_needed = 818 if sdl_major == 2 else 1270  # entry + SDL exports
    start = (first - 16 * slots_needed) & ~15
    require(start >= 32 + struct.unpack_from('<I', data, 20)[0], 'insufficient code padding')
    require(data[start:first] == bytes(first - start), 'code padding is occupied')
    const = segments[b'__DATA_CONST']
    vm, vmsize, fileoff, filesize = struct.unpack_from('<QQQQ', data, const + 24)
    last = max(s['offset'] + s['size'] for s in macho.sections if s['segment'] == '__DATA_CONST')
    slot = (last + 7) & ~7
    require(slot + 8 <= fileoff + filesize, 'no entry pointer padding')
    require(data[slot:fileoff + filesize] == bytes(fileoff + filesize - slot),
            'constant pointer padding is occupied')
    data_vm, data_vmsize, _, data_size = struct.unpack_from('<QQQQ', data, segments[b'__DATA'] + 24)
    bss_slot = (max(s['address'] + s['size'] for s in macho.sections if s['segment'] == '__DATA') + 7) & ~7
    require(bss_slot >= data_vm + data_size, 'pointer padding is not zero-fill')
    slots = (fileoff + filesize - slot) // 8 + (data_vm + data_vmsize - bss_slot) // 8
    require(slots >= slots_needed, 'insufficient pointer padding')

def validate_source(app):
    import hashlib
    binary = app / 'Contents/MacOS/factorio'
    if not binary.is_file():
        raise ValueError(f'Factorio executable not found: {binary}. Run tools/setup.py --app /path/to/factorio.app')
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    if digest not in SUPPORTED_SOURCES:
        raise ValueError(f'Unsupported Factorio executable SHA-256: {digest}\n'
                         'Only explicitly audited Factorio 2.0.77 and 2.1.23 Steam executables are accepted.\n'
                         'Do not bypass this check: a new executable requires a new analysis.')
    for relative in ('Contents/Info.plist', 'Contents/data/base/info.json', 'Contents/data/core/info.json'):
        if not (app / relative).is_file():
            raise ValueError(f'Incomplete Factorio app: missing {relative}')
    if digest in (EXPERIMENTAL_SHA256, FACTORIO_21_SHA256):
        from macho import MachO
        validate_patch_layout(MachO(binary), SDL_MAJOR_BY_SHA256[digest])
    return digest
