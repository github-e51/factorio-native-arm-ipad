# Controls

The touch controls float over the game in landscape and move onto a panel below
it in portrait. They're translucent, fade back after five seconds without a
touch, and return on the next touch. Buttons give a light haptic tap.

## Layout

| Control | Function |
|---|---|
| **Pill at the top** | Touch mode (**Tap** / **Mine** / **Cursor**), on-screen keyboard, and the eye button to hide or show the controls |
| **Stick**, bottom left | Walk (W A S D), in eight equal directions, so diagonals are as easy as straight lines |
| **Rail above the stick** | Menu (Esc), Inventory (E), Research (T), Map (M) |
| **Use**, the large button in the bottom-right corner | Left click: select, build, open |
| Inner arc: **Mine**, **Rotate**, **Pipette** | Right click (mine, remove) / R / Q (pick an entity, or clear the cursor) |
| Outer arc: **Pick up**, **Shoot**, **Gun**, **Middle** | F / Space / Tab (switch gun; also answers the matching tutorial prompt) / middle click |
| **Zoom** pair above the arc | Zoom out / in |
| **Shift**, **Ctrl**, **Alt** | Tap to hold the modifier down; tap again to release |
| **Keyboard** | Full keyboard with letters, numbers, Enter, function and arrow keys |

The exact effect of each click depends on the game's context and key bindings.

## Touch modes

Choose a mode in the top pill. The active one is highlighted, and a short hint
appears below it.

- **Tap:** touching the screen clicks where you touch. Use it for menus and
  ordinary play.
- **Mine:** holding a finger on a tree or ore holds the right mouse button, so
  you mine it. Switch back to Tap for menus.
- **Cursor:** touching moves a white arrow without clicking; then press **Use**
  or **Mine** to click at the arrow's tip. To drag, hold **Use** or **Mine** and
  slide a second finger across the game.

## Portrait

Rotate the device to portrait to put the controls on a solid panel below the
game. The game shrinks to the upper part of the screen, so no control covers
it, and the on-screen keyboard opens in the panel with the game still visible
above. Hiding the controls with the eye button gives the game the whole screen.

## Bluetooth keyboard, mouse, trackpad and controllers

When a keyboard, mouse or trackpad, or game controller connects, the touch
controls hide and a short notice says so. Tap the eye button to bring them back.
They return by themselves when all hardware disconnects, unless you showed or
hid them yourself in the meantime.

- **Keyboard:** works as on a computer, with Factorio's normal key bindings.
- **Controller:** Factorio's own controller support is switched on.
  Controller play is experimental and hasn't been tested on a device yet.
- **Mouse or trackpad on iPad:** works directly. The port draws a white arrow
  for the pointer.
- **Mouse or trackpad on iPhone:** see below.

### Trackpad or mouse on iPhone

iPhone doesn't pass mouse movement to apps by itself. Turn on
**Settings → Accessibility → Touch → AssistiveTouch**, and pair the trackpad
under **AssistiveTouch → Pointer Devices**. iOS then shows its own round
pointer, and clicks work. Optional tweaks in the same place:

- turn off **Always Show Menu** to hide the floating AssistiveTouch button;
- change **Pointer Style** to make the pointer easier to see.

**iOS 27.1 on iPhone Duo has a bug:** AssistiveTouch shows its pointer and
delivers its left-click taps only on the *outer* display, even while the game is
on the inner one. The port works around it on 27.1:

- it draws its own white arrow on the inner display while you move the trackpad;
- the trackpad's **right button acts as left click**, because the left click
  never arrives. To mine or remove, bind **Mine** to a keyboard key in
  Factorio's **Settings → Controls**, or use the overlay's **Mine** mode.

iOS 27.2 fixes the bug, and on 27.2 or later both workarounds switch off: you get
iOS's pointer only, with normal left and right clicks. Updating to iOS 27.2 is
recommended for trackpad play.

## Hiding the controls

The eye button at the top hides everything except itself; tap it again to bring
the controls back. Any held button or key is released when the controls are
hidden, the window resizes, or the device rotates, so nothing stays stuck down.
