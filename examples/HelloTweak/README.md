# HelloTweak

简单的测试插件 - 在状态栏时间后面添加火焰图标 🔥

## 功能

在 iOS 状态栏的时间后面显示一个火焰表情符号

## 编译

### Rootless 版本
```bash
make clean
make package THEOS_PACKAGE_SCHEME=rootless
```

### Rootful 版本
```bash
make clean
make package THEOS_PACKAGE_SCHEME=rootful
```

## 安装

编译完成后，deb 包会在 `.theos/packages/` 目录下。

### 添加到插件源
```bash
# Rootless
cp .theos/packages/com.fengyn.hellotweak_*.rootless.*.deb ../../debs/rootless/

# Rootful
cp .theos/packages/com.fengyn.hellotweak_*.deb ../../debs/rootful/

# 推送到 GitHub
cd ../..
git add debs/
git commit -m "Add HelloTweak"
git push
```

## 兼容性

- iOS 15.0 - 18.x (Rootless)
- iOS 12.0 - 14.x (Rootful)
