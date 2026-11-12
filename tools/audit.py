"""Reproducible, read-only binary and iOS SDK import inventory."""
import argparse
import hashlib
import json
import plistlib
import re
import subprocess
from pathlib import Path
from typing import TypedDict

import yaml
from config import DEFAULT_APP, ROOT, validate_source
from macho import MachO


class LibraryAudit(TypedDict):
    """Describe imports provided or missing from a single SDK library."""

    original: str
    mobile: str
    sdk_has_exports: bool
    import_count: int
    missing: list[dict[str, object]]


class TBDLoader(yaml.SafeLoader):
    """Read Apple's tagged YAML text-based library stubs."""
TBDLoader.add_constructor('!tapi-tbd', lambda loader, node: loader.construct_mapping(node, deep=True))
TBDLoader.add_constructor('!tapi-tbd-v3', lambda loader, node: loader.construct_mapping(node, deep=True))

def sdk_path(sdk: str) -> Path:
    """Find the selected Xcode SDK root."""
    return Path(subprocess.check_output(['xcrun', '--sdk', sdk, '--show-sdk-path'], text=True).strip())

def mobile_path(path: str) -> str:
    """Remove macOS framework version components from install names."""
    return re.sub(r'/Versions/[^/]+/', '/', path)

def supports_ios_arm64(targets: list[str]) -> bool:
    """Recognize iOS system stubs used when linking an ARM64 app, including SDK 27."""
    supported = {'arm64-ios', 'arm64-ios-simulator', 'arm64e-ios', 'arm64e.x1-ios'}
    return not targets or any(target in supported for target in targets)

def sdk_exports(sdk: Path, install_name: str, seen: set[str] | None = None) -> set[str]:
    """Collect iOS ARM64 exports, recursively following system reexports."""
    seen = set() if seen is None else seen
    if install_name in seen:
        return set()
    seen.add(install_name)
    stem = sdk / install_name.lstrip('/')
    path = stem.with_suffix('.tbd') if stem.suffix == '.dylib' else Path(str(stem)+'.tbd')
    if not path.exists():
        return set()
    result = set()
    for doc in yaml.load_all(path.read_text(), Loader=TBDLoader):
        if not doc:
            continue
        for group in doc.get('exports', []) + doc.get('reexports', []):
            targets = group.get('targets', [])
            # Exclude macCatalyst and other platforms from SDK symbol availability.
            if not supports_ios_arm64(targets):
                continue
            result.update(group.get('symbols', []))
            result.update(group.get('weak-symbols', []))
            result.update(group.get('thread-local-symbols', []))
            for name in group.get('objc-classes', []):
                result.update(('_OBJC_CLASS_$_'+name, '_OBJC_METACLASS_$_'+name))
            for name in group.get('objc-ivars', []):
                result.add('_OBJC_IVAR_$_'+name)
            for name in group.get('objc-eh-types', []):
                result.add('_OBJC_EHTYPE_$_'+name)
        for group in doc.get('reexported-libraries', []):
            if not supports_ios_arm64(group.get('targets', [])):
                continue
            for library in group['libraries']:
                result.update(sdk_exports(sdk, library, seen))
    return result

def audit(app: Path, sdk_name: str) -> None:
    """Write import and entrypoint reports from the validated game and local SDK."""
    validate_source(app)
    binary = app / 'Contents/MacOS/factorio'
    macho = MachO(binary)
    symbols = macho.symbols()
    imports = [s for s in symbols if 'library' in s]
    sdk = sdk_path(sdk_name)
    libraries: list[LibraryAudit] = []
    for library in macho.libraries:
        destination = mobile_path(library)
        exports = sdk_exports(sdk, destination)
        required = [s for s in imports if s['library'] == library]
        missing = [s for s in required if s['name'] not in exports]
        libraries.append({'original': library, 'mobile': destination, 'sdk_has_exports': bool(exports),
                              'import_count': len(required), 'missing': missing})
    info = plistlib.loads((app/'Contents/Info.plist').read_bytes())
    result = {'source': str(binary), 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                  'version': info['CFBundleShortVersionString'], 'sdk': str(sdk),
                  'defined_symbols': len(symbols)-len(imports), 'imports': len(imports), 'libraries': libraries,
                  'sections': macho.sections,
                  'entrypoints': [s for s in symbols if s['name'] in ('_main','_SDL_Init','_SDL_CreateWindow','_SDL_GetVersion','_lua_version')]}
    out = ROOT/'reports'
    out.mkdir(exist_ok=True)
    (out/f'audit-{sdk_name}.json').write_text(json.dumps(result, indent=2)+'\n')
    raw = out/'raw'
    raw.mkdir(exist_ok=True)
    (raw/'symbols.json').write_text(json.dumps(symbols))
    lines = [f'# Factorio {result["version"]}: ARM64 import audit', '',
             f'Source SHA-256: `{result["sha256"]}`', '',
             f'{result["defined_symbols"]:,} defined symbols; {len(imports)} imported symbols.', '',
             'This checks SDK exports, not ABI or runtime compatibility. Missing weak imports may be optional.', '',
             '| Library | Imports | Absent from SDK exports |', '|---|---:|---:|']
    for lib in libraries:
        lines.append(f'| {Path(lib["original"]).name} | {lib["import_count"]} | {len(lib["missing"])} |')
    (out/f'audit-{sdk_name}.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, default=DEFAULT_APP)
    parser.add_argument('--sdk', choices=['iphoneos','iphonesimulator'], default='iphoneos')
    args = parser.parse_args()
    audit(args.app, args.sdk)
