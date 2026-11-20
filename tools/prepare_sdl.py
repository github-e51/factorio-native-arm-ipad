#!/usr/bin/env python3
"""Fetch pinned upstream SDL and compile a separate ARM64 iOS platform library."""
import argparse
import hashlib
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from config import ROOT, CMAKE, DEFAULT_APP, SDL_MAJOR_BY_SHA256, validate_source

RELEASES = {
    2: ('2.30.9', '682a055004081e37d81a7d4ce546c3ee3ef2e0e6a675ed2651e430ccd14eb407'),
    3: ('3.4.14', '9d57b178fb297e121ef2605275937b7afaa7cd24d99ce1f95953e69e7a2535d6'),
}

def adapt_sdl3_scene_window(source):
    """Use the active UIWindowScene's bounds during the first SDL window setup.

    SDL 3.4.14 computes the frame before storing its UIWindow, so the initial
    calculation uses UIScreen.mainScreen instead of the active Duo display.
    """
    path = source/'src/video/uikit/SDL_uikitwindow.m'
    original = '''    SDL_uikitview *view;

#ifdef SDL_PLATFORM_VISIONOS
    CGRect frame = UIKit_ComputeViewFrame(window);
#else
    CGRect frame = UIKit_ComputeViewFrame(window, displaydata.uiscreen);
#endif

    int width = (int)frame.size.width;
    int height = (int)frame.size.height;

    SDL_UIKitWindowData *data = [[SDL_UIKitWindowData alloc] init];
    if (!data) {
        return SDL_OutOfMemory();
    }

    window->internal = (SDL_WindowData *)CFBridgingRetain(data);

    data.uiwindow = uiwindow;
'''
    adapted = '''    SDL_uikitview *view;
    SDL_UIKitWindowData *data = [[SDL_UIKitWindowData alloc] init];
    if (!data) {
        return SDL_OutOfMemory();
    }

    window->internal = (SDL_WindowData *)CFBridgingRetain(data);
    data.uiwindow = uiwindow;

#ifdef SDL_PLATFORM_VISIONOS
    CGRect frame = UIKit_ComputeViewFrame(window);
#else
    CGRect frame = UIKit_ComputeViewFrame(window, displaydata.uiscreen);
#endif

    int width = (int)frame.size.width;
    int height = (int)frame.size.height;
'''
    text = path.read_text()
    if adapted not in text:
        if text.count(original) != 1:
            raise ValueError('Pinned SDL 3.4.14 UIKit window setup changed')
        text = text.replace(original, adapted, 1)

    # UIScreen.mainScreen remains the outer panel on Duo even when the active
    # UIWindowScene is on the inner panel. SDL's external-display branch clears
    # keyboard/mouse focus, which also prevents our touch overlay from attaching.
    helper = '''static BOOL UIKit_IsActiveSceneScreen(UIScreen *screen)
{
    UIWindowScene *scene = UIKit_GetActiveWindowScene();
    return screen == (scene ? scene.screen : [UIScreen mainScreen]);
}

'''
    anchor = 'static bool SetupWindowData(SDL_VideoDevice *_this, SDL_Window *window, UIWindow *uiwindow, bool created)'
    if helper not in text:
        if text.count(anchor) != 1:
            raise ValueError('Pinned SDL 3.4.14 UIKit setup anchor changed')
        text = text.replace(anchor, helper + anchor, 1)
    # SDL selects its main display by UIScreen.mainScreen, which can be the
    # outer panel even when UIKit put the scene on the inner panel. Keep that
    # SDL selection (and its explicit external-screen assignment) unchanged;
    # use the actual UIWindow screen only for focus, resizing, and status UI.
    comparisons = [
        ('if (displaydata.uiscreen != [UIScreen mainScreen]) {',
         'if (!UIKit_IsActiveSceneScreen(uiwindow.screen)) {'),
        ('if (displaydata.uiscreen == [UIScreen mainScreen]) {',
         'if (UIKit_IsActiveSceneScreen(uiwindow.screen)) {'),
        ('if (displaydata.uiscreen == [UIScreen mainScreen])\n#endif\n        {',
         'if (UIKit_IsActiveSceneScreen(data.uiwindow.screen))\n#endif\n        {'),
        ('if (data.uiwindow.screen == [UIScreen mainScreen]) {',
         'if (UIKit_IsActiveSceneScreen(data.uiwindow.screen)) {'),
    ]
    for old, new in comparisons:
        if old in text:
            text = text.replace(old, new, 1)
        elif new not in text:
            raise ValueError('Pinned SDL 3.4.14 screen comparison changed: '+old)
    if path.read_text() != text:
        path.write_text(text)

    # UIApplication.statusBarOrientation is global and can be unknown or
    # describe Duo's outer panel while this UIWindowScene is landscape on the
    # inner panel. A later SDL border/fullscreen update otherwise swaps a
    # 951x669 Metal view into a clipped 669x951 view.
    video_path = source/'src/video/uikit/SDL_uikitvideo.m'
    old_orientation = '''    UIInterfaceOrientation orient = [UIApplication sharedApplication].statusBarOrientation;
    BOOL landscape = UIInterfaceOrientationIsLandscape(orient) ||
                    !(UIKit_GetSupportedOrientations(window) & (UIInterfaceOrientationMaskPortrait | UIInterfaceOrientationMaskPortraitUpsideDown));
'''
    new_orientation = '''    UIInterfaceOrientation orient = data.uiwindow.windowScene.interfaceOrientation;
    if (orient == UIInterfaceOrientationUnknown) {
        orient = [UIApplication sharedApplication].statusBarOrientation;
    }
    BOOL landscape = (orient == UIInterfaceOrientationUnknown ? frame.size.width > frame.size.height : UIInterfaceOrientationIsLandscape(orient)) ||
                    !(UIKit_GetSupportedOrientations(window) & (UIInterfaceOrientationMaskPortrait | UIInterfaceOrientationMaskPortraitUpsideDown));
'''
    video_text = video_path.read_text()
    if new_orientation not in video_text:
        if video_text.count(old_orientation) != 1:
            raise ValueError('Pinned SDL 3.4.14 UIKit orientation calculation changed')
        video_text = video_text.replace(old_orientation, new_orientation, 1)

    # Factorio positions its own HUD at the drawable edges and does not use
    # SDL's safe-area rectangle. Keep the UIKit window full size, but put its
    # Metal view inside the phone's safe area with a small corner guard.
    old_viewport = '''#endif

    return frame;
}
#endif // SDL_PLATFORM_VISIONOS
'''
    new_viewport = '''#endif

#ifdef SDL_PLATFORM_IOS
    if (data != nil && data.uiwindow != nil &&
        data.uiwindow.traitCollection.userInterfaceIdiom == UIUserInterfaceIdiomPhone) {
        UIEdgeInsets safe = data.uiwindow.safeAreaInsets;
        const CGFloat corner = 16.0f;
        safe.top = SDL_max(safe.top, corner);
        safe.left = SDL_max(safe.left, corner);
        // The portrait control deck reserves the lower part of the window.
        extern float FPIReservedBottom(void);
        safe.bottom = SDL_max(corner, FPIReservedBottom());
        safe.right = SDL_max(safe.right, corner);
        frame = UIEdgeInsetsInsetRect(frame, safe);
    }
#endif

    return frame;
}
#endif // SDL_PLATFORM_VISIONOS
'''
    if new_viewport not in video_text:
        bottom_line = '''        // The portrait control deck reserves the lower part of the window.
        extern float FPIReservedBottom(void);
        safe.bottom = SDL_max(corner, FPIReservedBottom());'''
        previous_bottoms = [
            '''        safe.bottom = corner;''',
            '''        // Keep the HUD above the home indicator while reclaiming a little of
        // the otherwise unused bottom safe area.
        safe.bottom = SDL_max(safe.bottom - 6.0f, corner);''',
            '''        safe.bottom = SDL_max(safe.bottom, corner);''',
        ]
        previous = next((new_viewport.replace(bottom_line, bottom)
                         for bottom in previous_bottoms
                         if new_viewport.replace(bottom_line, bottom) in video_text), None)
        if previous is not None:
            video_text = video_text.replace(previous, new_viewport, 1)
        elif video_text.count(old_viewport) == 1:
            video_text = video_text.replace(old_viewport, new_viewport, 1)
        else:
            raise ValueError('Pinned SDL 3.4.14 UIKit viewport calculation changed')
    if video_path.read_text() != video_text:
        video_path.write_text(video_text)

    controller_path = source/'src/video/uikit/SDL_uikitviewcontroller.m'
    old_layout = '''- (void)viewDidLayoutSubviews
{
    const CGSize size = self.view.bounds.size;
'''
    new_layout = '''- (void)viewDidLayoutSubviews
{
#ifdef SDL_PLATFORM_IOS
    SDL_UIKitWindowData *data = (__bridge SDL_UIKitWindowData *)window->internal;
    if (data != nil && data.uiwindow != nil &&
        data.uiwindow.traitCollection.userInterfaceIdiom == UIUserInterfaceIdiomPhone) {
        CGRect frame = UIKit_ComputeViewFrame(window, data.uiwindow.screen);
        if (!CGRectEqualToRect(self.view.frame, frame)) {
            self.view.autoresizingMask = UIViewAutoresizingNone;
            self.view.frame = frame;
            [self.view layoutIfNeeded];
        }
    }
#endif
    const CGSize size = self.view.bounds.size;
'''
    controller_text = controller_path.read_text()
    if new_layout not in controller_text:
        if controller_text.count(old_layout) != 1:
            raise ValueError('Pinned SDL 3.4.14 UIKit view layout changed')
        controller_path.write_text(controller_text.replace(old_layout, new_layout, 1))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sdk',choices=['iphoneos','iphonesimulator'],default='iphonesimulator')
    args=parser.parse_args()
    major = SDL_MAJOR_BY_SHA256[validate_source(DEFAULT_APP)]
    version, expected_sha256 = RELEASES[major]
    stem = f'SDL-release-{version}'
    url = f'https://github.com/libsdl-org/SDL/archive/refs/tags/release-{version}.tar.gz'
    (ROOT/'reports').mkdir(exist_ok=True)
    vendor=ROOT/'build/vendor'
    vendor.mkdir(parents=True,exist_ok=True)
    archive=vendor/(stem+'.tar.gz')
    if not archive.exists(): urllib.request.urlretrieve(url,archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('SDL archive checksum mismatch')
    source=vendor/stem
    if not source.exists():
        with tarfile.open(archive) as tar: tar.extractall(vendor,filter='data')
    if major == 3:
        adapt_sdl3_scene_window(source)
    # Add the input adapter to SDL's target so it can call private event/state
    # functions. SDL3 also carries the narrowly scoped Duo scene-size fix above.
    with tarfile.open(archive) as tar:
        upstream=tar.extractfile(stem+'/CMakeLists.txt').read().decode()
    target = 'SDL2' if major == 2 else 'SDL3-shared'
    cmake=upstream+'\n# Local iOS input adapter\n'+f'target_sources({target} PRIVATE "{ROOT}/probe/SDLInputBridge.c")\n'+f'target_include_directories({target} PRIVATE "{source}/src")\n'
    cmake_file=source/'CMakeLists.txt'
    if cmake_file.read_text()!=cmake: cmake_file.write_text(cmake)
    build=ROOT/'build'/(('sdl' if major == 2 else 'sdl3')+'-'+('simulator' if args.sdk=='iphonesimulator' else 'iphoneos'))
    log_stem = 'sdl' if major == 2 else 'sdl3'
    with (ROOT/f'reports/{log_stem}-configure-{args.sdk}.log').open('w') as log:
        subprocess.run([CMAKE,'-S',str(source),'-B',str(build),'-DCMAKE_SYSTEM_NAME=iOS',
            '-DCMAKE_OSX_SYSROOT='+args.sdk,'-DCMAKE_OSX_ARCHITECTURES=arm64',
            '-DCMAKE_OSX_DEPLOYMENT_TARGET=26.0','-DSDL_SHARED=ON','-DSDL_STATIC=OFF',
            '-DSDL_TEST=OFF','-DSDL_TESTS=OFF','-DSDL_INSTALL=OFF','-DCMAKE_BUILD_TYPE=Release'],
            check=True,stdout=log,stderr=subprocess.STDOUT)
    with (ROOT/f'reports/{log_stem}-build-{args.sdk}.log').open('w') as log:
        subprocess.run([CMAKE,'--build',str(build),'-j','8'],check=True,stdout=log,stderr=subprocess.STDOUT)
    print(build/('libSDL2-2.0.0.dylib' if major == 2 else 'libSDL3.0.dylib'))

if __name__=='__main__': main()
