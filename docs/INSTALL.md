# Install guide: Factorio on iPad or iPhone Duo

This guide is for people who have never used Xcode. It takes about an hour the
first time, mostly waiting for downloads and the first build. You'll need:

- **An Apple Silicon Mac** (M1 or newer) with about **40 GB free**: roughly
  15 GB for Xcode and 20 GB for the build.
- **Factorio for macOS, bought on Steam**, installed on that Mac. The app is
  built from *your* copy; nothing of the game is downloaded or shared.
- **An Apple Account** (the one you use for the App Store is fine). A free
  account works.
- **The iPad or iPhone Duo** and a **USB cable** to connect it to the Mac.

| Device | What works |
|---|---|
| **iPad** with an M1 chip or newer, iPadOS 26 or later | Tested on an 11-inch iPad Pro (M1) |
| **iPhone Duo**, **iOS 27.2** recommended | Tested; needs **Xcode 27.2** or later to build |
| Other iPhones and iPads | Untested. They may fail to start the game's graphics |

There is no ready-made app to download, and there can't be: the app contains
Factorio's own files, which may not be shared, and Apple requires every
sideloaded app to be signed with the installer's own Apple Account. The
installer script below does all the building and signing for you.

## 1. Install Xcode

Xcode is Apple's free tool for building apps.

1. Open the **App Store** on the Mac, search for **Xcode**, and click **Get**.
   It's a large download. For iPhone Duo you need **Xcode 27.2 or later**; if
   your Mac already has an older Xcode, update it from the App Store.
2. Open **Xcode** once from Applications. Agree to the licence and enter your
   Mac password if asked.
3. When Xcode asks which platforms to install, make sure **iOS** is selected,
   and wait for it to finish. (If it didn't ask: **Xcode → Settings →
   Components**, then install **iOS**.)

## 2. Sign in to Xcode with your Apple Account

1. In Xcode, open **Xcode → Settings → Apple Accounts**.
2. Click **+**, choose **Apple Account**, and sign in.

You don't need to pay for the Apple Developer Program. With a free account the
app stops opening after **7 days**; run the installer again to renew it, and
your saves are kept. A free account can also have at most 3 self-built apps on
a device at once. With the paid program ($99 a year), the app lasts a year.

## 3. Install the right version of Factorio on the Mac

The port works only with an exact, checked version of the game, because it
patches specific locations in the game's code:

| Device | Factorio version (macOS, Steam) |
|---|---|
| iPhone Duo | **2.1.23** (build 87750) |
| iPad | **2.1.23**, or 2.0.77 (build 84539) |

1. Install Factorio from **Steam** on the Mac and let it finish downloading.
   Start it once to check it runs, then quit it.
2. The version shows in the top-left corner of Factorio's main menu.
3. Stop Steam from updating it later, so a new game version doesn't break your
   next build: in Steam, right-click **Factorio → Properties → Updates**, and
   choose **Only update this game when I launch it**.

If you own **Space Age**, it's included automatically.

## 4. Get this project

1. On this project's GitHub page, click the green **Code** button, then
   **Download ZIP**.
2. Open the downloaded ZIP to unpack it. You get a folder such as
   `factorio-native-arm-ipad-main`. Leave it in Downloads or move it anywhere.

## 5. Prepare the iPad or iPhone

1. **iPhone Duo:** unfold it. The game runs on the inner display.
2. Connect the device to the Mac with the cable and unlock it.
3. On the device, tap **Trust** when it asks whether to trust this computer,
   and enter its passcode.
4. On the Mac, Xcode may say it is preparing the device. Let it finish; you can
   watch in Xcode under **Window → Devices and Simulators**.
5. **Turn on Developer Mode** on the device:
   **Settings → Privacy & Security → Developer Mode**, turn it on, tap
   **Restart**, and after the restart tap **Turn On** and enter the passcode.
   The Developer Mode switch only appears after the device has been connected
   to Xcode, so do steps 2–4 first.

## 6. Run the installer

1. In the project folder, double-click **Install Factorio.command**.
   - If macOS says it can't verify the developer, open **System Settings →
     Privacy & Security**, scroll down, and click **Open Anyway** next to the
     message, then double-click the file again.
   - Or open **Terminal**, type `bash ` (with a space), drag the file into the
     Terminal window, and press Return.
2. A Terminal window opens and walks you through the rest. It may:
   - offer to install **Homebrew**, which then installs Python and CMake. Type
     `y` and enter your Mac password when asked (nothing shows as you type);
   - ask you to drag **factorio.app** into the window if the game isn't in
     Steam's usual folder;
   - ask you to choose a device or team if you have more than one.
3. The first build takes 10–30 minutes. A timer shows it's still working.
4. When it finishes, Factorio is installed and starts on the device.

The installer remembers your choices, so later runs need no answers.

## 7. First start

- **"Untrusted Developer" on the device:** open **Settings → General → VPN &
  Device Management**, tap your Apple Account under **Developer App**, and tap
  **Trust**. Then open Factorio from the home screen.
- The first start takes about 30 seconds.
- Tap **Confirm** on the **Steam error** message. Steam features aren't
  available on iOS; the game itself works.
- Close the changelog if it appears, then start a tutorial or a new game.

You can unplug the cable now. The game runs entirely on the device.

**How to play with touch:** see [Controls](CONTROLS.md). In short: the stick on
the left moves, the big **Use** button in the bottom-right corner clicks, and
the pill at the top switches between touch modes. Rotate to portrait to put the
controls below the game.

## Updating, renewing, and keeping your saves

Double-click **Install Factorio.command** again to:

- **renew** the app after 7 days on a free account (or a year on a paid one);
- **update** after downloading a newer version of this project.

The installer reuses the same app ID, so your saves and settings are kept.
**Don't delete the app** to fix a problem: deleting it deletes your saves.

To copy your saves to the Mac first, run this in Terminal from the project folder:

```sh
.venv/bin/python - <<'EOF'
import json, subprocess
s = json.load(open('.local-config.json'))
subprocess.run(['xcrun', 'devicectl', 'device', 'copy', 'from', '--device', s['device_id'],
                '--domain-type', 'appDataContainer', '--domain-identifier', s['bundle_id'],
                '--source', 'Documents/Factorio/user/saves', '--destination', 'save-backup'], check=True)
EOF
```

If Steam updates Factorio to a version the port doesn't support yet, the
installer stops with **Unsupported Factorio executable**. The app already on
your device keeps working until its signing expires.

## If something goes wrong

| What you see | What to do |
|---|---|
| **No iPhone or iPad is ready** | Unlock it, check the cable, tap **Trust**, and wait for Xcode to finish preparing it. iPhone Duo: unfold it |
| **Developer Mode is off** | Step 5.5. If the switch is missing, connect the device and open Xcode's **Devices and Simulators** window first |
| **Xcode has no Apple Account yet** | Step 2, then press Return in the installer window |
| **Unsupported Factorio executable** | Your game isn't the exact supported version; see step 3 |
| **That bundle ID is taken** | Open `.local-config.json` in the project folder with TextEdit, delete the line with `bundle_id`, and run the installer again |
| **maximum number of apps** (free account) | Delete another app you built yourself from the device, then run again |
| **Untrusted Developer** | Step 7 |
| The app stops opening after a week | The free signing expired. Run the installer again |
| The game doesn't fill the iPhone Duo's inner display | Build with Xcode 27.2 or later |
| The build failed with something else | The installer prints the first errors. The full log is `reports/install-build.log` in the project folder |

More: [Troubleshooting for developers](DEVELOPMENT.md#troubleshooting).
