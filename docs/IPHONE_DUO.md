# iPhone Duo

To install, follow the [install guide](INSTALL.md). This page covers what is
specific to the Duo.

## Requirements

| | |
|---|---|
| Xcode | **27.2 or later** |
| iOS on the Duo | **27.2 recommended**. 27.1 works, but its AssistiveTouch bug needs workarounds for trackpad play ([Controls](CONTROLS.md#trackpad-or-mouse-on-iphone)) |
| Factorio | **2.1.23, build 87750**, macOS Steam, executable SHA-256 `42218e9676f36687282800e5b6336b049c0f0e45f0f71eb20f90c49ccdec4359` |

A newer Steam version of Factorio isn't automatically compatible: setup rejects
any other executable, because the binary patches depend on its exact layout.

## What has been tested

On a physical iPhone Duo, Factorio 2.1.23 with Space Age loads its main menu and
saved games and plays with the touch controls, a Bluetooth keyboard, and a
trackpad through AssistiveTouch (iOS 27.1 and 27.2 RC2). A 120-update Space Age
simulation produced the same checksum (`4032494708`) as the original Mac game.
Fold/unfold while running, long sessions, large factories, multiplayer and
controller play are untested.

The phone build uses low-quality texture compression, virtual-atlas compression
and low video-memory settings to keep the initial texture allocation down.

## Inner display

The game runs on the inner display, unfolded. The port selects the active
window scene instead of assuming `UIScreen.mainScreen` is the game display;
otherwise later orientation updates can squeeze the game into a 669-point-wide
view with the right side black and the bottom cut off.

The game window fills the inner display, while the game view sits inside dark
16-point margins so Factorio's edge-aligned HUD stays clear of the rounded
corners. In landscape the window is **951 × 669 points** (2853 × 2007 pixels)
and the game view **919 × 637 points** (2757 × 1911 pixels). The side margins
follow the larger of the system safe area and 16 points.

In portrait the game shrinks to the upper part of the screen and the controls sit
on a panel below it; see [Controls](CONTROLS.md#portrait).

## Checking the display (developers)

If the right edge is black or the HUD is clipped, capture the **inner** display.
XCTest's default screenshot may capture the outer one. Get the device ID from
`xcrun devicectl list devices` and the inner display's unique ID from
`device info displays`:

```sh
export FACTORIO_DEVICE_ID="YOUR_DEVICE_IDENTIFIER"
xcrun devicectl device info displays --device "$FACTORIO_DEVICE_ID"
mkdir -p reports
xcrun devicectl device capture screenshot \
  --device "$FACTORIO_DEVICE_ID" \
  --display-unique-id "YOUR_INNER_DISPLAY_UNIQUE_ID" \
  --destination reports/duo-inner.png
swift tests/check_duo_viewport.swift reports/duo-inner.png
swift tests/check_duo_safe_viewport.swift reports/duo-inner.png
```

The checks assume the tested landscape layout; a different rotation or a loading
screen can invalidate them, so look at the image too.

## Simulator

The iPhone Duo simulator profile needs the matching Xcode simulator runtime. It
runs the touch-control harness and the small simulation probes, but it can't
start the game's graphics: its simulated GPU lacks the needed Metal family and
BC texture formats. Use a physical Duo for anything graphical. See
[Development](DEVELOPMENT.md#simulator-checks).
