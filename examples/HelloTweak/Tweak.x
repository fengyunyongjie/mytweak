#import <Foundation/Foundation.h>
#import <objc/runtime.h>

%group HelloTweakHooks
%hook SBStatusBarStateProvider

- (NSString *)timeString {
    NSString *original = %orig;
    return [original stringByAppendingString:@" 🔥"];
}

%end
%end

%ctor {
    @autoreleasepool {
        Class provider = objc_getClass("SBStatusBarStateProvider");
        if (provider != Nil && class_getInstanceMethod(provider, @selector(timeString)) != NULL) {
            %init(HelloTweakHooks, SBStatusBarStateProvider = provider);
        }
    }
}
