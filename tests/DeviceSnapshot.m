#import <XCTest/XCTest.h>
#if __has_include("../build/ui-actions.h")
#include "../build/ui-actions.h"
#else
#define PROBE_ACTIONS @"[]"
#define PROBE_BUNDLE_ID @"local.factorio.loaderprobe"
#endif

@interface DeviceSnapshot : XCTestCase
@end

@implementation DeviceSnapshot
- (void)testCaptureInstalledApp {
    XCUIApplication *app=[[XCUIApplication alloc] initWithBundleIdentifier:PROBE_BUNDLE_ID];
    [app activate];
    XCTAssertEqual(app.state,XCUIApplicationStateRunningForeground);
    XCTAttachment *capture=[XCTAttachment attachmentWithScreenshot:app.screenshot];
    capture.name=@"Factorio on physical device";
    capture.lifetime=XCTAttachmentLifetimeKeepAlways;
    [self addAttachment:capture];
    NSArray *actions=[NSJSONSerialization JSONObjectWithData:[PROBE_ACTIONS dataUsingEncoding:NSUTF8StringEncoding] options:0 error:NULL];
    for (NSDictionary *action in actions) {
        if (action[@"button"]) {
            XCUIElement *button=app.buttons[action[@"button"]];
            XCTAssertTrue(button.exists);
            if (action[@"duration"]) [button pressForDuration:[action[@"duration"] doubleValue]];
            else [button tap];
        } else if (action[@"key"]) {
            NSDictionary *keys=@{@"Tab":XCUIKeyboardKeyTab,@"Escape":XCUIKeyboardKeyEscape,@"Return":XCUIKeyboardKeyReturn};
            [app typeKey:keys[action[@"key"]] ?: action[@"key"] modifierFlags:0];
        } else {
        XCUICoordinate *point=[app coordinateWithNormalizedOffset:CGVectorMake([action[@"x"] doubleValue],[action[@"y"] doubleValue])];
        if (action[@"duration"]) [point pressForDuration:[action[@"duration"] doubleValue]];
        else [point tap];
        }
        // SDL draws asynchronously and has no accessibility element changes
        // for XCTest's idle heuristic; allow the next rendered frames to land.
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.5]];
        XCTAttachment *after=[XCTAttachment attachmentWithScreenshot:app.screenshot];
        after.name=action[@"button"] ?: (action[@"key"] ? [@"After key " stringByAppendingString:action[@"key"]] : [NSString stringWithFormat:@"After touch %@,%@",action[@"x"],action[@"y"]]);
        after.lifetime=XCTAttachmentLifetimeKeepAlways;
        [self addAttachment:after];
        XCTAssertEqual(app.state,XCUIApplicationStateRunningForeground);
    }
}
@end
