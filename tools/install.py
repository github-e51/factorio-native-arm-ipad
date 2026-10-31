#!/usr/bin/env python3
"""Build, sign and install Factorio on a connected iPhone or iPad in one step.

Run through "Install Factorio.command", which prepares Xcode, Python and CMake
first. This script picks the device, signing team and bundle ID, remembers them
in the ignored .local-config.json, builds with xcodebuild, installs, and starts
the app. Re-run it to update the app or renew an expired signing profile.
"""
import argparse
import getpass
import json
import os
import plistlib
import re
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from config import ROOT, CONFIG_PATH

DUO_PRODUCT_TYPES = {'iPhone19,4'}
DUO_XCODE = (27, 2)
LOG = ROOT / 'reports/install-build.log'
APP = ROOT / 'build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app'


def say(text=''):
    print(text, flush=True)


def step(number, text):
    say(f'\n[{number}/5] {text}')


def stop(text):
    say('\n' + text)
    raise SystemExit(1)


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ''


def version(text):
    return tuple(int(part) for part in re.findall(r'\d+', text)[:2])


def load_settings():
    return json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}


def save_settings(settings):
    CONFIG_PATH.write_text(json.dumps(settings, indent=2) + '\n')


def choose(items, label, describe):
    if len(items) == 1:
        return items[0]
    for index, item in enumerate(items, 1):
        say(f'  {index}. {describe(item)}')
    while True:
        answer = ask(f'Choose a {label} [1-{len(items)}]: ')
        if answer.isdigit() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]


