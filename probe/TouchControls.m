#import <UIKit/UIKit.h>
#if FACTORIO_SDL_MAJOR == 3
#include <SDL3/SDL.h>
#else
#include "SDL.h"
#define SDL_KMOD_CTRL KMOD_CTRL
#define SDL_KMOD_ALT KMOD_ALT
#define SDL_KMOD_GUI KMOD_GUI
#define SDL_KMOD_SHIFT KMOD_SHIFT
#define SDL_KMOD_CAPS KMOD_CAPS
#endif

extern void FPIKeyboard(int scan,int down);
extern void FPIMouseButton(int button,int down);
extern void FPIWheel(float y);
extern void FPIText(const char *text);
extern void FPIPointer(float x,float y);
extern int FPIGetPointer(float *x,float *y);

@interface FPInputButton : UIButton
@property(nonatomic) int scan;
@property(nonatomic) int mouseButton;
@property(nonatomic) int wheel;
@property(nonatomic) BOOL inputHeld;
@property(nonatomic) BOOL latch;
@property(nonatomic,copy) NSString *text;
@end
@implementation FPInputButton
- (void)sendDown:(BOOL)down {
    if (self.inputHeld==down) return;
    self.inputHeld=down;
    if (self.scan) FPIKeyboard(self.scan,down);
    if (down && self.text && !(SDL_GetModState()&(SDL_KMOD_CTRL|SDL_KMOD_ALT|SDL_KMOD_GUI))) {
        BOOL shift=(SDL_GetModState()&SDL_KMOD_SHIFT)!=0;
        BOOL caps=(SDL_GetModState()&SDL_KMOD_CAPS)!=0;
        NSString *text=(shift!=caps) ? self.text.uppercaseString : self.text;
        if (shift && self.text.length==1) {
            NSString *plain=@"`1234567890-=[]\\;',./";
            NSString *shifted=@"~!@#$%^&*()_+{}|:\"<>?";
            NSRange index=[plain rangeOfString:self.text];
            if (index.location!=NSNotFound) text=[shifted substringWithRange:NSMakeRange(index.location,1)];
        }
        FPIText(text.UTF8String);
    }
    if (self.mouseButton) FPIMouseButton(self.mouseButton,down);
    if (self.wheel && down) FPIWheel(self.wheel);
    self.backgroundColor=down ? [UIColor colorWithRed:0.3 green:0.5 blue:0.2 alpha:0.85] : [UIColor colorWithWhite:0.08 alpha:0.6];
}
- (void)down { [self sendDown:self.latch ? !self.inputHeld : YES]; }
- (void)up { if (!self.latch) [self sendDown:NO]; }
@end

@interface FPJoystick : UIView
@property(nonatomic) CGPoint offset;
- (void)reset;
@end
@implementation FPJoystick
- (instancetype)initWithFrame:(CGRect)frame {
    if ((self=[super initWithFrame:frame])) {self.backgroundColor=UIColor.clearColor;self.accessibilityLabel=@"Movement stick";}
    return self;
}
- (void)updatePoint:(CGPoint)p {
    CGFloat radius=self.bounds.size.width/2;
    self.offset=CGPointMake(MAX(-1,MIN(1,(p.x-radius)/radius)),MAX(-1,MIN(1,(p.y-radius)/radius)));
    FPIKeyboard(SDL_SCANCODE_A,self.offset.x < -0.25);
    FPIKeyboard(SDL_SCANCODE_D,self.offset.x > 0.25);
    FPIKeyboard(SDL_SCANCODE_W,self.offset.y < -0.25);
    FPIKeyboard(SDL_SCANCODE_S,self.offset.y > 0.25);
    [self setNeedsDisplay];
}
- (void)reset { [self updatePoint:CGPointMake(self.bounds.size.width/2,self.bounds.size.height/2)]; }
- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self updatePoint:[touches.anyObject locationInView:self]]; }
- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self touchesBegan:touches withEvent:event]; }
- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self reset]; }
- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self reset]; }
- (void)drawRect:(CGRect)rect {
    [[UIColor colorWithWhite:0.08 alpha:0.55] setFill];
    [[UIBezierPath bezierPathWithOvalInRect:CGRectInset(self.bounds,2,2)] fill];
    CGFloat r=self.bounds.size.width/2;
    [[UIColor colorWithWhite:1 alpha:0.55] setFill];
    [[UIBezierPath bezierPathWithOvalInRect:CGRectMake(r-24+self.offset.x*45,r-24+self.offset.y*45,48,48)] fill];
}
@end

