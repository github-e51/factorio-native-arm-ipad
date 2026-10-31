#import <UIKit/UIKit.h>
#import <GameController/GameController.h>
#import <objc/runtime.h>
#include "SDL.h"
#if FPI_SDL_MAJOR == 3
#define FPI_MOD_CTRL SDL_KMOD_CTRL
#define FPI_MOD_ALT SDL_KMOD_ALT
#define FPI_MOD_GUI SDL_KMOD_GUI
#define FPI_MOD_SHIFT SDL_KMOD_SHIFT
#define FPI_MOD_CAPS SDL_KMOD_CAPS
#else
#define FPI_MOD_CTRL KMOD_CTRL
#define FPI_MOD_ALT KMOD_ALT
#define FPI_MOD_GUI KMOD_GUI
#define FPI_MOD_SHIFT KMOD_SHIFT
#define FPI_MOD_CAPS KMOD_CAPS
#endif

extern void FPIKeyboard(int scan,int down);
extern void FPIMouseButton(int button,int down);
extern void FPIWheel(float y);
extern void FPIText(const char *text);
extern void FPIPointer(float x,float y);
extern int FPIGetPointer(float *x,float *y);
extern void FPIMouseDelta(float dx,float dy);
extern void FPISetReservedBottom(float bottom);

// Translucent dark chrome with one warm accent, so controls recede over the factory.
static UIColor *FPSurface(void) { return [UIColor colorWithWhite:0.05 alpha:0.55]; }
static UIColor *FPStroke(void) { return [UIColor colorWithWhite:1 alpha:0.16]; }
static UIColor *FPAccent(void) { return [UIColor colorWithRed:1 green:0.65 blue:0.18 alpha:0.95]; }
static UIColor *FPInk(void) { return [UIColor colorWithWhite:0.08 alpha:1]; }
static UIImpactFeedbackGenerator *FPPressFeedback(void) {
    static UIImpactFeedbackGenerator *generator;
    static dispatch_once_t once;
    dispatch_once(&once,^{ generator=[[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleLight]; });
    return generator;
}

// iOS delivers GCMouse movement only to a scene whose root view controller locks the
// pointer, and SDL locks it only in relative mode. Ask for the lock whenever a mouse is
// connected; iPad grants it, iPhone (tested on iPhone Duo, iOS 27.1) does not.
static BOOL FPPointerLockWanted;
static void FPRequestPointerLock(UIViewController *controller,BOOL lock) {
    static Class patched;
    if (!controller) return;
    if (patched!=controller.class) {
        patched=controller.class;
        SEL selector=@selector(prefersPointerLocked);
        Method method=class_getInstanceMethod(patched,selector);
        __block IMP original=NULL;
        IMP replacement=imp_implementationWithBlock(^BOOL(UIViewController *self) {
            return FPPointerLockWanted || (original && ((BOOL(*)(id,SEL))original)(self,selector));
        });
        original=class_replaceMethod(patched,selector,replacement,method_getTypeEncoding(method));
    }
    FPPointerLockWanted=lock;
    [controller setNeedsUpdateOfPrefersPointerLocked];

}

static BOOL FPLeftButtonArrives;

@interface FPInputButton : UIButton
@property(nonatomic) int scan;
@property(nonatomic) int mouseButton;
@property(nonatomic) int wheel;
@property(nonatomic) BOOL inputHeld;
@property(nonatomic) BOOL latch;
@property(nonatomic) BOOL standalone; // Draws its own disc instead of sitting on a shared pill.
@property(nonatomic) BOOL captioned;  // Icon above a small title.
@property(nonatomic,copy) NSString *text;
- (void)refreshAppearance;
@end
@implementation FPInputButton
- (void)sendDown:(BOOL)down {
    if (self.inputHeld==down) return;
    self.inputHeld=down;
    if (self.scan) FPIKeyboard(self.scan,down);
    if (down && self.text && !(SDL_GetModState()&(FPI_MOD_CTRL|FPI_MOD_ALT|FPI_MOD_GUI))) {
        BOOL shift=(SDL_GetModState()&FPI_MOD_SHIFT)!=0;
        BOOL caps=(SDL_GetModState()&FPI_MOD_CAPS)!=0;
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
    if (down) [FPPressFeedback() impactOccurred];
    [self refreshAppearance];
}
- (void)down { [self sendDown:self.latch ? !self.inputHeld : YES]; }
- (void)up { if (!self.latch) [self sendDown:NO]; }
- (void)setHighlighted:(BOOL)highlighted { [super setHighlighted:NO]; }
- (void)refreshAppearance {
    UIColor *ink=self.inputHeld ? FPInk() : UIColor.whiteColor;
    self.backgroundColor=self.inputHeld ? FPAccent() : (self.standalone ? FPSurface() : UIColor.clearColor);
    self.layer.borderWidth=self.standalone && !self.inputHeld ? 1 : 0;
    self.tintColor=ink; [self setTitleColor:ink forState:UIControlStateNormal];
    self.transform=self.inputHeld && !self.latch ? CGAffineTransformMakeScale(0.93,0.93) : CGAffineTransformIdentity;
}
- (void)layoutSubviews {
    [super layoutSubviews];
    UIImage *image=self.imageView.image;
    if (!self.captioned || !image) return;
    CGSize size=self.bounds.size, icon=image.size;
    CGFloat captionHeight=ceil(self.titleLabel.font.lineHeight), top=floor((size.height-icon.height-captionHeight)/2);
    self.imageView.frame=CGRectMake(floor((size.width-icon.width)/2),top,icon.width,icon.height);
    self.titleLabel.frame=CGRectMake(3,top+icon.height,size.width-6,captionHeight);
}
@end

@interface FPJoystick : UIView
@property(nonatomic) CGPoint offset;
@property(nonatomic) int direction; // -1 at rest, else 0-7 clockwise from east.
- (void)reset;
- (void)updatePoint:(CGPoint)p;
@end
@implementation FPJoystick
- (instancetype)initWithFrame:(CGRect)frame {
    if ((self=[super initWithFrame:frame])) {
        self.backgroundColor=UIColor.clearColor; self.opaque=NO; self.direction=-1;
        self.contentMode=UIViewContentModeRedraw; self.accessibilityLabel=@"Movement stick";
    }
    return self;
}
static BOOL FPDirectionHas(int direction,int a,int b,int c) { return direction==a || direction==b || direction==c; }
- (void)updatePoint:(CGPoint)p {
    CGFloat radius=self.bounds.size.width/2;
    CGFloat dx=(p.x-radius)/radius, dy=(p.y-radius)/radius, length=hypot(dx,dy);
    if (length>1) { dx/=length; dy/=length; }
    self.offset=CGPointMake(dx,dy);
    // Eight equal sectors make diagonals as easy to hold as the cardinal directions.
    int direction=length<0.22 ? -1 : ((int)lround(atan2(dy,dx)/(M_PI/4))+8)%8;
    if (direction!=self.direction) {
        self.direction=direction;
        FPIKeyboard(SDL_SCANCODE_D,FPDirectionHas(direction,7,0,1));
        FPIKeyboard(SDL_SCANCODE_S,FPDirectionHas(direction,1,2,3));
        FPIKeyboard(SDL_SCANCODE_A,FPDirectionHas(direction,3,4,5));
        FPIKeyboard(SDL_SCANCODE_W,FPDirectionHas(direction,5,6,7));
    }
    [self setNeedsDisplay];
}
- (void)reset { [self updatePoint:CGPointMake(self.bounds.size.width/2,self.bounds.size.height/2)]; }
- (BOOL)pointInside:(CGPoint)point withEvent:(UIEvent *)event {
    CGFloat r=self.bounds.size.width/2+18;
    return hypot(point.x-self.bounds.size.width/2,point.y-self.bounds.size.height/2)<=r;
}
- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self updatePoint:[touches.anyObject locationInView:self]]; }
- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self touchesBegan:touches withEvent:event]; }
- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self reset]; }
- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self reset]; }
- (void)drawRect:(CGRect)rect {
    CGFloat r=self.bounds.size.width/2;
    UIBezierPath *base=[UIBezierPath bezierPathWithOvalInRect:CGRectInset(self.bounds,1,1)];
    [FPSurface() setFill]; [base fill];
    [FPStroke() setStroke]; base.lineWidth=1; [base stroke];
    CGContextRef context=UIGraphicsGetCurrentContext();
    const int lit[4][3]={{7,0,1},{1,2,3},{3,4,5},{5,6,7}};
    for (int i=0;i<4;i++) {
        CGContextSaveGState(context);
        CGContextTranslateCTM(context,r,r); CGContextRotateCTM(context,i*M_PI/2);
        CGFloat x=r-r*0.16, size=r*0.07;
        UIBezierPath *chevron=[UIBezierPath bezierPath];
        [chevron moveToPoint:CGPointMake(x-size,-size*1.6)];
        [chevron addLineToPoint:CGPointMake(x+size,0)];
        [chevron addLineToPoint:CGPointMake(x-size,size*1.6)];
        chevron.lineWidth=2; chevron.lineCapStyle=kCGLineCapRound; chevron.lineJoinStyle=kCGLineJoinRound;
        [(FPDirectionHas(self.direction,lit[i][0],lit[i][1],lit[i][2]) ? FPAccent() : [UIColor colorWithWhite:1 alpha:0.35]) setStroke];
        [chevron stroke];
        CGContextRestoreGState(context);
    }
    CGFloat thumb=r*0.4, travel=r-thumb-r*0.08;
    CGRect knob=CGRectMake(r-thumb+self.offset.x*travel,r-thumb+self.offset.y*travel,thumb*2,thumb*2);
    UIBezierPath *path=[UIBezierPath bezierPathWithOvalInRect:knob];
    [[UIColor colorWithWhite:1 alpha:self.direction<0 ? 0.55 : 0.9] setFill]; [path fill];
    [[UIColor colorWithWhite:0 alpha:0.25] setStroke]; path.lineWidth=1; [path stroke];
}
@end

