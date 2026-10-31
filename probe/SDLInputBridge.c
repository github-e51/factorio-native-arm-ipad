#include "SDL_internal.h"
#include "events/SDL_keyboard_c.h"
#include "events/SDL_mouse_c.h"

// Use SDL's input path so both queued events and polled state stay consistent.
#if SDL_MAJOR_VERSION >= 3
#define FPI_EXPORT SDL_DECLSPEC
#else
#define FPI_EXPORT DECLSPEC
#endif
FPI_EXPORT void FPIKeyboard(int scan, int down) {
#if SDL_MAJOR_VERSION >= 3
    SDL_SendKeyboardKey(0, SDL_GLOBAL_KEYBOARD_ID, 0, (SDL_Scancode)scan, down != 0);
#else
    SDL_SendKeyboardKey(down ? SDL_PRESSED : SDL_RELEASED, (SDL_Scancode)scan);
#endif
}
FPI_EXPORT void FPIText(const char *text) {
#if SDL_MAJOR_VERSION >= 3
    if (SDL_TextInputActive(SDL_GetKeyboardFocus())) SDL_SendKeyboardText(text);
#else
    if (SDL_IsTextInputActive()) SDL_SendKeyboardText(text);
#endif
}
static SDL_Window *inputWindow(void) {
    SDL_Window *window=SDL_GetMouseFocus();
    return window ? window : SDL_GetKeyboardFocus();
}
FPI_EXPORT void FPIMouseButton(int button, int down) {
#if SDL_MAJOR_VERSION >= 3
    SDL_SendMouseButton(0, inputWindow(), SDL_GLOBAL_MOUSE_ID, (Uint8)button, down != 0);
#else
    SDL_SendMouseButton(inputWindow(),0,down ? SDL_PRESSED : SDL_RELEASED,(Uint8)button);
#endif
}
FPI_EXPORT void FPIWheel(float y) {
#if SDL_MAJOR_VERSION >= 3
    SDL_SendMouseWheel(0, inputWindow(), SDL_GLOBAL_MOUSE_ID, 0, y, SDL_MOUSEWHEEL_NORMAL);
#else
    SDL_SendMouseWheel(inputWindow(),0,0,y,SDL_MOUSEWHEEL_NORMAL);
#endif
}
FPI_EXPORT void FPIPointer(float x,float y) {
    SDL_Window *window=inputWindow();
    if (!window) return;
    int width,height; SDL_GetWindowSize(window,&width,&height);
#if SDL_MAJOR_VERSION >= 3
    SDL_SendMouseMotion(0, window, SDL_GLOBAL_MOUSE_ID, false, x*width, y*height);
#else
    SDL_SendMouseMotion(window,0,0,(int)(x*width),(int)(y*height));
#endif
}
FPI_EXPORT int FPIGetPointer(float *x,float *y) {
    SDL_Window *window=inputWindow();
    if (!window) return 0;
    int width,height;
    SDL_GetWindowSize(window,&width,&height);
    if (width<=0 || height<=0) return 0;
#if SDL_MAJOR_VERSION >= 3
    float mouseX,mouseY;
    SDL_GetMouseState(&mouseX,&mouseY);
#else
    int mouseX,mouseY;
    SDL_GetMouseState(&mouseX,&mouseY);
#endif
    *x=(float)mouseX/width; *y=(float)mouseY/height;
    return 1;
}
// SDL forwards GCMouse movement only while the pointer is locked in relative
// mode, and iPhone has no system pointer, so a Bluetooth trackpad would not move
// the cursor in normal play. Feed those deltas in as ordinary motion instead.
FPI_EXPORT void FPIMouseDelta(float dx,float dy) {
    SDL_Window *window=inputWindow();
    if (!window || SDL_GetMouse()->relative_mode) return;
#if SDL_MAJOR_VERSION >= 3
    SDL_SendMouseMotion(0, window, SDL_GLOBAL_MOUSE_ID, true, dx, dy);
#else
    SDL_SendMouseMotion(window,0,1,(int)dx,(int)dy);
#endif
}
// Points kept free below the game view for the portrait control deck.
static float reservedBottom;
FPI_EXPORT void FPISetReservedBottom(float bottom) { reservedBottom=bottom; }
FPI_EXPORT float FPIReservedBottom(void) { return reservedBottom; }
