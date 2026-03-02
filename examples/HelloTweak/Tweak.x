%hook SBStatusBarStateProvider

- (NSString *)timeString {
    NSString *original = %orig;
    return [original stringByAppendingString:@" 🔥"];
}

%end

%hook SBStatusBarContentView

- (void)setDate:(id)date {
    %orig;
}

%end
