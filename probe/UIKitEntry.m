#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <mach-o/dyld.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int (*MainFunction)(int, char **);
#if FACTORIO_SDL_MAJOR == 3
typedef int (*UIKitRunApp)(int, char **, MainFunction, void *);
#else
typedef int (*UIKitRunApp)(int, char **, MainFunction);
#endif
extern void PrepareMetalCompatibility(id<MTLDevice> device);
extern void InstallTouchControls(void);

int ProbeMain(int argc, char **argv) {
    MainFunction original = (MainFunction)((char *)_dyld_get_image_header(0) + ORIGINAL_MAIN_OFFSET);
    bool coreTest=argc==2 && !strcmp(argv[1],"--probe-core");
    bool benchmarkTest=argc==2 && !strcmp(argv[1],"--probe-benchmark");
    if (argc==1 || coreTest || benchmarkTest) {
        @autoreleasepool {
            NSString *root=[NSHomeDirectory() stringByAppendingPathComponent:@"Documents/Factorio"];
            NSString *user=[root stringByAppendingPathComponent:@"user"];
            NSString *data=[[[NSBundle mainBundle] bundlePath] stringByAppendingPathComponent:@"data"];
            NSError *error=nil;
            if (![[NSFileManager defaultManager] createDirectoryAtPath:user withIntermediateDirectories:YES attributes:nil error:&error]) {
                fprintf(stderr,"FACTORIO_PROBE: cannot create data directory: %s\n",error.description.UTF8String); return 1;
            }
            NSString *config=[root stringByAppendingPathComponent:@"config.ini"];
            NSString *text=[NSString stringWithFormat:@"[path]\nread-data=%@\nwrite-data=%@\n[general]\ncheck-updates=false\n[graphics]\ntexture-compression-level=none\ncompress-virtual-atlas=false\ngpu-accelerated-compression=false\ngpu-accelerated-mipmap-compression=false\nvideo-memory-usage=low\nmax-sprite-loading-threads=2\n",data,user];
            if ([[NSFileManager defaultManager] fileExistsAtPath:config]) {
                NSString *existing=[NSString stringWithContentsOfFile:config encoding:NSUTF8StringEncoding error:&error];
                if (!existing) { fprintf(stderr,"FACTORIO_PROBE: cannot read config: %s\n",error.description.UTF8String); return 1; }
                NSMutableArray<NSString *> *lines=[[existing componentsSeparatedByString:@"\n"] mutableCopy];
                BOOL inPaths=NO;
                for (NSUInteger i=0;i<lines.count;i++) {
                    NSString *line=[lines[i] stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceCharacterSet];
                    if ([line hasPrefix:@"["]) inPaths=[line isEqualToString:@"[path]"];
                    if (inPaths && [line hasPrefix:@"read-data="]) lines[i]=[@"read-data=" stringByAppendingString:data];
                    if (inPaths && [line hasPrefix:@"write-data="]) lines[i]=[@"write-data=" stringByAppendingString:user];
                }
                text=[lines componentsJoinedByString:@"\n"];
            }
            NSRegularExpression *crashSetting=[NSRegularExpression regularExpressionWithPattern:@"(?m)^;?\\s*enable-crash-log-uploading=.*$" options:0 error:NULL];
            if ([crashSetting numberOfMatchesInString:text options:0 range:NSMakeRange(0,text.length)]) {
                text=[crashSetting stringByReplacingMatchesInString:text options:0 range:NSMakeRange(0,text.length) withTemplate:@"enable-crash-log-uploading=false"];
            } else {
                text=[text stringByAppendingString:@"\n[other]\nenable-crash-log-uploading=false\n"];
            }
            if (![text writeToFile:config atomically:YES encoding:NSUTF8StringEncoding error:&error]) {
                fprintf(stderr,"FACTORIO_PROBE: cannot write config: %s\n",error.description.UTF8String); return 1;
            }
            NSMutableArray<NSString *> *arguments=[@[[NSString stringWithUTF8String:argv[0]],@"--config",config,@"--nogamepad"] mutableCopy];
            if (coreTest || benchmarkTest) [arguments addObject:@"--disable-audio"];
            if (coreTest) {
                NSString *settings=[root stringByAppendingPathComponent:@"map-gen-settings.json"];
                [@"{\"width\":64,\"height\":64,\"seed\":12345}" writeToFile:settings atomically:YES encoding:NSUTF8StringEncoding error:NULL];
                [arguments addObjectsFromArray:@[@"--create",[user stringByAppendingPathComponent:@"probe-map.zip"],@"--map-gen-settings",settings]];
            } else if (benchmarkTest) {
                [arguments addObjectsFromArray:@[@"--benchmark",[user stringByAppendingPathComponent:@"probe-map.zip"],@"--benchmark-ticks",@"120"]];
            } else {
                [arguments addObjectsFromArray:@[@"--force-metal",@"--graphics-quality",@"medium"]];
            }
            argc=(int)arguments.count;
            char **owned=calloc(argc+1,sizeof(char *));
            for (int i=0;i<argc;i++) owned[i]=strdup(arguments[i].UTF8String);
            argv=owned; // Process-lifetime storage; UIKit and the game retain argv.
        }
    }
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"--version") || !strcmp(argv[i],"--help") ||
            !strcmp(argv[i],"--create") || !strcmp(argv[i],"--benchmark") ||
            !strcmp(argv[i],"--generate-map-preview") || !strcmp(argv[i],"--test-scenario") ||
            !strcmp(argv[i],"--test-save")) return original(argc,argv);
    }
    @autoreleasepool {
        NSString *frameworks = [[NSBundle mainBundle] bundlePath];
#if FACTORIO_SDL_MAJOR == 3
        NSString *sdl = [frameworks stringByAppendingPathComponent:@"Frameworks/libSDL3.dylib"];
        const char *runSymbol="SDL_RunApp";
#else
        NSString *sdl = [frameworks stringByAppendingPathComponent:@"Frameworks/libSDL2.dylib"];
        const char *runSymbol="SDL_UIKitRunApp";
#endif
        void *handle = dlopen(sdl.fileSystemRepresentation, RTLD_NOW|RTLD_LOCAL);
        UIKitRunApp run = handle ? (UIKitRunApp)dlsym(handle,runSymbol) : NULL;
        if (!run) { fprintf(stderr,"FACTORIO_PROBE: SDL UIKit load failed: %s\n",dlerror()); return 1; }
        id<MTLDevice> device=MTLCreateSystemDefaultDevice();
        PrepareMetalCompatibility(device);
        fprintf(stderr,"FACTORIO_PROBE: Metal device=%s mac1=%d apple7=%d apple3=%d\n",
                device.name.UTF8String ?: "none", [device supportsFamily:MTLGPUFamilyMac1],
                [device supportsFamily:MTLGPUFamilyApple7],[device supportsFamily:MTLGPUFamilyApple3]);
        fprintf(stderr,"FACTORIO_PROBE: entering UIKit with original game main\n");
        InstallTouchControls();
#if FACTORIO_SDL_MAJOR == 3
        return run(argc,argv,original,NULL);
#else
        return run(argc,argv,original);
#endif
    }
}
