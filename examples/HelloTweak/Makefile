# The helper creates a fresh source copy, control and example.mk per scheme.
# Refuse in-tree make (including clean) rather than touching shared build data.
ifneq ($(EXAMPLE_STAGED_BUILD),1)
$(error Build with ../compile.sh --scheme both; see ../compile.sh --help)
endif

.DEFAULT_GOAL := all
include example.mk
include $(THEOS)/makefiles/common.mk

TWEAK_NAME = HelloTweak
HelloTweak_FILES = Tweak.x
HelloTweak_CFLAGS = -fobjc-arc
HelloTweak_FRAMEWORKS = Foundation

include $(THEOS_MAKE_PATH)/tweak.mk

.PHONY: example-build-info
example-build-info:
	$(info THEOS=$(THEOS))
	$(info THEOS_PACKAGE_SCHEME=$(THEOS_PACKAGE_SCHEME))
	$(info TARGET=$(TARGET))
	$(info ARCHS=$(ARCHS))
	$(info DEPLOYMENT_TARGET=$(_THEOS_TARGET_OS_DEPLOYMENT_VERSION))
	$(info SYSROOT=$(SYSROOT))
	$(info ISYSROOT=$(ISYSROOT))
	$(info TARGET_CXX=$(TARGET_CXX))
	$(info TARGET_LD=$(TARGET_LD))
	$(info TARGET_CODESIGN=$(TARGET_CODESIGN))
	@$(TARGET_CXX) --version
