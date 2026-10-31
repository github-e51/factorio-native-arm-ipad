# Architecture and limitations

## How the original executable starts on iOS

The tools read the ARM64 slice of the macOS executable identified by the pinned
SHA-256 hash. They create a new file under `build/`, change its Mach-O platform
to iOS, and replace library paths with local facade libraries that refer to iOS
libraries and the compatibility layer.

Before signing, `tools/entrypoint.py` inserts static ARM64 trampolines into
verified unused Mach-O space. Factorio 2.0.77 redirects 817 public SDL entry
points to SDL 2.30.9. Factorio 2.1.23 redirects 1,269 to SDL 3.4.14. Each SDL
release is built separately for iOS from a hash-checked source archive. The new
entry point runs through UIKit and reaches the preserved original `main`. There
is no JIT and no runtime modification of executable memory pages.

For iPhone Duo, the adapted game executable records the selected Xcode SDK in
its Mach-O build version. SDL 3.4.14's initial UIKit window setup is adjusted to
size from the active `UIWindowScene` and set input focus for that scene's screen.
This lets the inner display fill the game window even though `UIScreen.mainScreen`
can still refer to the outer display. Later UIKit frame updates also use that
window scene's orientation: the global status-bar orientation can be unknown on
Duo, which otherwise rotates the 951 × 669-point Metal view into a clipped
669 × 951-point view. The app's overlay lays out from its
window bounds and safe area, and recomputes them when the window changes size.
On phones, SDL uses the window's safe-area insets at the top and sides, with a
16-point minimum corner margin. The bottom margin is fixed at 16 points to
match the Duo's top margin, even though its reported bottom safe-area inset is
larger. The UIWindow stays full size and supplies the dark border. Factorio
places its own HUD against the drawable edges, so the margins keep those panels
clear of rounded corners. In portrait, the overlay reserves the lower part of
the window for its control deck through `FPISetReservedBottom`, and SDL's view
frame calculation adds that reserve to the bottom margin, so the game renders
above the deck and receives an ordinary resize.
Cursor and mining touches are converted through the actual Metal view frame.

The facade libraries preserve the original dyld library ordinals. Other missing
symbols receive diagnostic placeholders that abort with an explicit error.
Successful linking therefore does not mean that every game code path has been
implemented on iOS.

| File | Purpose |
|---|---|
| `tools/config.py`, `tools/setup.py` | Local paths, original executable validation, and setup |
| `tools/audit.py` | Check original imports against iOS SDK exports and generate a local report |
| `tools/macho.py` | Read ARM64 Mach-O; change the platform and load paths on a copy |
| `tools/entrypoint.py` | Static branches and documented platform patches |
| `tools/prepare_sdl.py` | Download SDL, verify its hash, and compile it for iOS |
| `tools/build_probe.py` | Build compatibility libraries, the executable, and the app bundle |
| `tools/xcode_build.sh` | Integrate with Xcode, apply its bundle ID, and sign libraries |
| `probe/UIKitEntry.m` | App lifecycle, local data paths, original game startup, and CLI probes |
| `probe/MetalCompat.m` | Supply the missing macOS depth-format query |
| `probe/BitmapCompat.m` | Required NSBitmapImageRep/NSColorSpace operations using ImageIO/RGBA8 |
| `probe/PlatformFallbacks.m` | Report OpenCL and Steam as unavailable |
| `probe/TouchControls.m` | Touch overlay, portrait deck, on-screen keyboard, cursor, and Bluetooth hardware handling |
| `probe/SDLInputBridge.c` | Send overlay and trackpad input through SDL's event path; hold the portrait reserve |
| `tools/install.py`, `Install Factorio.command` | One-step device selection, signing, build, install and launch |
| `tools/verify.py` | Check the original hash, patch provenance, platforms, and signatures |

## Additional adaptations

A small patch skips the macOS-specific display-ID suffix in Factorio 2.0.77's
display logging. Factorio 2.1.23 no longer needs that patch. The remaining game
engine and its Metal renderer are preserved. On the tested
M1 iPad, the compatibility layer implements the missing
`isDepth24Stencil8PixelFormatSupported` method by returning `NO`, causing the
original renderer to select its alternative depth format.

## Hardware input

SDL forwards GameController mouse (`GCMouse`) movement only in relative mode.
The overlay chains its own movement handler after SDL's and sends the deltas as
ordinary motion, and asks for pointer lock while a mouse is connected; iPad
grants it, iPhone refuses. On iPhone, a trackpad's pointer comes from
AssistiveTouch as hover and indirect-pointer touches. iOS 27.1 on iPhone Duo
delivers AssistiveTouch's pointer and left-click tap only to the outer display,
so on 27.1 the overlay draws its own arrow from hover and lets the trackpad's
right button click; iOS 27.2 fixes this and both workarounds switch off there.
Factorio starts without `--nogamepad`, so its own controller support is active.

Base-game assets are copied from the local installation into the app bundle.
Configuration and user data are stored under `Documents/Factorio` in the private
app container. Its changing absolute paths are adjusted at startup. Simulation
and rendering require no connection to the Mac.

## Verified behavior and remaining gaps

Baseline as of September 8, 2026: Factorio 2.0.77 / build 84539, 11-inch iPad Pro
M1, iPadOS 26.6.1, Xcode 26.3, and SDK 26.2. Observed behavior includes graphical
startup, the tutorial, the WASD stick, Tab, inventory, mining trees, on-screen
text entry, and saving and reloading a game. Audio was confirmed by the user.
Positioning the cursor alone did not click; pressing the separate Left click
button activated the targeted menu item. The mouse buttons are grouped together.

A shared test save with a 64 × 64 map and seed 12345 produced checksum
`2892897386` after 120 updates on the original Mac version, the simulator, and
the iPad. This is a small simulation probe, not a general compatibility
guarantee. The original test logs and device screenshots are not included;
`verify.py` can check logs generated by your own tests.

For Factorio 2.1.23 / build 87750 with Space Age, Quality, Elevated Rails, and
Recycler, a fresh map with the same dimensions and seed produced checksum
`4032494708` after 120 updates on the original Mac game, the iPhone Duo
iOS 27.1 simulator, and a physical iPhone Duo. The 2.1.23 executable uses SDL
3.4.14. This is a simulation check; it does not establish graphical gameplay.
Separately, the physical Duo reached the Space Age main menu and loaded an early
tutorial save. The original full-bleed build used a 2853 × 2007 Metal drawable
but let the HUD approach rounded corners. The current inset build uses a
2757 × 1911 drawable; its equal 16-point top and bottom margins were measured
on the physical Duo. The objective panel and bottom HUD were visible in the
previous 34-point-bottom build, and the current build's menu rendered correctly.
Extended gameplay remains untested.

On the physical iPhone Duo, a Bluetooth keyboard and a trackpad through
AssistiveTouch were used in play on iOS 27.1 and 27.2 RC2.

Complex factories, many shader and texture paths, color fidelity, the full range
of building actions involving multiple fingers, controllers, mice on iPad, and
long-term behavior remain unverified. Bitmap compatibility reduces
16-bit images to 8 bits. Steam features and Space Age are not established as complete. Multiplayer has not been tested. The app still displays
the original macOS executable's version label; that label does not establish
the build target.

## Simulator

For Factorio 2.0.77 diagnostics, the GPU-family check can be bypassed only in
the simulator (`--simulator-metal`). The tested simulator then fails on the unsupported
BC3_RGBA format. This exception is forbidden in device builds and rejected
there by verification. The simulator is useful for selected CLI probes here;
it is not a verified environment for graphical gameplay.