def devices():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / 'devices.json'
        subprocess.run(['xcrun', 'devicectl', 'list', 'devices', '--json-output', str(output)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not output.exists():
            return []
        found = json.loads(output.read_text()).get('result', {}).get('devices', [])
    return [d for d in found if d.get('hardwareProperties', {}).get('reality') == 'physical'
            and d.get('hardwareProperties', {}).get('deviceType') in ('iPhone', 'iPad')]


def device_name(device):
    properties = device.get('deviceProperties', {})
    return f"{properties.get('name', 'device')} (iOS {properties.get('osVersionNumber', '?')})"


def pick_device(settings):
    while True:
        found = devices()
        ready = [d for d in found if d.get('connectionProperties', {}).get('pairingState') == 'paired'
                 and d.get('connectionProperties', {}).get('tunnelState') != 'unavailable']
        remembered = [d for d in ready if d['identifier'] == settings.get('device_id')]
        if remembered:
            return remembered[0]
        if ready:
            return choose(ready, 'device', device_name)
        say('No iPhone or iPad is ready. Check that it is:')
        say('  - connected to this Mac with a USB cable, unlocked, and on its home screen;')
        say('  - trusting this Mac (tap Trust on the device and enter its passcode);')
        say('  - shown in Xcode under Window > Devices and Simulators, with preparation finished;')
        say('  - an iPhone Duo: unfolded.')
        if found:
            say('Seen but not ready: ' + ', '.join(device_name(d) for d in found))
        if ask('Press Return to look again, or type q to quit: ').lower() == 'q':
            raise SystemExit(1)


def xcode_teams():
    exported = subprocess.run(['defaults', 'export', 'com.apple.dt.Xcode', '-'], capture_output=True)
    teams = {}
    if exported.returncode == 0 and exported.stdout:
        def walk(value):
            if isinstance(value, dict):
                if 'teamID' in value:
                    teams[value['teamID']] = (value.get('teamName') or value['teamID'],
                                              bool(value.get('isFreeProvisioningTeam')))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(plistlib.loads(exported.stdout))
    if not teams:
        # Fall back to the organisational unit of existing development certificates.
        pems = subprocess.run(['security', 'find-certificate', '-a', '-c', 'Apple Development', '-p'],
                              capture_output=True, text=True).stdout
        for pem in re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', pems, re.S):
            subject = subprocess.run(['openssl', 'x509', '-noout', '-subject'], input=pem,
                                     capture_output=True, text=True).stdout
            match = re.search(r'OU\s*=\s*([A-Z0-9]{10})', subject)
            if match:
                teams.setdefault(match.group(1), (match.group(1), False))
    return teams


def pick_team(settings):
    while True:
        teams = xcode_teams()
        if settings.get('team_id') in teams:
            return settings['team_id'], teams[settings['team_id']][1]
        if teams:
            team = choose(sorted(teams), 'signing team',
                          lambda t: f"{teams[t][0]} ({t}){' - free account' if teams[t][1] else ''}")
            return team, teams[team][1]
        say('Xcode has no Apple Account yet. In Xcode, open Xcode > Settings > Apple Accounts,')
        say('click +, choose Apple Account, and sign in. A free account works.')
        subprocess.run(['open', '-a', 'Xcode'])
        if ask('Press Return once you have signed in, or type q to quit: ').lower() == 'q':
            raise SystemExit(1)


def installed_factorio(device):
    """Reuse the bundle ID of an already installed copy so its saves are kept."""
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / 'apps.json'
        subprocess.run(['xcrun', 'devicectl', 'device', 'info', 'apps', '--device', device['identifier'],
                        '--json-output', str(output)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not output.exists():
            return None
        apps = json.loads(output.read_text()).get('result', {}).get('apps', [])
    found = sorted(app['bundleIdentifier'] for app in apps
                   if app.get('name') == 'Factorio' and app.get('bundleIdentifier'))
    if not found:
        return None
    say('Factorio is already on this device. Choose the copy to update (its saves are kept):')
    return choose(found, 'copy', str)


def pick_bundle_id(settings, device, override):
    if override:
        return override
    if settings.get('bundle_id'):
        return settings['bundle_id']
    existing = installed_factorio(device)
    if existing:
        return existing
    # Bundle IDs are unique across all Apple accounts, so add a random suffix.
    user = re.sub(r'[^a-z0-9]', '', getpass.getuser().lower()) or 'player'
    return f'com.{user}.factorio.{secrets.token_hex(3)}'


def diagnose(log):
    hints = [
        ('No Account for Team', 'Xcode is not signed in to the chosen team. Check Xcode > Settings > Apple Accounts.'),
        ('Failed Registering Bundle Identifier', 'That bundle ID is taken. Delete "bundle_id" from .local-config.json and run again.'),
        ('is not available for registration', 'That bundle ID is taken. Delete "bundle_id" from .local-config.json and run again.'),
        ('maximum number of', 'A free account allows 3 sideloaded apps at a time. Delete one you built yourself from the device.'),
        ('Unsupported Factorio executable', 'Your Factorio is not the supported version. See docs/INSTALL.md, step 3.'),
        ('Developer Mode', 'Turn on Developer Mode on the device: Settings > Privacy & Security > Developer Mode.'),
        ('requires a development team', 'Signing failed; sign in to Xcode > Settings > Apple Accounts and run again.'),
        ('No space left', 'The Mac is out of disk space. The build needs about 15 GB free.'),
    ]
    text = log.read_text(errors='replace') if log.exists() else ''
    for needle, hint in hints:
        if needle in text:
            return hint
    return None


def build(team, bundle_id):
    LOG.parent.mkdir(exist_ok=True)
    command = ['xcodebuild', '-project', str(ROOT / 'FactorioProbe.xcodeproj'), '-scheme', 'FactorioProbe',
               '-configuration', 'Debug', '-sdk', 'iphoneos', '-destination', 'generic/platform=iOS',
               '-derivedDataPath', str(ROOT / 'build/Xcode'), f'DEVELOPMENT_TEAM={team}',
               f'PRODUCT_BUNDLE_IDENTIFIER={bundle_id}', 'CODE_SIGN_STYLE=Automatic',
               '-allowProvisioningUpdates', '-allowProvisioningDeviceRegistration', 'build']
    say(f'Building. The first build takes 10-30 minutes; updates are quicker. Log: {LOG.relative_to(ROOT)}')
    start = time.monotonic()
    with LOG.open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        while process.poll() is None:
            elapsed = int(time.monotonic() - start)
            print(f'\r  still building... {elapsed // 60}m {elapsed % 60:02d}s', end='', flush=True)
            time.sleep(5)
    say()
    if process.returncode:
        tail = LOG.read_text(errors='replace').splitlines()
        errors = [line for line in tail if 'error:' in line][:8]
        say('\n'.join(errors or tail[-15:]))
        stop('The build failed. ' + (diagnose(LOG) or f'See {LOG.relative_to(ROOT)} for details.'))


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-id', help='Use this bundle ID instead of the remembered or generated one')
    parser.add_argument('--no-launch', action='store_true', help='Install without starting the app')
    args = parser.parse_args()
    settings = load_settings()

    step(1, 'Looking for your iPhone or iPad')
    device = pick_device(settings)
    properties = device.get('deviceProperties', {})
    say('Using ' + device_name(device))
    if properties.get('developerModeStatus') not in (None, 'enabled'):
        stop('Developer Mode is off. On the device, open Settings > Privacy & Security > Developer Mode,\n'
             'turn it on, restart when asked, and choose Turn On after the restart. Then run this again.')
    sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-version'], text=True).strip()
    if device.get('hardwareProperties', {}).get('productType') in DUO_PRODUCT_TYPES:
        if version(sdk) < DUO_XCODE:
            say(f'Warning: iPhone Duo builds need Xcode {DUO_XCODE[0]}.{DUO_XCODE[1]} or later; this Xcode has the iOS {sdk} SDK.')
            say('Install the newer Xcode from the App Store if the game does not fill the inner display.')
        if version(properties.get('osVersionNumber', '0')) < DUO_XCODE:
            say('Note: iOS 27.2 or later is recommended on iPhone Duo; on 27.1 a Bluetooth trackpad\n'
                'pointer only works with the workarounds described in docs/CONTROLS.md.')

    step(2, 'Choosing your Apple signing team')
    team, free = pick_team(settings)
    say(f'Using team {team}' + (' (free account: the app must be reinstalled every 7 days)' if free else ''))

    bundle_id = pick_bundle_id(settings, device, args.bundle_id)
    settings.update(device_id=device['identifier'], team_id=team, bundle_id=bundle_id)
    save_settings(settings)
    say(f'App ID: {bundle_id}')

    step(3, 'Building Factorio for iOS from your own Mac copy')
    build(team, bundle_id)

    step(4, 'Installing on ' + properties.get('name', 'the device'))
    code, output = run(['xcrun', 'devicectl', 'device', 'install', 'app', '--device', device['identifier'], str(APP)])
    if code:
        say(output.strip()[-1500:])
        stop('Installing failed. Unlock the device, keep it connected, and run this again.')

    step(5, 'Starting Factorio')
    if args.no_launch:
        say('Installed. Open Factorio from the home screen.')
        return
    code, output = run(['xcrun', 'devicectl', 'device', 'process', 'launch', '--terminate-existing',
                        '--device', device['identifier'], bundle_id])
    if code and re.search(r'untrusted|not been explicitly trusted|invalid code signature|profile', output, re.I):
        say('The device needs to trust your developer certificate once:')
        say('  Settings > General > VPN & Device Management > your Apple Account > Trust.')
        say('Then open Factorio from the home screen.')
    elif code and re.search(r'Locked|could not be, unlocked', output):
        say('Installed. The device is locked, so it could not be started from the Mac.')
        say('Unlock it and open Factorio from the home screen.')
    elif code:
        say(output.strip()[-800:])
        say('Installed, but it could not be started from the Mac. Open Factorio from the home screen.')
    else:
        say('Factorio is starting on the device. The first start takes about 30 seconds;')
        say('tap Confirm on the Steam notice. You can unplug the cable now.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        stop('Stopped.')
