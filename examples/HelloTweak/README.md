# HelloTweak

同一份 Logos 源码构建 rootful / rootless 示例包。`timeString` 返回原字符串后追加一个空格和火焰图标；原返回值为 `nil` 时仍为 `nil`。只在初始化时确认 `SBStatusBarStateProvider` 类和 `timeString` 实例方法都存在后启用 hook，否则不启用。已移除没有行为的 `setDate:` 透传 hook。

## 构建

从仓库根目录运行（脚本也可从其他工作目录调用）

```bash
./examples/compile.sh --help
./examples/compile.sh                         # 默认 --scheme both
./examples/compile.sh --scheme rootful
THEOS=/opt/theos ./examples/compile.sh --scheme rootless
./examples/compile.sh --version 1.0.1-1 --sdk 16.5
./examples/compile.sh --rootful-archs arm64 --rootless-archs 'arm64 arm64e'
```

需要已有 Python 3.9+、GNU make、`dpkg-deb` 及完整 Theos/编译器/iOS SDK/签名工具；脚本不安装任何依赖、不连接设备。优先使用显式环境变量 `THEOS`，未设置时依次检查 `~/theos`、`/opt/theos`、`/usr/local/theos`、`/opt/homebrew/theos`，验证必需文件。显式 `THEOS` 无效或为空会报错，不偷偷回退；构建错误直接返回非零状态，保留日志。

共享默认值位于 `mk/example.mk`，不是一套额外运行时。

| 模式 | Theos scheme | Debian `Architecture` | 默认 Mach-O CPU slices | 最低 iOS / firmware | 包内路径前缀 |
| --- | --- | --- | --- | --- | --- |
| rootful | 空字符串 | `iphoneos-arm` | `arm64` | `12.0` | `/` |
| rootless | 官方 `rootless` | `iphoneos-arm64` | `arm64 arm64e` | `15.0` | `/var/jb` |

`iphoneos-arm` / `iphoneos-arm64` 是包管理器的架构名称，**不等于** Mach-O CPU slice。rootful 实际传 `THEOS_PACKAGE_SCHEME=`，不是 `THEOS_PACKAGE_SCHEME=rootful`。rootless 的安装前缀和链接路径由 Theos 官方模块处理。

- `--rootful-archs` / `--rootless-archs` 配置 CPU slices，支持引号内空格或逗号分隔。
- `--rootful-min-ios` / `--rootless-min-ios` 同时配置编译最低系统和生成 control 的 `firmware` 下限；不能低于本示例的 12.0 / 15.0。
- `--sdk` 是编译 SDK 版本，默认为 Theos 可见的 `latest`，不代表最低系统。可固定版本复现构建。
- 默认 rootful **不声称覆盖 iOS 12/13 的 arm64e 设备**。现代 clang 不支持该旧 ABI；脚本拒绝 `arm64e` + 低于 14.0 的最低系统组合。需要现代 arm64e rootful 时显式传 `--rootful-archs 'arm64 arm64e' --rootful-min-ios 14.0`。旧 ABI 必须另行验证旧工具链。
- 始终使用 `FINALPACKAGE=1`，默认版本取源码 control 的 `1.0.0-1`，可用 `--version` 或环境变量 `PACKAGE_VERSION` 覆盖。两个模式复用相同版本，以不同 Debian 架构区分，不附加 `.rootless` 或调试编号，也不修改源码版本。
- 两模式依赖均为 `mobilesubstrate (>= 0.9.5000)` 加对应的 `firmware` 下限。此为兼容 hook API 的依赖，不断言所有 rootless 环境必须使用 ElleKit。

## 隔离输出与核验

每次构建新建 `.build/examples/hellotweak-<唯一值>/<scheme>/`，其中

- `source/` 是仅包含构建必需源码及配置的自身副本；只在这里生成当前模式的 control，不修改源码 control。
- `.theos/`、`staging/`、`packages/` 分别存放构建数据、打包目录及 deb。
- `build.log` 记录完整命令、实际编译器、SDK、deployment target 和错误。

不执行 `make clean`，不覆盖上次输出。为避免混用源码控制文件和共享 `.theos`，源码目录直接 `make`（包括 `make clean`）会提示使用包装脚本。每个包只含相应前缀下的 `Library/MobileSubstrate/DynamicLibraries/HelloTweak.dylib` 和 `HelloTweak.plist`。

脚本使用 `dpkg-deb --field` 核验 Package / Version / Architecture / Depends，以 `--fsys-tarfile` 在内存读取载荷目录核验前缀；**不靠文件名中的 `.rootless.` 判断、不解包到文件系统、不执行 maintainer scripts**。结束时打印已核验 deb 的绝对路径。

产物不会自动复制到正式 `debs/`，也不会安装、提交或发布。确认包及设备兼容性后，再单独按仓库发布流程处理。

## 测试与实测边界

```bash
python3 -I tests/test_example.py -v
```

相关单元/静态测试覆盖参数、Theos 发现与错误回退、版本/依赖生成、隔离目录、空 rootful scheme、包内容识别及 hook 初始化守卫；不依赖 Theos / Xcode，不代表真机测试。

本机实际完成默认双模式 release 构建并核验：Theos `/opt/theos`（`13c2237`）、Xcode 16.2（16C5032a）、Apple clang 16.0.0、iPhoneOS 18.2 SDK、GNU Make 3.81、`ldid`。`lipo` / `vtool` 显示 rootful 为 `arm64`、minos 12.0；rootless 为 `arm64 arm64e`，两 slice 均 minos 15.0，SDK 均为 18.2。包元数据依赖和前缀与表格一致。Theos 提示未并行构建，链接器提示旧 `-multiply_defined` 参数，均未阻塞构建。

**未连接设备、未安装包、未验证 SpringBoard 私有 API 在任何具体 iOS 版本存在或显示效果。** iOS 12+ / 15+ 是编译及包元数据的目标意图，不是所有版本/设备的兼容性承诺；不存在目标类或 selector 时插件保持未启用。
