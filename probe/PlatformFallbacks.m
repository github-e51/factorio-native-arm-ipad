// Narrow, explicit absence responses for APIs that are optional for headless use.
// These are not implementations of macOS graphics or input.
#include <stdint.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>

bool SteamAPI_RestartAppIfNecessary(uint32_t appID) {
    fprintf(stderr, "FACTORIO_PROBE: Steam client unavailable on iOS\n");
    return false;
}

bool SteamAPI_Init(void) {
    fprintf(stderr, "FACTORIO_PROBE: Steam initialization unavailable\n");
    return false;
}

// Steamworks SDK 1.64: SteamAPI_InitEx calls this exported function. Its
// NoSteamClient result is 2, and SteamErrMsg is a 1024-byte output buffer.
int SteamInternal_SteamAPI_Init(const char *interface_versions, char (*out_error)[1024]) {
    (void)interface_versions;
    const char message[] = "Steam client is unavailable on iOS";
    if (out_error) memcpy(*out_error, message, sizeof(message));
    fprintf(stderr, "FACTORIO_PROBE: %s\n", message);
    return 2;
}

// OpenCL extension cl_khr_icd: no OpenCL platforms are available on iPadOS.
int32_t clGetPlatformIDs(uint32_t capacity, void **platforms, uint32_t *count) {
    if (count) *count = 0;
    fprintf(stderr, "FACTORIO_PROBE: OpenCL unavailable (CL_PLATFORM_NOT_FOUND_KHR)\n");
    return -1001;
}
