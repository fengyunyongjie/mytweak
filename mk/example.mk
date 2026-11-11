# Shared build intent. CPU slices are NOT Debian package architectures.
EXAMPLE_ROOTFUL_ARCHS ?= arm64
EXAMPLE_ROOTLESS_ARCHS ?= arm64 arm64e
EXAMPLE_ROOTFUL_DEPLOYMENT_TARGET ?= 12.0
EXAMPLE_ROOTLESS_DEPLOYMENT_TARGET ?= 15.0
EXAMPLE_SDK_VERSION ?= latest

# Theos has no "rootful" scheme: an empty value selects the normal layout.
ifeq ($(THEOS_PACKAGE_SCHEME),)
ARCHS ?= $(EXAMPLE_ROOTFUL_ARCHS)
EXAMPLE_DEPLOYMENT_TARGET ?= $(EXAMPLE_ROOTFUL_DEPLOYMENT_TARGET)
else ifeq ($(THEOS_PACKAGE_SCHEME),rootless)
ARCHS ?= $(EXAMPLE_ROOTLESS_ARCHS)
EXAMPLE_DEPLOYMENT_TARGET ?= $(EXAMPLE_ROOTLESS_DEPLOYMENT_TARGET)
else
$(error THEOS_PACKAGE_SCHEME must be empty or rootless)
endif

TARGET := iphone:clang:$(EXAMPLE_SDK_VERSION):$(EXAMPLE_DEPLOYMENT_TARGET)

# The helper queries the same defaults used by the staged Theos Makefile.
.PHONY: example-config
example-config:
	$(info ARCHS=$(ARCHS))
	$(info DEPLOYMENT_TARGET=$(EXAMPLE_DEPLOYMENT_TARGET))
	$(info SDK_VERSION=$(EXAMPLE_SDK_VERSION))
	@:
