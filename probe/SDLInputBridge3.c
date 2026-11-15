#include "SDL_internal.h"
#include "events/SDL_keyboard_c.h"
#include "events/SDL_mouse_c.h"

// SDL 3 uses timestamps, device IDs, boolean key state, and floating-point mouse
// coordinates. Send events through SDL itself so polled state stays consistent.
static SDL_Window *inputWindow(void) {
    SDL_Window *window = SDL_GetMouseFocus();
    return window ? window : SDL_GetKeyboardFocus();
}

SDL_DECLSPEC void FPIKeyboard(int scan, int down) {
    SDL_SendKeyboardKey(SDL_GetTicksNS(), SDL_GLOBAL_KEYBOARD_ID, 0,
                        (SDL_Scancode)scan, down != 0);
}

SDL_DECLSPEC void FPIText(const char *text) {
    SDL_Window *window = inputWindow();
    if (window && SDL_TextInputActive(window)) SDL_SendKeyboardText(text);
}

SDL_DECLSPEC void FPIMouseButton(int button, int down) {
    SDL_SendMouseButton(SDL_GetTicksNS(), inputWindow(), SDL_GLOBAL_MOUSE_ID,
                        (Uint8)button, down != 0);
}

SDL_DECLSPEC void FPIWheel(float y) {
    SDL_SendMouseWheel(SDL_GetTicksNS(), inputWindow(), SDL_GLOBAL_MOUSE_ID,
                       0, y, SDL_MOUSEWHEEL_NORMAL);
}

SDL_DECLSPEC void FPIPointer(float x, float y) {
    SDL_Window *window = inputWindow();
    int width, height;
    if (!window || !SDL_GetWindowSize(window, &width, &height)) return;
    SDL_SendMouseMotion(SDL_GetTicksNS(), window, SDL_GLOBAL_MOUSE_ID, false,
                        x * width, y * height);
}

SDL_DECLSPEC int FPIGetPointer(float *x, float *y) {
    SDL_Window *window = inputWindow();
    int width, height;
    float mouse_x, mouse_y;
    if (!window || !SDL_GetWindowSize(window, &width, &height) || width <= 0 || height <= 0) return 0;
    SDL_GetMouseState(&mouse_x, &mouse_y);
    *x = mouse_x / width;
    *y = mouse_y / height;
    return 1;
}
