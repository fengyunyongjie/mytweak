# Debian control 模板

这是说明文档，不是可发布的 deb。生成器只收录 `*.deb`，不会把这份模板复制到发布目录。接入规则统一见 [添加插件](../docs/adding-packages.md)。

## rootful 独立构建

```control
Package: com.example.tweak
Name: Example Tweak
Version: 1.0.0-1
Architecture: iphoneos-arm
Description: 插件的一行描述
Maintainer: Maintainer <maintainer@example.invalid>
Section: Tweaks
Depends: mobilesubstrate (>= 0.9.5000), firmware (>= 12.0)
```

## rootless 独立构建

```control
Package: com.example.tweak
Name: Example Tweak
Version: 1.0.0-1
Architecture: iphoneos-arm64
Description: 插件的一行描述
Maintainer: Maintainer <maintainer@example.invalid>
Section: Tweaks
Depends: mobilesubstrate (>= 0.9.5000), firmware (>= 15.0)
```

两个模式可沿用同一 Package ID、Version；需要分别编译。上述 firmware 和框架依赖是示例，不是所有插件的通用结论。务必与真实 deployment target、私有 API 和目标框架兼容接口一致。

**不要放入 control 的字段**：`Filename`、`Size`、`MD5sum`、`SHA1`、`SHA256`。它们由索引生成器从实际产物计算。

## Theos

```bash
# rootful：空 scheme，不能写 THEOS_PACKAGE_SCHEME=rootful
make package FINALPACKAGE=1 THEOS_PACKAGE_SCHEME=

# rootless：官方 scheme 处理包架构、安装前缀和链接搜索路径
make package FINALPACKAGE=1 THEOS_PACKAGE_SCHEME=rootless
```

两次构建需要隔离工作目录，并同步最低 iOS 的控制字段。不要直接复制模板两遍再依赖文件名判断模式。本仓库提供带隔离和产物检查的 [HelloTweak 构建入口](../examples/HelloTweak/README.md)：

```bash
THEOS=/opt/theos bash examples/compile.sh --scheme both
```

默认 deb 文件名包含 `Package_Version_Architecture`，通常没有 `.rootless.` 标记。正确性依据是 control 与二进制内容，不是文件名。
