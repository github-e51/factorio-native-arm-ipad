# Factorio on iPad and iPhone Duo

An experimental port that runs **your own copy of Factorio for macOS** natively
on an iPad or iPhone Duo. It builds an iOS app on your Mac from the game you
bought on Steam, signs it with your Apple Account, and installs it on your
device. The game then runs entirely on the device, with touch controls,
on-screen keyboard, portrait layout, and Bluetooth keyboard and trackpad support.

This is not an official client from Wube Software. **Factorio itself is not
included:** no game files, prebuilt apps, certificates or saves are in this
repository, and there is no downloadable app. Apple requires each sideloaded
app to be signed by its installer, and Factorio's files may not be shared.

## What you need

- An **Apple Silicon Mac** (M1 or newer) with about 40 GB free
- **Xcode** from the App Store: **27.2 or later** for iPhone Duo
- **Factorio 2.1.23 for macOS from Steam** (2.0.77 also works on iPad)
- An **Apple Account**; a free one works, but the app must be reinstalled every 7 days
- One of these devices and a USB cable:

| Device | Status |
|---|---|
| iPhone Duo, **iOS 27.2 recommended** | Plays: Space Age menu, saves, touch, Bluetooth keyboard and trackpad |
| iPad with M1 or newer, iPadOS 26+ | Plays: tutorial, mining, inventory, text entry, saving and loading, audio |
| Other iPhones and iPads | Untested |

## Install

**Follow the step-by-step [install guide](docs/INSTALL.md).** It starts from
installing Xcode and needs no programming knowledge.

In short: install Xcode and sign in with your Apple Account, install the exact
supported Factorio version through Steam, turn on Developer Mode on the
device, connect it, and double-click **`Install Factorio.command`**. The
installer sets up everything else, builds the app from your game, installs
it, and starts it. Run it again later to update or renew the app; your saves
are kept.

## Documentation

| | |
|---|---|
| [Install guide](docs/INSTALL.md) | Step-by-step setup for iPad and iPhone Duo, renewing, saves, problems |
| [Controls](docs/CONTROLS.md) | Touch controls and modes, portrait layout, keyboard, trackpad and controllers |
| [iPhone Duo](docs/IPHONE_DUO.md) | Duo requirements, inner display, display checks |
| [Development](docs/DEVELOPMENT.md) | Manual Xcode and Terminal builds, supported executables, tests, troubleshooting |
| [Architecture](docs/ARCHITECTURE.md) | How the macOS executable runs on iOS, and what is still unverified |

## Status and limitations

Factorio's own engine and Metal renderer run unchanged. The port adapts a copy
of the macOS executable for iOS, redirects its SDL calls to an iOS build of SDL,
and fills in the few macOS functions the game needs. The original game is never
modified, and only exactly checked game versions are accepted.

Large factories, long sessions, multiplayer, controllers, fold/unfold while
running, and the full range of building actions are untested. Steam features
(achievements, workshop, login) aren't available. A Steam update to a newer
Factorio version stops new builds until the port supports it; an installed app
keeps working. See [Architecture](docs/ARCHITECTURE.md#verified-behavior-and-remaining-gaps).

## Licence

The porting code, tools and documentation are under the [MIT License](LICENSE).
Factorio, SDL and other components: [scope and notices](THIRD_PARTY_NOTICES.md).
