TARGET := iphone:clang:latest:11.0
INSTALL_TARGET_PROCESSES = SpringBoard

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = HelloTweak

HelloTweak_FILES = Tweak.x
HelloTweak_CFLAGS = -fobjc-arc
HelloTweak_FRAMEWORKS = UIKit Foundation

include $(THEOS_MAKE_PATH)/tweak.mk
