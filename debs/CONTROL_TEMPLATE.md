# Debian 控制文件模板

## Rootless 插件控制文件模板

```control
Package: com.yourname.tweakname
Name: Your Tweak Name
Version: 1.0.0-1
Architecture: iphoneos-arm64
Description: 简短描述 (一行)
 长描述，可以写多行。
 详细介绍插件功能。
Maintainer: Your Name <your@email.com>
Author: Your Name
Section: Tweaks
Depends: mobilesubstrate (>= 0.9.5000), firmware (>= 15.0)
Filename: ./debs/rootless/com.yourname.tweakname_1.0.0-1_iphoneos-arm64.deb
Size: <文件大小>
MD5sum: <MD5值>
SHA1: <SHA1值>
SHA256: <SHA256值>
```

## Rootful 插件控制文件模板

```control
Package: com.yourname.tweakname
Name: Your Tweak Name
Version: 1.0.0-1
Architecture: iphoneos-arm64
Description: 简短描述
 长描述，可以写多行。
Maintainer: Your Name <your@email.com>
Author: Your Name
Section: Tweaks
Depends: mobilesubstrate (>= 0.9.5000), firmware (>= 12.0)
Filename: ./debs/rootful/com.yourname.tweakname_1.0.0-1_iphoneos-arm64.deb
Size: <文件大小>
MD5sum: <MD5值>
SHA1: <SHA1值>
SHA256: <SHA256值>
```

## Makefile 示例

```makefile
TARGET := iphone:clang:latest:15.0
INSTALL_TARGET_PROCESSES = SpringBoard

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = YourTweak

YourTweak_FILES = Tweak.x
YourTweak_CFLAGS = -fobjc-arc
YourTweak_FRAMEWORKS = UIKit Foundation

include $(THEOS_MAKE_PATH)/tweak.mk
```

## 编译命令

### Rootless
```bash
make clean
make package THEOS_PACKAGE_SCHEME=rootless
```

### Rootful
```bash
make clean
make package THEOS_PACKAGE_SCHEME=rootful
```
