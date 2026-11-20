// Exercise the real UIKit controls without depending on Factorio's renderer.
#import <UIKit/UIKit.h>
#include "SDL.h"
#undef main

#if FPI_SDL_MAJOR == 3
static BOOL keys[SDL_SCANCODE_COUNT], mouseButtons[8];
#else
static BOOL keys[SDL_NUM_SCANCODES], mouseButtons[8];
#endif
static float pointerX=0.75, pointerY=0.25, reservedBottom;
void FPIKeyboard(int scan,int down) { keys[scan]=down; }
void FPIMouseButton(int button,int down) { mouseButtons[button]=down; }
void FPIWheel(float y) {}
void FPIText(const char *text) {}
void FPIPointer(float x,float y) { pointerX=x; pointerY=y; }
int FPIGetPointer(float *x,float *y) { *x=pointerX; *y=pointerY; return 1; }
void FPIMouseDelta(float dx,float dy) {}
void FPISetReservedBottom(float bottom) { reservedBottom=bottom; }
#if FPI_SDL_MAJOR == 3
SDL_Keymod SDL_GetModState(void) { return SDL_KMOD_NONE; }
#else
SDL_Keymod SDL_GetModState(void) { return KMOD_NONE; }
#endif
SDL_Scancode SDL_GetScancodeFromName(const char *name) { return SDL_SCANCODE_UNKNOWN; }
SDL_Window *SDL_GetKeyboardFocus(void) { return NULL; }
#include "../probe/TouchControls.m"

@interface LayoutOverlay : FPTouchOverlay
@property(nonatomic) UIEdgeInsets testInsets;
@end
@implementation LayoutOverlay
- (UIEdgeInsets)safeAreaInsets { return self.testInsets; }
@end

static NSMutableArray<NSString *> *failures;
static void check(BOOL value, NSString *message) {
    if (!value) [failures addObject:message];
}
static void checkInside(UIView *view, CGRect area, NSString *label) {
    CGRect frame=view.frame;
    check(frame.size.width>0 && frame.size.height>0 && CGRectContainsRect(CGRectInset(area,-0.5,-0.5),frame),
          [NSString stringWithFormat:@"%@ outside safe area: %@",label,NSStringFromCGRect(frame)]);
}
static FPInputButton *findButton(FPTouchOverlay *overlay, int scan, int mouseButton) {
    for (FPInputButton *b in overlay.buttons) if (b.scan==scan && b.mouseButton==mouseButton) return b;
    return nil;
}
static void checkLayout(LayoutOverlay *overlay, NSString *name) {
    CGRect area=UIEdgeInsetsInsetRect(overlay.bounds,overlay.testInsets);
    NSMutableArray<UIView *> *controls=[NSMutableArray arrayWithArray:overlay.buttons];
    [controls addObjectsFromArray:overlay.modeButtons];
    [controls addObjectsFromArray:@[overlay.toggle,overlay.keyboardToggle,overlay.joystick]];
    for (NSUInteger i=0;i<controls.count;i++) {
        UIView *a=controls[i];
        checkInside(a,area,[NSString stringWithFormat:@"%@ control %lu",name,(unsigned long)i]);
        for (NSUInteger j=i+1;j<controls.count;j++) {
            check(!CGRectIntersectsRect(a.frame,controls[j].frame),
                  [NSString stringWithFormat:@"%@ controls %lu and %lu overlap",name,(unsigned long)i,(unsigned long)j]);
        }
    }
    check(CGRectEqualToRect(overlay.pointerSurface.frame,overlay.bounds),[name stringByAppendingString:@" pointer surface size"]);
    overlay.pointerSurface.mode=2;
    overlay.pointerSurface.hidden=NO;
    [overlay.pointerSurface refreshCursor];
    check(fabs(overlay.pointerSurface.cursorPoint.x-overlay.bounds.size.width*pointerX)<0.5 &&
          fabs(overlay.pointerSurface.cursorPoint.y-overlay.bounds.size.height*pointerY)<0.5,
          [name stringByAppendingString:@" cursor position after resize"]);
    checkInside(overlay.keyboard,area,[name stringByAppendingString:@" keyboard"]);
    for (NSArray *row in overlay.keyRows) for (UIView *key in row)
        checkInside(key,overlay.keyboard.bounds,[name stringByAppendingString:@" key"]);
}

@interface FixedTouch : NSObject
@property(nonatomic) CGPoint point;
@end
@implementation FixedTouch
- (CGPoint)locationInView:(UIView *)view { return self.point; }
@end

