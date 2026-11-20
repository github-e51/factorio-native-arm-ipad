#!/usr/bin/env python3
"""Verify a locally built app without depending on somebody else's test logs."""
import argparse
import json
import re
import struct
import subprocess
from pathlib import Path
from audit import ROOT, DEFAULT_APP, sdk_path, mobile_path, TBDLoader
import yaml
from config import SUPPORTED_SOURCES, validate_source
from macho import MachO, packed_version

def require(condition,message):
    if not condition: raise RuntimeError(message)

def verify_benchmark(log, expected_checksum=2892897386):
    match=re.search(r'^\s*checksum: (\d+)',log,re.M)
    require(match and match.group(1)==str(expected_checksum),
            'Probe-map simulation checksum differs or is missing')
    require('Performed 120 updates' in log and 'Goodbye' in log,'Incomplete benchmark')
    return dict(ticks=120,checksum=match.group(1),scope='64x64 probe map with selected mods only')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk',choices=['iphoneos','iphonesimulator'],default='iphoneos')
    parser.add_argument('--signed-app',type=Path,help='Also check this Xcode product and its bundle identifier')
    parser.add_argument('--bundle-id',help='Expected bundle identifier of --signed-app')
    parser.add_argument('--benchmark-log',type=Path,help='Optional log from your own 120-tick probe benchmark')
    parser.add_argument('--benchmark-checksum',type=int,default=2892897386,
                        help='Expected checksum measured on the original Mac with the same map and mods; default: upstream base game')
    args=parser.parse_args()
    original=DEFAULT_APP/'Contents/MacOS/factorio'
    source_sha256 = validate_source(DEFAULT_APP)
    source=MachO(original)
    report={}
    for sdk,folder,platform in [('iphoneos','build/iphoneos/FactorioProbe.app',2),('iphonesimulator','build/FactorioProbe.app',7)]:
        if sdk!=args.sdk: continue
        app=ROOT/folder
        patched=MachO(app/'FactorioProbe')
        built_sdk = next(struct.unpack_from('<I', patched.data, p+16)[0]
                         for c,p,n in patched.commands if c==0x32)
        selected_sdk = packed_version(subprocess.check_output(
            ['xcrun','--sdk',sdk,'--show-sdk-version'],text=True).strip())
        require(built_sdk == selected_sdk,
                'Game SDK version differs from selected Xcode SDK; rebuild to enable current device layouts')
        manifest=json.loads((ROOT/f'reports/entrypoint-patch-{sdk}.json').read_text())
        require(manifest.get('source_sha256') == source_sha256,
                'Build source differs from the current installation; rebuild before verifying')
        restored=bytearray(patched.data)
        seen=set()
        for entry in manifest['sdl_redirects']+manifest['platform_patches']:
            offset=entry['offset']
            require(offset not in seen,'Overlapping instruction patches')
            seen.add(offset)
            before=bytes.fromhex(entry['original_bytes'])
            require(source.data[offset:offset+len(before)]==before,'Incorrect original instruction in manifest')
            restored[offset:offset+len(before)]=before
        for section in source.sections:
            if section['offset'] and section['size']:
                a,b=section['offset'],section['offset']+section['size']
                require(restored[a:b]==source.data[a:b],f'Undocumented changes in {section["name"]}')
        modules=[app/'FactorioProbe']+list((app/'Frameworks').glob('*.dylib'))
        sdk_root=sdk_path(sdk)
        for module in modules:
            m=MachO(module)
            platforms=[struct.unpack_from('<I',m.data,p+8)[0] for c,p,n in m.commands if c==0x32]
            require(platforms==[platform],f'Wrong platform in {module.name}: {platforms}')
            for lib in m.libraries:
                if '/Versions/' in lib:
                    # iOS IOKit deliberately keeps a versioned install name.
                    # Accept only a name declared by this exact iOS SDK.
                    tbd=sdk_root/(mobile_path(lib).lstrip('/')+'.tbd')
                    require(tbd.exists(),f'Non-iOS versioned library: {lib}')
                    docs=list(yaml.load_all(tbd.read_text(),Loader=TBDLoader))
                    require(any(d.get('install-name')==lib for d in docs),f'Library not declared by iOS SDK: {lib}')
        if sdk=='iphoneos':
            require(not any('SIMULATOR ONLY' in p['name'] for p in manifest['platform_patches']),'Simulator bypass in device build')
        subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
        report[sdk]=dict(modules_verified=len(modules),sdl_redirects=len(manifest['sdl_redirects']),
                         platform_patches=manifest['platform_patches'],undocumented_section_changes=0,
                         signature='ad-hoc; device provisioning still required')
    if args.benchmark_log:
        report['simulation']=verify_benchmark(args.benchmark_log.read_text(),args.benchmark_checksum)
    report['source_sha256']=source_sha256
    report['source_status']=SUPPORTED_SOURCES[source_sha256]
    signed_app=args.signed_app
    if signed_app:
        import plistlib
        require((signed_app/'embedded.mobileprovision').is_file(),'Missing development provisioning profile')
        subprocess.run(['codesign','--verify','--deep','--strict',str(signed_app)],check=True)
        identifier=plistlib.loads((signed_app/'Info.plist').read_bytes())['CFBundleIdentifier']
        if args.bundle_id: require(identifier==args.bundle_id,'Xcode product bundle identifier differs')
        require((signed_app/'FactorioProbe').read_bytes()[:4]==b'\xcf\xfa\xed\xfe','Missing ARM64 executable')
        # Signing changes signatures, but must not change the patched game sections.
        signed_macho=MachO(signed_app/'FactorioProbe')
        for section in patched.sections:
            if section['offset'] and section['size']:
                a,b=section['offset'],section['offset']+section['size']
                require(signed_macho.data[a:b]==patched.data[a:b],f'Xcode product differs in {section["name"]}')
        require((signed_app/'data/base/info.json').is_file(),'Missing bundled base-game assets')
        report['development_signed_app']=dict(path=str(signed_app),bundle_id=identifier)
    (ROOT/'reports/verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