@interface FPPointerSurface : UIView
@property(nonatomic) int mode;
@property(nonatomic) BOOL mining;
@property(nonatomic) CGPoint cursorPoint;
@property(nonatomic,strong) CADisplayLink *cursorUpdates;
- (void)reset;
@end
@implementation FPPointerSurface
- (instancetype)initWithFrame:(CGRect)frame {
    if ((self=[super initWithFrame:frame])) {
        self.backgroundColor=UIColor.clearColor; self.opaque=NO;
        self.contentMode=UIViewContentModeRedraw;
    }
    return self;
}
- (void)didMoveToWindow {
    [super didMoveToWindow];
    [self.cursorUpdates invalidate]; self.cursorUpdates=nil;
    if (self.window) {
        self.cursorUpdates=[CADisplayLink displayLinkWithTarget:self selector:@selector(refreshCursor)];
        self.cursorUpdates.preferredFramesPerSecond=30;
        [self.cursorUpdates addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];
    }
}
- (void)refreshCursor {
    if (self.hidden || self.mode!=2) return;
    float x,y;
    if (!FPIGetPointer(&x,&y)) return;
    CGPoint p=CGPointMake(x*self.bounds.size.width,y*self.bounds.size.height);
    if (!CGPointEqualToPoint(p,self.cursorPoint)) { self.cursorPoint=p; [self setNeedsDisplay]; }
}
- (void)drawRect:(CGRect)rect {
    if (self.mode!=2) return;
    // Arrow tip is the exact SDL click position, including after lifting a finger.
    CGContextRef context=UIGraphicsGetCurrentContext();
    CGContextSaveGState(context);
    CGContextTranslateCTM(context,self.cursorPoint.x,self.cursorPoint.y);
    UIBezierPath *arrow=[UIBezierPath bezierPath];
    [arrow moveToPoint:CGPointZero];
    [arrow addLineToPoint:CGPointMake(1,28)];
    [arrow addLineToPoint:CGPointMake(8,21)];
    [arrow addLineToPoint:CGPointMake(14,34)];
    [arrow addLineToPoint:CGPointMake(20,31)];
    [arrow addLineToPoint:CGPointMake(14,18)];
    [arrow addLineToPoint:CGPointMake(24,17)]; [arrow closePath];
    arrow.lineWidth=3; arrow.lineJoinStyle=kCGLineJoinRound;
    [UIColor.blackColor setStroke]; [arrow stroke];
    [UIColor.whiteColor setFill]; [arrow fill];
    CGContextRestoreGState(context);
}
- (void)move:(UITouch *)touch {
    CGPoint p=[touch locationInView:self];
    FPIPointer(p.x/self.bounds.size.width,p.y/self.bounds.size.height);
}
- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    [self move:touches.anyObject];
    if (self.mode==1) { self.mining=YES; FPIMouseButton(SDL_BUTTON_RIGHT,YES); }
}
- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self move:touches.anyObject]; }
- (void)reset { if (self.mining) FPIMouseButton(SDL_BUTTON_RIGHT,NO);self.mining=NO; }
- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self reset]; }
- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self reset]; }
@end