@interface LayoutApp : UIResponder <UIApplicationDelegate, UIWindowSceneDelegate>
@property(nonatomic,strong) UIWindow *window;
@end
@implementation LayoutApp
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)options {
    return YES;
}
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session options:(UISceneConnectionOptions *)options {
    self.window=[[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
    self.window.rootViewController=[UIViewController new];
    self.window.rootViewController.view.backgroundColor=[UIColor colorWithWhite:0.2 alpha:1];
    [self.window makeKeyAndVisible];
    dispatch_async(dispatch_get_main_queue(),^{ [self runChecks]; });
}
- (void)runChecks {
    failures=[NSMutableArray new];
    NSString *output=[NSHomeDirectory() stringByAppendingPathComponent:@"Documents"];
    NSMutableArray *cases=[@[
        @[@"ipad-landscape",@1194,@834,@0,@0,@20,@0],
        @[@"phone-landscape",@852,@393,@0,@59,@21,@59],
        @[@"duo-inner-landscape",@951,@669,@0,@0,@21,@59],
        @[@"duo-inner-portrait",@669,@951,@59,@0,@21,@0],
        @[@"phone-portrait",@393,@852,@59,@0,@34,@0],
        @[@"narrow-window",@320,@568,@20,@0,@20,@0],
        @[@"wide-window",@890,@626,@24,@0,@24,@0],
        @[@"short-landscape",@667,@375,@0,@0,@21,@0]] mutableCopy];
    UIEdgeInsets actualInsets=self.window.safeAreaInsets;
    [cases addObject:@[@"simulator-window",@(self.window.bounds.size.width),@(self.window.bounds.size.height),
                      @(actualInsets.top),@(actualInsets.left),@(actualInsets.bottom),@(actualInsets.right)]];
    LayoutOverlay *overlay=[[LayoutOverlay alloc] initWithFrame:CGRectMake(0,0,1194,834)];
    for (NSArray *item in cases) {
        NSString *name=item[0];
        overlay.frame=CGRectMake(0,0,[item[1] doubleValue],[item[2] doubleValue]);
        overlay.testInsets=UIEdgeInsetsMake([item[3] doubleValue],[item[4] doubleValue],[item[5] doubleValue],[item[6] doubleValue]);
        [overlay setNeedsLayout]; [overlay layoutIfNeeded];
        checkLayout(overlay,name);
        BOOL portrait=overlay.bounds.size.height>overlay.bounds.size.width;
        check(overlay.split==portrait && overlay.deck.hidden==!portrait,[name stringByAppendingString:@" split deck only in portrait"]);
        check(portrait ? reservedBottom>0 && overlay.bounds.size.height-reservedBottom<=CGRectGetMinY(overlay.deck.frame)-4
                       : reservedBottom==0,[name stringByAppendingString:@" game view reserve"]);
        if (portrait) for (UIView *control in overlay.buttons)
            check(CGRectGetMinY(control.frame)>=CGRectGetMinY(overlay.deck.frame),[name stringByAppendingString:@" control above deck"]);
        UIGraphicsImageRenderer *renderer=[[UIGraphicsImageRenderer alloc] initWithSize:overlay.bounds.size];
        NSData *png=[renderer PNGDataWithActions:^(UIGraphicsImageRendererContext *context) {
            [[UIColor colorWithWhite:0.2 alpha:1] setFill]; UIRectFill(overlay.bounds);
            [overlay.layer renderInContext:context.CGContext];
        }];
        [png writeToFile:[output stringByAppendingPathComponent:[name stringByAppendingString:@".png"]] atomically:YES];
    }
    [findButton(overlay,SDL_SCANCODE_E,0) sendDown:YES];
    [overlay.joystick updatePoint:CGPointMake(overlay.joystick.bounds.size.width,overlay.joystick.bounds.size.height/2)];
    overlay.pointerSurface.mining=YES; FPIMouseButton(SDL_BUTTON_RIGHT,YES);
    check(keys[SDL_SCANCODE_E] && keys[SDL_SCANCODE_D] && mouseButtons[SDL_BUTTON_RIGHT],@"input held before resize");
    overlay.frame=CGRectMake(0,0,890,626);
    [overlay setNeedsLayout]; [overlay layoutIfNeeded];
    check(!keys[SDL_SCANCODE_E] && !keys[SDL_SCANCODE_D] && !mouseButtons[SDL_BUTTON_RIGHT],@"resize releases held input");
    [overlay toggleKeyboard];
    check(!overlay.keyboard.hidden && overlay.joystick.hidden,@"keyboard hides movement controls");
    for (UIView *button in overlay.buttons) check(button.hidden,@"keyboard hides action controls");
    [overlay toggleKeyboard];
    check(overlay.keyboard.hidden && !overlay.joystick.hidden,@"closing keyboard restores movement controls");
    overlay.frame=CGRectMake(0,0,669,951); overlay.testInsets=UIEdgeInsetsMake(59,0,21,0);
    [overlay setNeedsLayout]; [overlay layoutIfNeeded];
    [overlay toggleControls]; [overlay layoutIfNeeded];
    check(!overlay.split && reservedBottom==0,@"hiding controls gives portrait game the full screen");
    [overlay toggleControls]; [overlay layoutIfNeeded];
    check(overlay.split && reservedBottom>0,@"showing controls restores the portrait deck");
    overlay.pointerSurface.mode=0; overlay.pointerSurface.hardwareCursor=YES; [overlay applyVisibility];
    check(!overlay.pointerSurface.hidden && !overlay.pointerSurface.userInteractionEnabled,@"hardware cursor draws without capturing touches");
    overlay.pointerSurface.hardwareCursor=NO; [overlay applyVisibility];
    check(overlay.pointerSurface.hidden,@"tap mode hides cursor without a hardware mouse");
    overlay.frame=CGRectMake(0,0,890,626); overlay.testInsets=UIEdgeInsetsMake(24,0,24,0);
    [overlay setNeedsLayout]; [overlay layoutIfNeeded];
    [overlay toggleControls];
    check(!overlay.toggle.hidden && overlay.joystick.hidden && overlay.keyboardToggle.hidden,@"hiding leaves only the show button");
    for (UIView *button in overlay.buttons) check(button.hidden,@"hiding hides action controls");
    [overlay toggleControls];
    check(!overlay.joystick.hidden && !overlay.modeButtons[2].hidden,@"showing restores controls");
    [overlay selectMode:overlay.modeButtons[2]];
    check(overlay.pointerSurface.mode==2 && !overlay.pointerSurface.hidden,@"cursor mode button selects cursor mode");
    [overlay selectMode:overlay.modeButtons[0]];
    check(overlay.pointerSurface.mode==0 && overlay.pointerSurface.hidden,@"tap mode button restores direct touch");
    [overlay.joystick updatePoint:CGPointMake(overlay.joystick.bounds.size.width,0)];
    check(keys[SDL_SCANCODE_D] && keys[SDL_SCANCODE_W] && !keys[SDL_SCANCODE_A] && !keys[SDL_SCANCODE_S],@"stick diagonal holds two keys");
    [overlay.joystick reset];
    check(!keys[SDL_SCANCODE_D] && !keys[SDL_SCANCODE_W],@"stick release clears keys");
    FPInputButton *leftClick=findButton(overlay,0,SDL_BUTTON_LEFT);
    [leftClick sendActionsForControlEvents:UIControlEventTouchDown];
    check(mouseButtons[SDL_BUTTON_LEFT],@"left click begins on touch down");
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
    check(mouseButtons[SDL_BUTTON_LEFT],@"left click remains held before touch up");
    [leftClick sendActionsForControlEvents:UIControlEventTouchUpInside];
    check(!mouseButtons[SDL_BUTTON_LEFT],@"left click releases on touch up");
    NSDictionary *result=@{@"layout_cases":@(cases.count),@"failures":failures,
                           @"runtime":UIDevice.currentDevice.systemVersion,
                           @"window_bounds":NSStringFromCGRect(self.window.bounds),
                           @"safe_area":NSStringFromUIEdgeInsets(actualInsets)};
    NSData *json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:NULL];
    [json writeToFile:[output stringByAppendingPathComponent:@"result.json"] atomically:YES];
    fprintf(stderr,"TOUCH_LAYOUT_TESTS: %s\n",[[NSString alloc] initWithData:json encoding:NSUTF8StringEncoding].UTF8String);
    overlay.frame=self.window.bounds; overlay.testInsets=self.window.safeAreaInsets;
    [self.window addSubview:overlay];

    // Cursor mode must target the inset Metal viewport, not the entire overlay.
    CGRect gameFrame=CGRectInset(self.window.bounds,16,16);
    self.window.rootViewController.view.frame=gameFrame;
    overlay.pointerSurface.frame=overlay.bounds;
    overlay.pointerSurface.mode=2;
    overlay.pointerSurface.hidden=NO;
    pointerX=0.75; pointerY=0.25;
    [overlay.pointerSurface refreshCursor];
    CGPoint expected=CGPointMake(CGRectGetMinX(gameFrame)+0.75*gameFrame.size.width,
                                 CGRectGetMinY(gameFrame)+0.25*gameFrame.size.height);
    check(fabs(overlay.pointerSurface.cursorPoint.x-expected.x)<0.5 &&
          fabs(overlay.pointerSurface.cursorPoint.y-expected.y)<0.5,
          @"cursor marker follows inset game viewport");
    FixedTouch *touch=[FixedTouch new]; touch.point=expected;
    [overlay.pointerSurface move:(UITouch *)touch];
    check(fabs(pointerX-0.75)<0.005 && fabs(pointerY-0.25)<0.005,
          @"cursor touch maps into inset game viewport");
    if (failures.count) {
        NSMutableDictionary *updated=[result mutableCopy]; updated[@"failures"]=failures;
        json=[NSJSONSerialization dataWithJSONObject:updated options:NSJSONWritingPrettyPrinted error:NULL];
        [json writeToFile:[output stringByAppendingPathComponent:@"result.json"] atomically:YES];
        fprintf(stderr,"TOUCH_VIEWPORT_TESTS: %s\n",[[NSString alloc] initWithData:json encoding:NSUTF8StringEncoding].UTF8String);
    }
}
@end

int main(int argc,char **argv) {
    @autoreleasepool { return UIApplicationMain(argc,argv,nil,NSStringFromClass(LayoutApp.class)); }
}
