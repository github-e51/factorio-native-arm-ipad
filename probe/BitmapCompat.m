#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ImageIO/ImageIO.h>

@interface NSColorSpace : NSObject
+ (instancetype)sRGBColorSpace;
+ (instancetype)genericRGBColorSpace;
@end
@implementation NSColorSpace
+ (instancetype)sRGBColorSpace {
    static NSColorSpace *space; static dispatch_once_t once;
    dispatch_once(&once, ^{ space = [NSColorSpace new]; }); return space;
}
+ (instancetype)genericRGBColorSpace { return [self sRGBColorSpace]; }
@end

// The original loader reads tightly packed, unpremultiplied RGBA8 and performs
// its own optional premultiplication. ImageIO handles PNG decoding; CGContext
// converts color profiles to sRGB. Undo CGContext's premultiplication below.
@interface NSBitmapImageRep : NSObject
@property(nonatomic,strong) NSMutableData *pixels;
@property(nonatomic) NSInteger width;
@property(nonatomic) NSInteger height;
@end
@implementation NSBitmapImageRep
+ (instancetype)imageRepWithData:(NSData *)data {
    // The game's preload workers are long-lived. Release ImageIO/Foundation
    // temporary objects after each image instead of after the whole atlas load.
    @autoreleasepool {
        NSDictionary *options=@{(__bridge NSString *)kCGImageSourceShouldCache:@NO};
        CGImageSourceRef source = CGImageSourceCreateWithData((__bridge CFDataRef)data,(__bridge CFDictionaryRef)options);
        if (!source) return nil;
        CGImageRef image = CGImageSourceCreateImageAtIndex(source,0,(__bridge CFDictionaryRef)options);
        CFRelease(source);
        if (!image) return nil;
        size_t width=CGImageGetWidth(image),height=CGImageGetHeight(image);
        if (!width || !height || width>SIZE_MAX/4/height) { CGImageRelease(image); return nil; }
        NSBitmapImageRep *result = [self new];
        result.width=width; result.height=height;
        result.pixels=[NSMutableData dataWithLength:width*height*4];
        CGColorSpaceRef space=CGColorSpaceCreateWithName(kCGColorSpaceSRGB);
        CGContextRef context=CGBitmapContextCreate(result.pixels.mutableBytes,width,height,8,width*4,space,
                                                   kCGImageAlphaPremultipliedLast|kCGBitmapByteOrder32Big);
        CGColorSpaceRelease(space);
        if (!context) { CGImageRelease(image); return nil; }
        CGContextDrawImage(context,CGRectMake(0,0,width,height),image);
        CGContextRelease(context); CGImageRelease(image);
        uint8_t *p=result.pixels.mutableBytes;
        for (size_t i=0;i<width*height;i++,p+=4) {
            unsigned a=p[3];
            if (a && a<255) for (int c=0;c<3;c++) p[c]=(uint8_t)MIN(255,(p[c]*255u+a/2)/a);
        }
        return result;
    }
}
- (unsigned char *)bitmapData { return self.pixels.mutableBytes; }
- (NSInteger)pixelsWide { return self.width; }
- (NSInteger)pixelsHigh { return self.height; }
- (NSInteger)bitsPerPixel { return 32; }
- (NSInteger)samplesPerPixel { return 4; }
- (NSColorSpace *)colorSpace { return [NSColorSpace sRGBColorSpace]; }
- (instancetype)bitmapImageRepByRetaggingWithColorSpace:(NSColorSpace *)space { return self; }
- (instancetype)bitmapImageRepByConvertingToColorSpace:(NSColorSpace *)space renderingIntent:(NSInteger)intent { return self; }
@end