@interface FPTouchOverlay : UIView
@property(nonatomic,strong) NSMutableArray<FPInputButton *> *buttons;
@property(nonatomic,strong) UIButton *toggle;
@property(nonatomic) BOOL expanded;
@property(nonatomic,strong) FPJoystick *joystick;
@property(nonatomic,strong) FPPointerSurface *pointerSurface;
@property(nonatomic,strong) UIButton *modeButton;
@property(nonatomic,strong) UIButton *keyboardToggle;
@property(nonatomic,strong) UILabel *modeHint;
@property(nonatomic,strong) UIView *keyboard;
@property(nonatomic,strong) NSMutableArray<NSArray<FPInputButton *> *> *keyRows;
@end
@implementation FPTouchOverlay
- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    UIView *hit=[super hitTest:point withEvent:event];
    return hit==self ? nil : hit;
}
- (FPInputButton *)button:(NSString *)title scan:(int)scan {
    FPInputButton *b=[FPInputButton buttonWithType:UIButtonTypeCustom];
    b.scan=scan; b.exclusiveTouch=NO;
    b.titleLabel.font=[UIFont systemFontOfSize:15 weight:UIFontWeightSemibold];
    b.titleLabel.adjustsFontSizeToFitWidth=YES; b.titleLabel.minimumScaleFactor=0.75;
    [b setTitle:title forState:UIControlStateNormal];
    b.accessibilityLabel=title;
    b.backgroundColor=[UIColor colorWithWhite:0.08 alpha:0.6];
    b.layer.cornerRadius=10; b.layer.borderWidth=1;
    b.layer.borderColor=[UIColor colorWithWhite:1 alpha:0.3].CGColor;
    [b addTarget:b action:@selector(down) forControlEvents:UIControlEventTouchDown];
    [b addTarget:b action:@selector(up) forControlEvents:UIControlEventTouchUpInside|UIControlEventTouchUpOutside|UIControlEventTouchCancel];
    [self.buttons addObject:b]; [self addSubview:b]; return b;
}
- (instancetype)initWithFrame:(CGRect)frame {
    if ((self=[super initWithFrame:frame])) {
        self.buttons=[NSMutableArray new]; self.expanded=YES;
        self.autoresizingMask=UIViewAutoresizingFlexibleWidth|UIViewAutoresizingFlexibleHeight;
        self.pointerSurface=[[FPPointerSurface alloc] initWithFrame:self.bounds];
        self.pointerSurface.hidden=YES; [self addSubview:self.pointerSurface];
        self.joystick=[[FPJoystick alloc] initWithFrame:CGRectMake(0,0,150,150)];
        [self addSubview:self.joystick];
        [self button:@"Inventory" scan:SDL_SCANCODE_E];
        [self button:@"Rotate" scan:SDL_SCANCODE_R];
        [self button:@"Clear / pick" scan:SDL_SCANCODE_Q];
        [self button:@"Map" scan:SDL_SCANCODE_M];
        [self button:@"Research" scan:SDL_SCANCODE_T];
        [self button:@"Tab" scan:SDL_SCANCODE_TAB];
        [self button:@"Pick up" scan:SDL_SCANCODE_F];
        [self button:@"Shoot" scan:SDL_SCANCODE_SPACE];
        [self button:@"Menu" scan:SDL_SCANCODE_ESCAPE];
        [self button:@"+" scan:0].wheel=1;
        [self button:@"−" scan:0].wheel=-1;
        [self button:@"Enter" scan:SDL_SCANCODE_RETURN];
        [self button:@"Shift" scan:SDL_SCANCODE_LSHIFT].latch=YES;
        [self button:@"Ctrl" scan:SDL_SCANCODE_LCTRL].latch=YES;
        [self button:@"Alt" scan:SDL_SCANCODE_LALT].latch=YES;
        [self button:@"Left click" scan:0].mouseButton=SDL_BUTTON_LEFT;
        [self button:@"Middle click" scan:0].mouseButton=SDL_BUTTON_MIDDLE;
        [self button:@"Right click" scan:0].mouseButton=SDL_BUTTON_RIGHT;
        self.toggle=[UIButton buttonWithType:UIButtonTypeSystem];
        [self.toggle setTitle:@"Hide controls" forState:UIControlStateNormal];
        [self.toggle setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
        self.toggle.backgroundColor=[UIColor colorWithWhite:0.08 alpha:0.65];
        self.toggle.layer.cornerRadius=8;
        [self.toggle addTarget:self action:@selector(toggleControls) forControlEvents:UIControlEventTouchUpInside];
        [self addSubview:self.toggle];
        self.modeButton=[UIButton buttonWithType:UIButtonTypeSystem];
        [self.modeButton setTitle:@"Tap ▸" forState:UIControlStateNormal];
        self.modeButton.accessibilityHint=@"Switch between Tap, Mine and Cursor mode";
        [self.modeButton addTarget:self action:@selector(cycleMode) forControlEvents:UIControlEventTouchUpInside];
        self.keyboardToggle=[UIButton buttonWithType:UIButtonTypeSystem];
        [self.keyboardToggle setTitle:@"Keyboard" forState:UIControlStateNormal];
        [self.keyboardToggle addTarget:self action:@selector(toggleKeyboard) forControlEvents:UIControlEventTouchUpInside];
        for (UIButton *b in @[self.modeButton,self.keyboardToggle]) {
            b.backgroundColor=[UIColor colorWithWhite:0.08 alpha:0.65];b.layer.cornerRadius=8;
            [b setTitleColor:UIColor.whiteColor forState:UIControlStateNormal]; [self addSubview:b];
        }
        self.modeHint=[UILabel new]; self.modeHint.hidden=YES;
        self.modeHint.textColor=UIColor.whiteColor;
        self.modeHint.font=[UIFont systemFontOfSize:13 weight:UIFontWeightMedium];
        self.modeHint.numberOfLines=2; self.modeHint.textAlignment=NSTextAlignmentCenter;
        self.modeHint.backgroundColor=[UIColor colorWithWhite:0.08 alpha:0.8];
        self.modeHint.layer.cornerRadius=8; self.modeHint.clipsToBounds=YES;
        self.modeHint.userInteractionEnabled=NO;
        [self addSubview:self.modeHint];
        [self buildKeyboard];
        [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(releaseInputs) name:UIApplicationWillResignActiveNotification object:nil];
    }
    return self;
}
- (void)releaseInputs {
    for (FPInputButton *b in self.buttons) [b sendDown:NO];
    for (NSArray *row in self.keyRows) for (FPInputButton *b in row) [b sendDown:NO];
    [self.joystick reset]; [self.pointerSurface reset];
}
- (void)cycleMode {
    [self releaseInputs];
    self.pointerSurface.mode=(self.pointerSurface.mode+1)%3;
    self.pointerSurface.hidden=self.pointerSurface.mode==0;
    [self.pointerSurface refreshCursor]; [self.pointerSurface setNeedsDisplay];
    [self.modeButton setTitle:@[@"Tap ▸",@"Mine ▸",@"Cursor ▸"][self.pointerSurface.mode] forState:UIControlStateNormal];
    self.modeHint.text=self.pointerSurface.mode==1
        ? @"Hold on a tree or ore to mine.\nSwitch back to Tap to use menus."
        : @"Touch to aim; Left / Right click acts at the arrow.\nTo drag, hold a click button and slide another finger.";
    self.modeHint.hidden=self.pointerSurface.mode==0 || !self.keyboard.hidden;
}
- (void)toggleKeyboard {
    [self releaseInputs];
    self.keyboard.hidden=!self.keyboard.hidden;
    self.modeHint.hidden=!self.keyboard.hidden || self.pointerSurface.mode==0;
}
- (void)buildKeyboard {
    self.keyboard=[UIView new]; self.keyboard.hidden=YES;
    self.keyboard.backgroundColor=[UIColor colorWithWhite:0.1 alpha:0.96];self.keyboard.layer.cornerRadius=12;
    self.keyRows=[NSMutableArray new];
    NSArray<NSArray<NSString *> *> *rows=@[
        @[@"Esc",@"F1",@"F2",@"F3",@"F4",@"F5",@"F6",@"F7",@"F8",@"F9",@"F10",@"F11",@"F12"],
        @[@"`",@"1",@"2",@"3",@"4",@"5",@"6",@"7",@"8",@"9",@"0",@"-",@"=",@"⌫"],
        @[@"Tab",@"q",@"w",@"e",@"r",@"t",@"y",@"u",@"i",@"o",@"p",@"[",@"]",@"\\"],
        @[@"Caps",@"a",@"s",@"d",@"f",@"g",@"h",@"j",@"k",@"l",@";",@"'",@"Enter"],
        @[@"Shift",@"z",@"x",@"c",@"v",@"b",@"n",@"m",@",",@".",@"/",@"↑",@"Del"],
        @[@"Ctrl",@"Alt",@"Cmd",@"Space",@"Home",@"End",@"PgUp",@"PgDn",@"Ins",@"←",@"↓",@"→"]];
    NSDictionary *special=@{@"Esc":@(SDL_SCANCODE_ESCAPE),@"⌫":@(SDL_SCANCODE_BACKSPACE),@"Tab":@(SDL_SCANCODE_TAB),
        @"Caps":@(SDL_SCANCODE_CAPSLOCK),@"Enter":@(SDL_SCANCODE_RETURN),@"Shift":@(SDL_SCANCODE_LSHIFT),
        @"Ctrl":@(SDL_SCANCODE_LCTRL),@"Alt":@(SDL_SCANCODE_LALT),@"Cmd":@(SDL_SCANCODE_LGUI),
        @"Space":@(SDL_SCANCODE_SPACE),@"Home":@(SDL_SCANCODE_HOME),@"End":@(SDL_SCANCODE_END),
        @"PgUp":@(SDL_SCANCODE_PAGEUP),@"PgDn":@(SDL_SCANCODE_PAGEDOWN),@"Ins":@(SDL_SCANCODE_INSERT),
        @"Del":@(SDL_SCANCODE_DELETE),@"←":@(SDL_SCANCODE_LEFT),@"↓":@(SDL_SCANCODE_DOWN),@"→":@(SDL_SCANCODE_RIGHT),@"↑":@(SDL_SCANCODE_UP)};
    for (NSArray<NSString *> *labels in rows) {
        NSMutableArray *buttons=[NSMutableArray new];
        for (NSString *label in labels) {
            SDL_Scancode scan=special[label] ? [special[label] intValue] : SDL_GetScancodeFromName(label.UTF8String);
            FPInputButton *b=[self button:label scan:scan];
            [self.buttons removeLastObject];
            b.latch=[@[@"Shift",@"Ctrl",@"Alt",@"Cmd"] containsObject:label];
            if (label.length==1) b.text=label;
            if ([label isEqual:@"Space"]) b.text=@" ";
            [self.keyboard addSubview:b]; [buttons addObject:b];
        }
        [self.keyRows addObject:buttons];
    }
    [self addSubview:self.keyboard];
}
- (void)toggleControls {
    [self releaseInputs]; self.expanded=!self.expanded;
    for (UIView *v in self.buttons) v.hidden=!self.expanded;
    self.joystick.hidden=!self.expanded;
    self.modeButton.hidden=!self.expanded;self.keyboardToggle.hidden=!self.expanded;
    self.keyboard.hidden=YES;
    self.pointerSurface.hidden=!self.expanded || self.pointerSurface.mode==0;
    self.modeHint.hidden=!self.expanded || self.pointerSurface.mode==0;
    [self.toggle setTitle:self.expanded ? @"Hide controls" : @"Show controls" forState:UIControlStateNormal];
}
- (void)layoutSubviews {
    [super layoutSubviews];
    CGFloat left=MAX(self.safeAreaInsets.left,12), bottom=self.bounds.size.height-MAX(self.safeAreaInsets.bottom,12)-72;
    // Keep the tutorial/objective panel in the upper-left corner readable.
    self.toggle.frame=CGRectMake((self.bounds.size.width-352)/2,MAX(self.safeAreaInsets.top,12),112,36);
    self.modeButton.frame=CGRectOffset(self.toggle.frame,120,0);
    self.keyboardToggle.frame=CGRectOffset(self.toggle.frame,240,0);
    CGFloat hintWidth=MIN(440,self.bounds.size.width-32);
    self.modeHint.frame=CGRectMake((self.bounds.size.width-hintWidth)/2,CGRectGetMaxY(self.toggle.frame)+6,hintWidth,44);
    self.joystick.frame=CGRectMake(left,bottom-160,150,150);
    self.pointerSurface.frame=self.bounds;
    CGFloat right=self.bounds.size.width-MAX(self.safeAreaInsets.right,12)-248;
    NSUInteger rows=(self.buttons.count+2)/3;
    for (NSUInteger i=0;i<self.buttons.count;i++) {
        NSUInteger index=i;
        self.buttons[i].frame=CGRectMake(right+(index%3)*84,bottom-rows*44+(index/3)*44,80,40);
    }
    CGFloat width=MIN(900,self.bounds.size.width-32);
    self.keyboard.frame=CGRectMake((self.bounds.size.width-width)/2,CGRectGetMaxY(self.toggle.frame)+10,width,288);
    for (NSUInteger row=0;row<self.keyRows.count;row++) {
        NSArray *keys=self.keyRows[row]; CGFloat keyWidth=(width-12)/keys.count;
        for (NSUInteger col=0;col<keys.count;col++) ((UIView *)keys[col]).frame=CGRectMake(6+col*keyWidth,6+row*46,keyWidth-4,42);
    }
}
@end

void InstallTouchControls(void) {
    [NSTimer scheduledTimerWithTimeInterval:0.5 repeats:YES block:^(NSTimer *timer) {
        if (!SDL_GetKeyboardFocus()) return;
        UIWindow *window=nil;
        for (UIWindow *candidate in UIApplication.sharedApplication.windows) if (candidate.isKeyWindow) {window=candidate;break;}
        if (!window.rootViewController) return;
        FPTouchOverlay *overlay=[[FPTouchOverlay alloc] initWithFrame:window.bounds];
        [window addSubview:overlay];
        [timer invalidate];
        fprintf(stderr,"FACTORIO_PROBE: touch controls installed\n");
    }];
}
