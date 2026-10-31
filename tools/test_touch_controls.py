#!/usr/bin/env python3
"""Run the actual UIKit controls through layout/input checks in a simulator."""
import argparse
import json
import plistlib
import shutil
import subprocess
import time
from pathlib import Path
from audit import ROOT, sdk_path
from config import DEFAULT_APP, SDL_MAJOR_BY_SHA256, validate_source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True, help='Booted simulator UDID')
    args=parser.parse_args()
    sdl_major=SDL_MAJOR_BY_SHA256[validate_source(DEFAULT_APP)]
    source=ROOT/'build/vendor'/('SDL-release-2.30.9' if sdl_major==2 else 'SDL-release-3.4.14')
    app=ROOT/'build/TouchControlsTests.app'
    app.mkdir(parents=True, exist_ok=True)
    bundle='local.factorio.touchcontrolstests'
    (app/'Info.plist').write_bytes(plistlib.dumps(dict(
        CFBundleExecutable='TouchControlsTests', CFBundleIdentifier=bundle,
        CFBundleName='Factorio Controls Tests', CFBundlePackageType='APPL',
        CFBundleVersion='1', CFBundleShortVersionString='1.0',
        CFBundleSupportedPlatforms=['iPhoneSimulator'], UIDeviceFamily=[1,2],
        MinimumOSVersion='26.0', LSRequiresIPhoneOS=True, UILaunchScreen={},
        UIApplicationSceneManifest=dict(UIApplicationSupportsMultipleScenes=False,
            UISceneConfigurations=dict(UIWindowSceneSessionRoleApplication=[dict(
                UISceneConfigurationName='Controls', UISceneDelegateClassName='LayoutApp')])),
        UISupportedInterfaceOrientations=['UIInterfaceOrientationLandscapeLeft',
                                         'UIInterfaceOrientationLandscapeRight'])))
    include=['-I'+str(source/'include')]
    if sdl_major==3: include.append('-I'+str(source/'include/SDL3'))
    subprocess.run(['xcrun','--sdk','iphonesimulator','clang',
                    '-target','arm64-apple-ios26.0-simulator',
                    '-isysroot',str(sdk_path('iphonesimulator')),'-fobjc-arc',
                    f'-DFPI_SDL_MAJOR={sdl_major}',*include,
                    str(ROOT/'tests/TouchControlsHarness.m'),'-framework','UIKit','-framework','GameController',
                    '-framework','Foundation','-framework','CoreGraphics','-framework','QuartzCore',
                    '-o',str(app/'TouchControlsTests')],check=True)
    subprocess.run(['codesign','--force','--sign','-',str(app)],check=True)
    subprocess.run(['xcrun','simctl','install',args.device,str(app)],check=True)
    container=Path(subprocess.check_output(
        ['xcrun','simctl','get_app_container',args.device,bundle,'data'],text=True).strip())
    result=container/'Documents/result.json'
    result.unlink(missing_ok=True)
    subprocess.run(['xcrun','simctl','launch','--terminate-running-process',args.device,bundle],check=True)
    deadline=time.monotonic()+30
    while not result.exists():
        if time.monotonic()>deadline: raise RuntimeError('Control tests did not produce a result')
        time.sleep(0.2)
    output=ROOT/'reports/touch-controls'
    shutil.copytree(container/'Documents',output,dirs_exist_ok=True)
    report=json.loads(result.read_text())
    print(json.dumps(report,indent=2))
    print('Screenshots:',output)
    raise SystemExit(bool(report['failures']))

if __name__=='__main__': main()
