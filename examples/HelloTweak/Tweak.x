#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>

static char HelloTweakTimeViewKey;

static NSString *HelloTweakDecoratedTime(NSString *text) {
    if (text.length == 0 || [text hasSuffix:@" 🔥✨"]) return text;
    if ([text hasSuffix:@" 🔥"]) return [text stringByAppendingString:@"✨"];
    return [text stringByAppendingString:@" 🔥✨"];
}

static void HelloTweakMarkTimeView(UILabel *view) {
    if (![view isKindOfClass:UILabel.class]) return;
    objc_setAssociatedObject(view, &HelloTweakTimeViewKey, @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    NSString *text = view.text;
    NSString *decorated = HelloTweakDecoratedTime(text);
    if (![text isEqualToString:decorated]) view.text = decorated;
}

static void HelloTweakMarkItemViews(id item) {
    for (NSString *name in @[@"timeView", @"shortTimeView", @"pillTimeView"]) {
        SEL selector = NSSelectorFromString(name);
        if ([item respondsToSelector:selector]) {
            UILabel *(*getter)(id, SEL) = (UILabel *(*)(id, SEL))[item methodForSelector:selector];
            HelloTweakMarkTimeView(getter(item, selector));
        }
    }
}

%group LegacyTime
%hook SBStatusBarStateProvider
- (NSString *)timeString {
    return HelloTweakDecoratedTime(%orig);
}
%end
%end

%group UIKitTime
%hook _UIStatusBarTimeItem
- (void)setTimeView:(UILabel *)view {
    HelloTweakMarkTimeView(view);
    %orig;
}
- (void)setShortTimeView:(UILabel *)view {
    HelloTweakMarkTimeView(view);
    %orig;
}
- (void)setPillTimeView:(UILabel *)view {
    HelloTweakMarkTimeView(view);
    %orig;
}
- (id)applyUpdate:(id)update toDisplayItem:(id)displayItem {
    HelloTweakMarkItemViews(self);
    id result = %orig;
    HelloTweakMarkItemViews(self);
    return result;
}
%end
%end

%group StatusKitTime
%hook STUIStatusBarTimeItem
- (void)setTimeView:(UILabel *)view {
    HelloTweakMarkTimeView(view);
    %orig;
}
- (void)setShortTimeView:(UILabel *)view {
    HelloTweakMarkTimeView(view);
    %orig;
}
- (void)setPillTimeView:(UILabel *)view {
    HelloTweakMarkTimeView(view);
    %orig;
}
- (id)applyUpdate:(id)update toDisplayItem:(id)displayItem {
    HelloTweakMarkItemViews(self);
    id result = %orig;
    HelloTweakMarkItemViews(self);
    return result;
}
%end
%end

%group UIKitString
%hook _UIStatusBarStringView
- (void)setText:(NSString *)text {
    if ([objc_getAssociatedObject(self, &HelloTweakTimeViewKey) boolValue]) {
        text = HelloTweakDecoratedTime(text);
    }
    %orig(text);
}
%end
%end

%group StatusKitString
%hook STUIStatusBarStringView
- (void)setText:(NSString *)text {
    if ([objc_getAssociatedObject(self, &HelloTweakTimeViewKey) boolValue]) {
        text = HelloTweakDecoratedTime(text);
    }
    %orig(text);
}
%end
%end

static BOOL HelloTweakHasMethod(Class cls, SEL selector) {
    return cls != Nil && class_getInstanceMethod(cls, selector) != NULL;
}

static BOOL HelloTweakSupportsTimeItem(Class cls) {
    return HelloTweakHasMethod(cls, @selector(applyUpdate:toDisplayItem:)) &&
        HelloTweakHasMethod(cls, @selector(setTimeView:)) &&
        HelloTweakHasMethod(cls, @selector(setShortTimeView:)) &&
        HelloTweakHasMethod(cls, @selector(setPillTimeView:));
}

%ctor {
    @autoreleasepool {
        Class uiItem = objc_getClass("_UIStatusBarTimeItem");
        Class stItem = objc_getClass("STUIStatusBarTimeItem");
        Class uiString = objc_getClass("_UIStatusBarStringView");
        Class stString = objc_getClass("STUIStatusBarStringView");
        BOOL uiSupported = HelloTweakSupportsTimeItem(uiItem) && HelloTweakHasMethod(uiString, @selector(setText:));
        BOOL stSupported = HelloTweakSupportsTimeItem(stItem) && HelloTweakHasMethod(stString, @selector(setText:));
        if (uiSupported) {
            %init(UIKitString);
            %init(UIKitTime);
        }
        if (stSupported) {
            %init(StatusKitString);
            %init(StatusKitTime);
        }
        if (!uiSupported && !stSupported) {
            Class provider = objc_getClass("SBStatusBarStateProvider");
            if (HelloTweakHasMethod(provider, @selector(timeString))) {
                %init(LegacyTime);
            }
        }
    }
}
