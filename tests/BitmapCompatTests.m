#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ImageIO/ImageIO.h>
#include <assert.h>
#include <string.h>

@interface NSBitmapImageRep : NSObject
+ (instancetype)imageRepWithData:(NSData *)data;
- (unsigned char *)bitmapData;
- (NSInteger)pixelsWide;
- (NSInteger)pixelsHigh;
- (NSInteger)bitsPerPixel;
- (NSInteger)samplesPerPixel;
@end

static NSData *makePNG(void) {
    const unsigned char pixels[] = {255,0,0,255, 0,128,0,128};
    CFDataRef bytes = CFDataCreate(NULL,pixels,sizeof(pixels));
    CGDataProviderRef provider = CGDataProviderCreateWithCFData(bytes);
    CGColorSpaceRef space = CGColorSpaceCreateWithName(kCGColorSpaceSRGB);
    CGImageRef image = CGImageCreate(2,1,8,32,8,space,
        kCGImageAlphaPremultipliedLast|kCGBitmapByteOrder32Big,provider,NULL,false,kCGRenderingIntentDefault);
    NSMutableData *png = [NSMutableData data];
    CGImageDestinationRef destination = CGImageDestinationCreateWithData((__bridge CFMutableDataRef)png,CFSTR("public.png"),1,NULL);
    assert(image && destination);
    CGImageDestinationAddImage(destination,image,NULL);
    assert(CGImageDestinationFinalize(destination));
    CFRelease(destination);
    CGImageRelease(image);
    CGColorSpaceRelease(space);
    CGDataProviderRelease(provider);
    CFRelease(bytes);
    return png;
}

static void verifyPixels(NSBitmapImageRep *bitmap) {
    const unsigned char expected[] = {255,0,0,255, 0,255,0,128};
    assert(bitmap && bitmap.pixelsWide == 2 && bitmap.pixelsHigh == 1);
    assert(bitmap.bitsPerPixel == 32 && bitmap.samplesPerPixel == 4);
    assert(memcmp(bitmap.bitmapData,expected,sizeof(expected)) == 0);
}

int main(void) {
    @autoreleasepool {
        NSData *png = makePNG();
        NSBitmapImageRep *retained;
        @autoreleasepool { retained = [NSBitmapImageRep imageRepWithData:png]; }
        verifyPixels(retained);
        dispatch_apply(128,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^(size_t index) {
            verifyPixels([NSBitmapImageRep imageRepWithData:png]);
        });
        assert([NSBitmapImageRep imageRepWithData:[NSData data]] == nil);
        assert([NSBitmapImageRep imageRepWithData:[@"invalid PNG" dataUsingEncoding:NSUTF8StringEncoding]] == nil);
    }
    return 0;
}