@interface FPPointerSurface : UIView
@property(nonatomic) int mode;
@property(nonatomic) BOOL hardwareCursor; // A Bluetooth mouse or trackpad is connected.
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
- (CGRect)gameRect {
    UIView *game=self.window.rootViewController.view;
    if (!game || !game.window) return self.bounds;
    CGRect rect=[game convertRect:game.bounds toView:self];
    return rect.size.width>0 && rect.size.height>0 ? rect : self.bounds;
}
- (BOOL)drawsCursor { return self.mode==2 || self.hardwareCursor; }
- (void)refreshCursor {
    if (self.hidden || !self.drawsCursor) return;
    float x,y;
    if (!FPIGetPointer(&x,&y)) return;
    CGRect game=[self gameRect];
    CGPoint p=CGPointMake(CGRectGetMinX(game)+x*game.size.width,
                          CGRectGetMinY(game)+y*game.size.height);
    if (!CGPointEqualToPoint(p,self.cursorPoint)) { self.cursorPoint=p; [self setNeedsDisplay]; }
}
- (void)drawRect:(CGRect)rect {
    if (!self.drawsCursor) return;
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
    CGRect game=[self gameRect];
    FPIPointer(MAX(0,MIN(1,(p.x-CGRectGetMinX(game))/game.size.width)),
               MAX(0,MIN(1,(p.y-CGRectGetMinY(game))/game.size.height)));
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
@property(nonatomic,strong) NSArray<FPInputButton *> *menuRail, *zoomPair, *modifierPair, *cluster;
@property(nonatomic,strong) UIView *systemPill, *systemDivider, *menuPill, *zoomPill, *modifierPill, *deck;
@property(nonatomic,strong) UIButton *toggle;
@property(nonatomic) BOOL expanded;
@property(nonatomic) BOOL dimmed;
@property(nonatomic) BOOL split;        // Portrait: game above, controls on a deck below.
@property(nonatomic) BOOL autoHidden;   // Collapsed because hardware input connected.
@property(nonatomic) BOOL hadHardware;
@property(nonatomic) BOOL systemPointer; // iOS draws its own pointer (AssistiveTouch on iOS 27.2+).
@property(nonatomic) BOOL mouseMoves;   // Pointer movement arrives: GCMouse deltas (iPad) or hover (AssistiveTouch).
@property(nonatomic) CGFloat gameReserve;
@property(nonatomic,strong) NSHashTable<GCMouse *> *adoptedMice;
@property(nonatomic,strong) FPJoystick *joystick;
@property(nonatomic,strong) FPPointerSurface *pointerSurface;
@property(nonatomic,strong) NSArray<UIButton *> *modeButtons;
@property(nonatomic,strong) UIButton *keyboardToggle;
@property(nonatomic,strong) UILabel *modeHint;
@property(nonatomic,strong) UIView *keyboard;
@property(nonatomic,strong) NSMutableArray<NSArray<FPInputButton *> *> *keyRows;
@property(nonatomic) CGSize previousLayoutSize;
@end
@implementation FPTouchOverlay
- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    UIView *hit=[super hitTest:point withEvent:event];
    if (hit==self || hit==self.deck) return nil;
    if (hit && hit!=self.pointerSurface) [self wake];
    return hit;
}
// Hardware keyboards normally reach SDL through GameController. As a second route, receive the
// iPhone's own key presses here and pass them on as the same scancodes (USB HID usages match
// SDL's). SDL ignores a key that is already held, so both routes together never double up.
- (BOOL)canBecomeFirstResponder { return YES; }
- (void)claimKeyboard {
    BOOL typing;
#if FPI_SDL_MAJOR == 3
    typing=SDL_TextInputActive(SDL_GetKeyboardFocus());
#else
    typing=SDL_IsTextInputActive();
#endif
    if (self.window && !typing && !self.isFirstResponder) [self becomeFirstResponder];
}
- (void)forwardPresses:(NSSet<UIPress *> *)presses down:(BOOL)down {
    for (UIPress *press in presses) {
        if (!press.key) continue;
        NSInteger code=press.key.keyCode;
        if (code>0 && code<512) FPIKeyboard((int)code,down);
    }
}
- (void)pressesBegan:(NSSet<UIPress *> *)presses withEvent:(UIPressesEvent *)event { [self forwardPresses:presses down:YES]; }
- (void)pressesEnded:(NSSet<UIPress *> *)presses withEvent:(UIPressesEvent *)event { [self forwardPresses:presses down:NO]; }
- (void)pressesCancelled:(NSSet<UIPress *> *)presses withEvent:(UIPressesEvent *)event { [self forwardPresses:presses down:NO]; }
- (UIView *)pill {
    UIView *pill=[UIView new];
    pill.backgroundColor=FPSurface(); pill.userInteractionEnabled=NO;
    pill.layer.borderWidth=1; pill.layer.borderColor=FPStroke().CGColor;
    [self addSubview:pill]; return pill;
}
- (FPInputButton *)button:(NSString *)title symbol:(NSString *)symbol scan:(int)scan {
    FPInputButton *b=[FPInputButton buttonWithType:UIButtonTypeCustom];
    b.scan=scan; b.exclusiveTouch=NO;
    b.titleLabel.font=[UIFont systemFontOfSize:15 weight:UIFontWeightSemibold];
    b.titleLabel.adjustsFontSizeToFitWidth=YES; b.titleLabel.minimumScaleFactor=0.6;
    b.titleLabel.textAlignment=NSTextAlignmentCenter;
    UIImage *image=symbol ? [UIImage systemImageNamed:symbol] : nil;
    if (image) [b setImage:[image imageWithRenderingMode:UIImageRenderingModeAlwaysTemplate] forState:UIControlStateNormal];
    else [b setTitle:title forState:UIControlStateNormal];
    b.accessibilityLabel=title;
    b.layer.borderColor=FPStroke().CGColor;
    [b addTarget:b action:@selector(down) forControlEvents:UIControlEventTouchDown];
    [b addTarget:b action:@selector(up) forControlEvents:UIControlEventTouchUpInside|UIControlEventTouchUpOutside|UIControlEventTouchCancel];
    [b refreshAppearance];
    [self.buttons addObject:b]; [self addSubview:b]; return b;
}
- (FPInputButton *)clusterButton:(NSString *)title caption:(NSString *)caption symbol:(NSString *)symbol scan:(int)scan {
    FPInputButton *b=[self button:title symbol:symbol scan:scan];
    b.standalone=YES; b.captioned=YES;
    [b setTitle:caption forState:UIControlStateNormal];
    [b refreshAppearance]; return b;
}
- (UIButton *)systemButton:(NSString *)symbol label:(NSString *)label action:(SEL)action {
    UIButton *b=[UIButton buttonWithType:UIButtonTypeSystem];
    [b setImage:[UIImage systemImageNamed:symbol] forState:UIControlStateNormal];
    b.tintColor=UIColor.whiteColor; b.accessibilityLabel=label;
    [b addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:b]; return b;
}
- (instancetype)initWithFrame:(CGRect)frame {
    if ((self=[super initWithFrame:frame])) {
        self.buttons=[NSMutableArray new]; self.expanded=YES;
        self.adoptedMice=[NSHashTable weakObjectsHashTable];
        self.autoresizingMask=UIViewAutoresizingFlexibleWidth|UIViewAutoresizingFlexibleHeight;
        self.pointerSurface=[[FPPointerSurface alloc] initWithFrame:self.bounds];
        self.pointerSurface.hidden=YES; [self addSubview:self.pointerSurface];
        self.deck=[UIView new]; self.deck.hidden=YES;
        self.deck.backgroundColor=[UIColor colorWithWhite:0.07 alpha:1];
        self.deck.layer.cornerRadius=24; self.deck.layer.maskedCorners=kCALayerMinXMinYCorner|kCALayerMaxXMinYCorner;
        self.deck.layer.borderWidth=1; self.deck.layer.borderColor=FPStroke().CGColor;
        [self addSubview:self.deck];
        self.systemPill=[self pill]; self.menuPill=[self pill];
        self.zoomPill=[self pill]; self.modifierPill=[self pill];
        self.systemDivider=[UIView new]; self.systemDivider.backgroundColor=FPStroke();
        self.systemDivider.userInteractionEnabled=NO; [self addSubview:self.systemDivider];
        self.joystick=[[FPJoystick alloc] initWithFrame:CGRectMake(0,0,130,130)];
        [self addSubview:self.joystick];

        self.menuRail=@[[self button:@"Menu" symbol:@"line.3.horizontal" scan:SDL_SCANCODE_ESCAPE],
                        [self button:@"Inventory" symbol:@"backpack" scan:SDL_SCANCODE_E],
                        [self button:@"Research" symbol:@"flask" scan:SDL_SCANCODE_T],
                        [self button:@"Map" symbol:@"map" scan:SDL_SCANCODE_M]];
        FPInputButton *zoomOut=[self button:@"Zoom out" symbol:@"minus.magnifyingglass" scan:0];
        FPInputButton *zoomIn=[self button:@"Zoom in" symbol:@"plus.magnifyingglass" scan:0];
        zoomOut.wheel=-1; zoomIn.wheel=1;
        self.zoomPair=@[zoomOut,zoomIn];
        self.modifierPair=@[[self button:@"Shift" symbol:nil scan:SDL_SCANCODE_LSHIFT],
                            [self button:@"Ctrl" symbol:nil scan:SDL_SCANCODE_LCTRL],
                            [self button:@"Alt" symbol:nil scan:SDL_SCANCODE_LALT]];
        for (FPInputButton *b in self.modifierPair) b.latch=YES;

        // Primary action at the thumb's resting point, secondary actions on two arcs around it.
        FPInputButton *use=[self clusterButton:@"Left click" caption:@"Use" symbol:@"hand.point.up.left.fill" scan:0];
        FPInputButton *mine=[self clusterButton:@"Right click" caption:@"Mine" symbol:@"hammer.fill" scan:0];
        FPInputButton *middle=[self clusterButton:@"Middle click" caption:@"Middle" symbol:@"computermouse" scan:0];
        use.mouseButton=SDL_BUTTON_LEFT; mine.mouseButton=SDL_BUTTON_RIGHT; middle.mouseButton=SDL_BUTTON_MIDDLE;
        self.cluster=@[use,mine,
                       [self clusterButton:@"Rotate" caption:@"Rotate" symbol:@"arrow.clockwise" scan:SDL_SCANCODE_R],
                       [self clusterButton:@"Clear / pick" caption:@"Pipette" symbol:@"eyedropper" scan:SDL_SCANCODE_Q],
                       [self clusterButton:@"Pick up" caption:@"Pick up" symbol:@"tray.and.arrow.down.fill" scan:SDL_SCANCODE_F],
                       [self clusterButton:@"Shoot" caption:@"Shoot" symbol:@"scope" scan:SDL_SCANCODE_SPACE],
                       [self clusterButton:@"Switch gun" caption:@"Gun" symbol:@"arrow.left.arrow.right" scan:SDL_SCANCODE_TAB],
                       middle];

        self.modeButtons=@[[self systemButton:@"hand.tap" label:@"Tap mode" action:@selector(selectMode:)],
                           [self systemButton:@"hammer" label:@"Mine mode" action:@selector(selectMode:)],
                           [self systemButton:@"cursorarrow" label:@"Cursor mode" action:@selector(selectMode:)]];
        self.keyboardToggle=[self systemButton:@"keyboard" label:@"Keyboard" action:@selector(toggleKeyboard)];
        self.toggle=[self systemButton:@"eye.slash" label:@"Hide controls" action:@selector(toggleControls)];
        for (UIButton *b in self.modeButtons) b.accessibilityHint=@"Switch between Tap, Mine and Cursor mode";

        self.modeHint=[UILabel new]; self.modeHint.alpha=0;
        self.modeHint.textColor=UIColor.whiteColor;
        self.modeHint.font=[UIFont systemFontOfSize:13 weight:UIFontWeightMedium];
        self.modeHint.numberOfLines=2; self.modeHint.textAlignment=NSTextAlignmentCenter;
        self.modeHint.backgroundColor=[UIColor colorWithWhite:0.05 alpha:0.8];
        self.modeHint.layer.cornerRadius=10; self.modeHint.clipsToBounds=YES;
        self.modeHint.userInteractionEnabled=NO;
        [self addSubview:self.modeHint];
        [self buildKeyboard];
        [self refreshModeButtons];
        [self wake];
        NSNotificationCenter *center=[NSNotificationCenter defaultCenter];
        [center addObserver:self selector:@selector(releaseInputs) name:UIApplicationWillResignActiveNotification object:nil];
        for (NSNotificationName name in @[GCMouseDidConnectNotification,GCMouseDidDisconnectNotification,
                                          GCKeyboardDidConnectNotification,GCKeyboardDidDisconnectNotification,
                                          GCControllerDidConnectNotification,GCControllerDidDisconnectNotification])
            [center addObserver:self selector:@selector(hardwareChanged:) name:name object:nil];
        dispatch_async(dispatch_get_main_queue(),^{ [self hardwareChanged:nil]; [self claimKeyboard]; });
        // Take the keyboard back whenever the game's own text entry closes or the app returns.
        for (NSNotificationName name in @[UIKeyboardDidHideNotification,UIApplicationDidBecomeActiveNotification,
                                          GCKeyboardDidConnectNotification])
            [center addObserver:self selector:@selector(claimKeyboard) name:name object:nil];

    }
    return self;
}
// SDL installs its GCMouse handlers first (its observers were registered earlier); chain ours after them.
- (void)adoptMouse:(GCMouse *)mouse {
    if ([self.adoptedMice containsObject:mouse]) return;
    [self.adoptedMice addObject:mouse];
    GCMouseMoved previous=mouse.mouseInput.mouseMovedHandler;
    __weak FPTouchOverlay *weakSelf=self;
    mouse.mouseInput.mouseMovedHandler=^(GCMouseInput *input,float deltaX,float deltaY) {
        if (previous) previous(input,deltaX,deltaY);
        FPIMouseDelta(deltaX,-deltaY);
        if (!weakSelf.mouseMoves) dispatch_async(dispatch_get_main_queue(),^{
            if (weakSelf.mouseMoves) return;
            weakSelf.mouseMoves=YES; [weakSelf hardwareChanged:nil];
        });
    };
    // On iPhone Duo with iOS 27.1, AssistiveTouch takes a trackpad's primary button for its tap and
    // then delivers that tap only to the outer display, so the inner display gets no left click at all;
    // only the right button arrives. Let the right button click instead until a real left-button event
    // shows the trackpad is fully available. iOS 27.2 delivers the tap, so keep the right button there.
    BOOL phone=UIDevice.currentDevice.userInterfaceIdiom==UIUserInterfaceIdiomPhone;
    if (@available(iOS 27.2, *)) phone=NO;
    GCControllerButtonValueChangedHandler left=mouse.mouseInput.leftButton.pressedChangedHandler;
    mouse.mouseInput.leftButton.pressedChangedHandler=^(GCControllerButtonInput *input,float value,BOOL pressed) {
        FPLeftButtonArrives=YES;
        if (left) left(input,value,pressed);
    };
    GCControllerButtonValueChangedHandler right=mouse.mouseInput.rightButton.pressedChangedHandler;
    __block BOOL clicking=NO;
    mouse.mouseInput.rightButton.pressedChangedHandler=^(GCControllerButtonInput *input,float value,BOOL pressed) {
        if (pressed) clicking=phone && !FPLeftButtonArrives;
        if (clicking) FPIMouseButton(SDL_BUTTON_LEFT,pressed);
        else if (right) right(input,value,pressed);
    };
}


// On iPhone Duo with iOS 27.1, AssistiveTouch draws its pointer only on the outer display, but its
// hover still reaches the inner display, and SDL turns it into mouse motion. Draw our own arrow then.
// iOS 27.2 draws the pointer on the inner display itself, so a second arrow would only duplicate it.
// Hover arrives only while iOS shows a pointer; UIAccessibilityIsAssistiveTouchRunning() reports NO
// for AssistiveTouch used as a pointer (tested on iOS 27.2 RC2), so hover is the signal.
- (void)didMoveToWindow {
    [super didMoveToWindow];
    if (!self.window) return;
    UIHoverGestureRecognizer *hover=[[UIHoverGestureRecognizer alloc] initWithTarget:self action:@selector(pointerHovered)];
    hover.cancelsTouchesInView=NO;
    [self.window addGestureRecognizer:hover];
}
- (void)pointerHovered {
    if (!GCMouse.mice.count) return;
    if (@available(iOS 27.2, *)) {
        if (!self.systemPointer) { self.systemPointer=YES; [self hardwareChanged:nil]; }
        return;
    }
    if (self.mouseMoves) return;
    self.mouseMoves=YES; [self hardwareChanged:nil];
}
- (void)hardwareChanged:(NSNotification *)note {
    if (![NSThread isMainThread]) { dispatch_async(dispatch_get_main_queue(),^{ [self hardwareChanged:note]; }); return; }
    if ([note.name isEqual:GCMouseDidDisconnectNotification]) [self.adoptedMice removeObject:note.object];
    NSArray<GCMouse *> *mice=GCMouse.mice;
    for (GCMouse *mouse in mice) [self adoptMouse:mouse];
    BOOL keyboard=GCKeyboard.coalescedKeyboard!=nil, controller=GCController.controllers.count>0;
    BOOL hardware=mice.count>0 || keyboard || controller;
    // iPhone reports a connected trackpad but sends no GCMouse movement unless iOS grants pointer lock,
    // which it refuses; there the pointer comes from AssistiveTouch hover. Draw our arrow only once
    // movement really arrives, rather than leaving a dead arrow in the corner.
    if (!mice.count) self.mouseMoves=self.systemPointer=NO;
    self.pointerSurface.hardwareCursor=mice.count>0 && self.mouseMoves && !self.systemPointer;
    if (self.window) FPRequestPointerLock(self.window.rootViewController,mice.count>0);
    [self applyVisibility]; [self.pointerSurface refreshCursor]; [self.pointerSurface setNeedsDisplay];
    // Hardware players rarely want the touch controls; keep them one tap away on the eye.
    if (hardware && !self.hadHardware && self.expanded) {
        [self toggleControls]; self.autoHidden=YES;
        NSString *device=controller ? @"Controller" : mice.count ? @"Trackpad" : @"Keyboard";
        BOOL phone=self.traitCollection.userInterfaceIdiom==UIUserInterfaceIdiomPhone;
        NSString *detail=mice.count && phone ? @"\nTrackpad: right button clicks. Needs AssistiveTouch for a pointer." : @"\nTap the eye to bring them back.";
        [self showHint:[[device stringByAppendingString:@" connected — touch controls hidden."] stringByAppendingString:detail]];
    } else if (!hardware && self.hadHardware && self.autoHidden && !self.expanded) {
        [self toggleControls];
    }
    if (!hardware) self.autoHidden=NO;
    self.hadHardware=hardware;
}
- (NSArray<UIView *> *)fadingViews {
    NSMutableArray *views=[NSMutableArray arrayWithArray:self.buttons];
    [views addObjectsFromArray:self.modeButtons];
    [views addObjectsFromArray:@[self.joystick,self.systemPill,self.systemDivider,self.menuPill,self.zoomPill,
                                 self.modifierPill,self.keyboardToggle,self.toggle]];
    return views;
}
// Controls fade back while the player watches the factory and return on the next touch.
- (void)wake {
    [NSObject cancelPreviousPerformRequestsWithTarget:self selector:@selector(rest) object:nil];
    [self performSelector:@selector(rest) withObject:nil afterDelay:5];
    if (!self.dimmed) return;
    self.dimmed=NO;
    [UIView animateWithDuration:0.15 animations:^{ for (UIView *v in [self fadingViews]) v.alpha=1; }];
}
- (void)rest {
    BOOL held=self.joystick.direction>=0;
    for (FPInputButton *b in self.buttons) held=held || (b.inputHeld && !b.latch);
    if (held || !self.keyboard.hidden || self.split) { [self wake]; return; }
    self.dimmed=YES;
    [UIView animateWithDuration:0.6 animations:^{ for (UIView *v in [self fadingViews]) v.alpha=0.45; }];
}
- (void)releaseInputs {
    for (FPInputButton *b in self.buttons) [b sendDown:NO];
    for (NSArray *row in self.keyRows) for (FPInputButton *b in row) [b sendDown:NO];
    [self.joystick reset]; [self.pointerSurface reset];
}
- (void)refreshModeButtons {
    for (NSUInteger i=0;i<self.modeButtons.count;i++) {
        BOOL selected=(int)i==self.pointerSurface.mode;
        self.modeButtons[i].backgroundColor=selected ? FPAccent() : UIColor.clearColor;
        self.modeButtons[i].tintColor=selected ? FPInk() : UIColor.whiteColor;
        self.modeButtons[i].accessibilityTraits=selected ? UIAccessibilityTraitButton|UIAccessibilityTraitSelected : UIAccessibilityTraitButton;
    }
}
- (void)selectMode:(UIButton *)sender { [self setMode:(int)[self.modeButtons indexOfObject:sender]]; }
- (void)cycleMode { [self setMode:(self.pointerSurface.mode+1)%3]; }
- (void)setMode:(int)mode {
    [self releaseInputs];
    self.pointerSurface.mode=mode;
    [self applyVisibility];
    [self.pointerSurface refreshCursor]; [self.pointerSurface setNeedsDisplay];
    [self refreshModeButtons];
    [FPPressFeedback() impactOccurred];
    [self showHint:@[@"Tap: touches go straight to the game.",
                     @"Mine: hold on a tree or ore to mine it.\nSwitch back to Tap for menus.",
                     @"Cursor: touch to aim, then Use or Mine acts at the arrow.\nTo drag, hold a button and slide another finger."][mode]];
}
- (void)showHint:(NSString *)text {
    self.modeHint.text=text;
    [NSObject cancelPreviousPerformRequestsWithTarget:self selector:@selector(fadeHint) object:nil];
    [self setNeedsLayout];
    [UIView animateWithDuration:0.2 animations:^{ self.modeHint.alpha=self.keyboard.hidden ? 1 : 0; }];
    [self performSelector:@selector(fadeHint) withObject:nil afterDelay:3.2];
}
- (void)fadeHint { [UIView animateWithDuration:0.4 animations:^{ self.modeHint.alpha=0; }]; }
- (void)applyVisibility {
    BOOL playing=self.expanded && self.keyboard.hidden;
    for (UIView *v in self.buttons) v.hidden=!playing;
    for (UIView *v in @[self.menuPill,self.zoomPill,self.modifierPill,self.joystick]) v.hidden=!playing;
    for (UIView *v in self.modeButtons) v.hidden=!self.expanded;
    self.keyboardToggle.hidden=!self.expanded; self.systemDivider.hidden=!self.expanded;
    // The surface captures touches only for Mine and Cursor; it still draws the arrow for a hardware mouse.
    BOOL captures=self.expanded && self.pointerSurface.mode!=0;
    self.pointerSurface.userInteractionEnabled=captures;
    self.pointerSurface.hidden=!captures && !self.pointerSurface.hardwareCursor && !(self.expanded && self.pointerSurface.mode==2);
    self.keyboardToggle.backgroundColor=self.keyboard.hidden ? UIColor.clearColor : FPAccent();
    self.keyboardToggle.tintColor=self.keyboard.hidden ? UIColor.whiteColor : FPInk();
    [self.toggle setImage:[UIImage systemImageNamed:self.expanded ? @"eye.slash" : @"eye"] forState:UIControlStateNormal];
    self.toggle.accessibilityLabel=self.expanded ? @"Hide controls" : @"Show controls";
    [self setNeedsLayout];
}
- (void)toggleKeyboard {
    [self releaseInputs];
    self.keyboard.hidden=!self.keyboard.hidden;
    if (!self.keyboard.hidden) self.modeHint.alpha=0;
    [self applyVisibility];
}
- (void)buildKeyboard {
    self.keyboard=[UIView new]; self.keyboard.hidden=YES;
    self.keyboard.backgroundColor=[UIColor colorWithWhite:0.06 alpha:0.94];self.keyboard.layer.cornerRadius=16;
    self.keyboard.layer.borderWidth=1; self.keyboard.layer.borderColor=FPStroke().CGColor;
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
            FPInputButton *b=[self button:label symbol:nil scan:scan];
            [self.buttons removeLastObject];
            b.standalone=YES; b.layer.cornerRadius=7;
            b.latch=[@[@"Shift",@"Ctrl",@"Alt",@"Cmd"] containsObject:label];
            if (label.length==1) b.text=label;
            if ([label isEqual:@"Space"]) b.text=@" ";
            [b refreshAppearance];
            [self.keyboard addSubview:b]; [buttons addObject:b];
        }
        [self.keyRows addObject:buttons];
    }
    [self addSubview:self.keyboard];
}
- (void)toggleControls {
    [self releaseInputs]; self.expanded=!self.expanded; self.autoHidden=NO;
    self.keyboard.hidden=YES;
    [self applyVisibility];
}
static CGFloat FPPillLength(NSUInteger count,CGFloat item,CGFloat pad) { return count*item+(count-1)*2+2*pad; }
// Lays out buttons in a pill with 2-point gaps; vertical pills stack top to bottom.
static CGRect FPLayoutPill(UIView *pill,NSArray<UIView *> *items,CGPoint origin,CGFloat item,CGFloat pad,BOOL vertical) {
    CGFloat length=FPPillLength(items.count,item,pad), thickness=item+2*pad;
    CGRect frame=vertical ? CGRectMake(origin.x,origin.y,thickness,length) : CGRectMake(origin.x,origin.y,length,thickness);
    pill.frame=frame; pill.layer.cornerRadius=thickness/2;
    for (NSUInteger i=0;i<items.count;i++) {
        CGFloat along=pad+i*(item+2);
        items[i].frame=vertical ? CGRectMake(frame.origin.x+pad,frame.origin.y+along,item,item)
                                : CGRectMake(frame.origin.x+along,frame.origin.y+pad,item,item);
        items[i].layer.cornerRadius=item/2;
    }
    return frame;
}
- (NSArray<UIView *> *)systemItems {
    return self.expanded ? @[self.modeButtons[0],self.modeButtons[1],self.modeButtons[2],self.keyboardToggle,self.toggle] : @[self.toggle];
}
- (CGFloat)systemWidthItem:(CGFloat)item pad:(CGFloat)pad divider:(CGFloat)divider {
    return FPPillLength(self.systemItems.count,item,pad)+(self.expanded ? divider : 0);
}
// System pill: input mode, keyboard and hide, with a divider after the modes.
- (CGRect)layoutSystemAt:(CGPoint)origin item:(CGFloat)item pad:(CGFloat)pad divider:(CGFloat)divider {
    NSArray<UIView *> *system=self.systemItems;
    CGRect pill=FPLayoutPill(self.systemPill,system,origin,item,pad,NO);
    if (!self.expanded) return pill;
    pill.size.width+=divider; self.systemPill.frame=pill;
    for (NSUInteger i=3;i<system.count;i++) system[i].frame=CGRectOffset(system[i].frame,divider,0);
    self.systemDivider.frame=CGRectMake(round(CGRectGetMaxX(self.modeButtons[2].frame)+1+divider/2-0.5),pill.origin.y+pad+item*0.2,1,item*0.6);
    return pill;
}
// Primary action at the corner point, secondary actions on two arcs around it. Returns the cluster's top.
- (CGFloat)layoutClusterAt:(CGPoint)c scale:(CGFloat)s {
    static const CGFloat ring[8][3]={{0,74,0},{96,54,180},{96,54,135},{96,54,90},{162,46,180},{162,46,150},{162,46,120},{162,46,90}};
    CGFloat top=c.y;
    for (NSUInteger i=0;i<self.cluster.count;i++) {
        CGFloat d=round(ring[i][1]*s), angle=ring[i][2]*M_PI/180;
        CGFloat x=c.x+cos(angle)*ring[i][0]*s, y=c.y-sin(angle)*ring[i][0]*s;
        FPInputButton *b=self.cluster[i];
        b.frame=CGRectMake(round(x-d/2),round(y-d/2),d,d); b.layer.cornerRadius=d/2;
        b.titleLabel.font=[UIFont systemFontOfSize:round((i==0 ? 11 : 9)*s) weight:UIFontWeightSemibold];
        [b setPreferredSymbolConfiguration:[UIImageSymbolConfiguration configurationWithPointSize:round((i==0 ? 24 : i<4 ? 18 : 15)*s) weight:UIImageSymbolWeightSemibold] forImageInState:UIControlStateNormal];
        top=MIN(top,CGRectGetMinY(b.frame));
    }
    return top;
}
- (void)layoutKeyboardIn:(CGRect)frame {
    self.keyboard.frame=frame;
    CGFloat rowHeight=(frame.size.height-12)/self.keyRows.count;
    for (NSUInteger row=0;row<self.keyRows.count;row++) {
        NSArray *keys=self.keyRows[row]; CGFloat keyWidth=(frame.size.width-12)/keys.count;
        for (NSUInteger col=0;col<keys.count;col++) ((UIView *)keys[col]).frame=CGRectMake(6+col*keyWidth+2,6+row*rowHeight+2,keyWidth-4,rowHeight-4);
    }
}
- (void)setGameReserve:(CGFloat)reserve {
    reserve=round(reserve);
    if (reserve==_gameReserve) return;
    _gameReserve=reserve; FPISetReservedBottom(reserve);
    // SDL recomputes its Metal view frame, and tells the game about the new size, on its next layout pass.
    dispatch_async(dispatch_get_main_queue(),^{
        UIView *game=self.window.rootViewController.view;
        [game setNeedsLayout]; [game layoutIfNeeded];
        [self.pointerSurface refreshCursor];
    });
}
- (void)layoutSubviews {
    [super layoutSubviews];
    if (!CGSizeEqualToSize(self.previousLayoutSize,CGSizeZero) &&
        !CGSizeEqualToSize(self.previousLayoutSize,self.bounds.size)) [self releaseInputs];
    self.previousLayoutSize=self.bounds.size;
    UIEdgeInsets insets=self.safeAreaInsets;
    // Use the current view, including its safe area, as it changes between displays.
    CGRect area=UIEdgeInsetsInsetRect(self.bounds,UIEdgeInsetsMake(MAX(insets.top,16),MAX(insets.left,16),
                                                               MAX(insets.bottom,16),MAX(insets.right,16)));
    CGFloat width=area.size.width, height=area.size.height;
    self.split=self.expanded && height>width*1.15;
    self.deck.hidden=!self.split;
    if (self.split) [self wake];
    CGFloat s=self.split ? MAX(0.7,MIN(1,width/420)) : MAX(0.7,MIN(1,MIN(width/390,height/560)));
    CGFloat item=round(40*s), pad=round(4*s), gap=round(10*s);
    UIImageSymbolConfiguration *symbol=[UIImageSymbolConfiguration configurationWithPointSize:round(17*s) weight:UIImageSymbolWeightSemibold];
    UIImageSymbolConfiguration *small=[UIImageSymbolConfiguration configurationWithPointSize:round(15*s) weight:UIImageSymbolWeightSemibold];
    for (UIButton *b in [self.modeButtons arrayByAddingObjectsFromArray:@[self.keyboardToggle,self.toggle]])
        [b setPreferredSymbolConfiguration:small forImageInState:UIControlStateNormal];
    for (FPInputButton *b in [self.menuRail arrayByAddingObjectsFromArray:self.zoomPair])
        [b setPreferredSymbolConfiguration:symbol forImageInState:UIControlStateNormal];
    for (FPInputButton *b in self.modifierPair) b.titleLabel.font=[UIFont systemFontOfSize:round(12*s) weight:UIFontWeightSemibold];
    self.modeHint.font=[UIFont systemFontOfSize:round(13*s) weight:UIFontWeightMedium];
    self.pointerSurface.frame=self.bounds;
    if (self.split) [self layoutDeckIn:area scale:s item:item pad:pad gap:gap];
    else [self layoutFloatingIn:area scale:s item:item pad:pad gap:gap];
    [self.joystick setNeedsDisplay];
    [self.pointerSurface refreshCursor];
}
// Landscape: controls float over the game, kept clear of Factorio's edge-aligned HUD.
- (void)layoutFloatingIn:(CGRect)area scale:(CGFloat)s item:(CGFloat)item pad:(CGFloat)pad gap:(CGFloat)gap {
    self.gameReserve=0;
    CGFloat width=area.size.width, height=area.size.height;
    // Right of centre in landscape to clear Factorio's top-left objective and research panels.
    CGFloat pillWidth=[self systemWidthItem:item pad:pad divider:round(9*s)];
    CGFloat centerX=width>height ? CGRectGetMinX(area)+width*0.62 : CGRectGetMidX(area);
    centerX=MIN(MAX(centerX,CGRectGetMinX(area)+pillWidth/2),CGRectGetMaxX(area)-pillWidth/2);
    CGRect pill=[self layoutSystemAt:CGPointMake(round(centerX-pillWidth/2),CGRectGetMinY(area)) item:item pad:pad divider:round(9*s)];
    CGFloat top=CGRectGetMaxY(pill)+gap;
    CGFloat hintWidth=MIN(400,width);
    self.modeHint.frame=CGRectMake(MIN(MAX(round(centerX-hintWidth/2),CGRectGetMinX(area)),CGRectGetMaxX(area)-hintWidth),top,hintWidth,round(46*s));

    // Left: stick raised clear of the character/gun panel, menu rail above it.
    CGFloat stick=round(130*s);
    CGFloat menuHeight=FPPillLength(self.menuRail.count,item,pad);
    CGFloat raise=MAX(0,MIN(round(96*s),CGRectGetMaxY(area)-top-menuHeight-gap-stick));
    self.joystick.frame=CGRectMake(CGRectGetMinX(area),CGRectGetMaxY(area)-raise-stick,stick,stick);
    CGFloat menuTop=MAX(top,CGRectGetMinY(self.joystick.frame)-gap-menuHeight);
    FPLayoutPill(self.menuPill,self.menuRail,CGPointMake(CGRectGetMinX(area),menuTop),item,pad,YES);

    // Right: thumb cluster in the corner; zoom and modifier pills just above it.
    CGFloat clusterTop=[self layoutClusterAt:CGPointMake(CGRectGetMaxX(area)-round(42*s),CGRectGetMaxY(area)-round(42*s)) scale:s];
    CGFloat rowY=clusterTop-gap-(item+2*pad);
    CGFloat modifierWidth=FPPillLength(self.modifierPair.count,item,pad);
    CGFloat zoomWidth=FPPillLength(self.zoomPair.count,item,pad);
    FPLayoutPill(self.modifierPill,self.modifierPair,CGPointMake(CGRectGetMaxX(area)-modifierWidth,rowY),item,pad,NO);
    FPLayoutPill(self.zoomPill,self.zoomPair,CGPointMake(CGRectGetMaxX(area)-modifierWidth-gap-zoomWidth,rowY),item,pad,NO);

    CGFloat keyboardWidth=MIN(900,width);
    [self layoutKeyboardIn:CGRectMake(CGRectGetMidX(area)-keyboardWidth/2,top,keyboardWidth,MIN(288,CGRectGetMaxY(area)-top))];
}
// Portrait: the game shrinks to the top of the screen and the controls sit on an opaque deck below it.
- (void)layoutDeckIn:(CGRect)area scale:(CGFloat)s item:(CGFloat)item pad:(CGFloat)pad gap:(CGFloat)gap {
    CGFloat width=area.size.width, row=item+2*pad, divider=round(9*s);
    CGFloat stick=round(140*s), clusterSize=round(227*s), band=MAX(stick,clusterSize);
    CGFloat zoomWidth=FPPillLength(self.zoomPair.count,item,pad);
    CGFloat modifierWidth=FPPillLength(self.modifierPair.count,item,pad);
    // Zoom and modifiers go between the stick and the cluster when they fit; otherwise they join the rows above.
    CGFloat middle=width-stick-clusterSize-2*gap;
    BOOL middleFits=middle>=MAX(zoomWidth,modifierWidth) && band>=2*row+gap;
    CGFloat widths[4]={[self systemWidthItem:item pad:pad divider:divider],FPPillLength(self.menuRail.count,item,pad),zoomWidth,modifierWidth};
    NSUInteger groups=middleFits ? 2 : 4, rowOf[4]={0}, rows=1;
    CGFloat used=0;
    for (NSUInteger i=0;i<groups;i++) {
        if (used>0 && used+gap+widths[i]>width) { rows++; used=0; }
        used+=(used>0 ? gap : 0)+widths[i]; rowOf[i]=rows-1;
    }
    CGFloat deckTop=CGRectGetMaxY(area)-rows*(row+gap)-band;
    for (NSUInteger r=0;r<rows;r++) {
        NSUInteger count=0; CGFloat total=0;
        for (NSUInteger i=0;i<groups;i++) if (rowOf[i]==r) { count++; total+=widths[i]; }
        CGFloat spacing=count>1 ? (width-total)/(count-1) : 0, x=CGRectGetMinX(area), y=deckTop+r*(row+gap);
        for (NSUInteger i=0;i<groups;i++) if (rowOf[i]==r) {
            CGPoint origin=CGPointMake(round(x),y);
            if (i==0) [self layoutSystemAt:origin item:item pad:pad divider:divider];
            if (i==1) FPLayoutPill(self.menuPill,self.menuRail,origin,item,pad,NO);
            if (i==2) FPLayoutPill(self.zoomPill,self.zoomPair,origin,item,pad,NO);
            if (i==3) FPLayoutPill(self.modifierPill,self.modifierPair,origin,item,pad,NO);
            x+=widths[i]+spacing;
        }
    }
    CGFloat bandTop=deckTop+rows*(row+gap);
    self.joystick.frame=CGRectMake(CGRectGetMinX(area),round(bandTop+(band-stick)/2),stick,stick);
    [self layoutClusterAt:CGPointMake(CGRectGetMaxX(area)-round(42*s),bandTop+band-round(42*s)) scale:s];
    if (middleFits) {
        CGFloat x=CGRectGetMinX(area)+stick+gap+middle/2, y=round(bandTop+(band-2*row-gap)/2);
        FPLayoutPill(self.zoomPill,self.zoomPair,CGPointMake(round(x-zoomWidth/2),y),item,pad,NO);
        FPLayoutPill(self.modifierPill,self.modifierPair,CGPointMake(round(x-modifierWidth/2),y+row+gap),item,pad,NO);
    }
    CGFloat edge=deckTop-gap;
    self.deck.frame=CGRectMake(-1,edge,self.bounds.size.width+2,self.bounds.size.height-edge+2);
    self.gameReserve=self.bounds.size.height-edge+round(6*s);
    CGFloat hintWidth=MIN(400,width), hintHeight=round(46*s);
    self.modeHint.frame=CGRectMake(round(CGRectGetMidX(area)-hintWidth/2),edge-round(6*s)-gap-hintHeight,hintWidth,hintHeight);
    // The keyboard takes over the deck below the system pill, so the game stays visible above it.
    CGFloat keyboardTop=deckTop+row+gap;
    [self layoutKeyboardIn:CGRectMake(CGRectGetMinX(area),keyboardTop,width,CGRectGetMaxY(area)-keyboardTop)];
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
