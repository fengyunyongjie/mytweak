# 兼容状态与设备验收

## 三种状态必须分开

1. **可收录**：仓库能够索引这种包架构，文件和哈希正确。
2. **构建通过**：特定源码、工具链、SDK 实际生成了对应二进制，并检查 control、路径、Mach-O 架构。
3. **设备通过**：特定设备/iOS/越狱环境上测试过安装、加载、功能、稳定性、升级与卸载。

不得用其中一项替代下一项。rootful/rootless 也不是 iOS 版本号的另一种写法；例如不能由“iOS 15”直接断言一定是 rootless。

## 当前正式包快照

以下来自仓库中真实 deb 的 control，表示当前检入的成品包，不是线上实时查询。

| 包 | 版本 | 已提供架构 | 本仓库源码 | 本次设备验证 |
|---|---|---|---|---|
| `com.fengyn.hellotweak` | `1.0.0-3` | `iphoneos-arm`、`iphoneos-arm64` | 有 | rootless APT 升降级通过、用户确认 🔥✨；rootful 未执行 |
| `com.fengyn.hellotweak` | `1.0.0-2` | `iphoneos-arm`、`iphoneos-arm64` | 有 | rootless 基本显示通过；rootful 未执行 |
| `com.yourcompany.ack` | `0.0.1-1000+stable20260515` | `iphoneos-arm` | 无 | 未执行 |
| `com.yourcompany.gck` | `0.0.1-1000+stable20260519` | `iphoneos-arm` | 无 | 未执行 |
| `com.yourcompany.sck` | `0.0.1-1003+stable20260610` | `iphoneos-arm` | 无 | 未执行 |

三个包依赖 `mobilesubstrate (>= 0.9.5000)`；Sck 还依赖 Ack 和 Gck。它们没有 firmware 最低版本声明，这不代表任意 iOS 版本都能运行。此改造不重写正式包，也不补猜测的兼容约束。

三个正式包的 rootless 构建尚未提供。应从各自源码构建，并验证路径、链接、注入框架和 ABI 后再收录。不要重命名现有包制造 `iphoneos-arm64` 版本。

## HelloTweak 示例

目标为单源码双构建：rootful iOS 12+、rootless iOS 15+。本次已用 Theos、Xcode 16.2 / clang 16.0.0 和 SDK 18.2 实际构建成功：rootful `arm64` 的 Mach-O 最低系统为 12.0；rootless `arm64 + arm64e` 两个 slice 的最低系统均为 15.0。control、包内路径及二进制检查通过；`1.0.0-2` 和 `1.0.0-3` 各两种包已保留在正式 `debs/`。

2026-11-12 在 iPad7,11 / iPadOS 18.7.12 rootless 设备上，`1.0.0-1` 已加载但未显示火焰。运行时证实旧 `timeString` 不存在，实际使用 StatusKit；升级现代适配版 `1.0.0-2` 后，**用户已目视确认主屏幕时间后出现 🔥**，安装、加载、基本显示和短时运行通过。rootful、其他设备及长期稳定性尚未实测。详见 [设备测试记录](device-test-2026-11-12.md)。

`1.0.0-3` 在同一设备完成正式源 APT 升级、显式降级、再次升级；用户最终确认显示 🔥✨。两版本均保留，详细证据和未签名源的临时信任处理见 [版本切换测试](hellotweak-version-testing.md)。中间降级后的图标未单独目视确认，rootful 仍未实测。

这些是**最低编译/安装目标和本地构建结果**，不是宣称覆盖所有后续 iOS。默认 CPU 与工具链限制见 [示例说明](../examples/HelloTweak/README.md)。

现代适配检查 `_UIStatusBarTimeItem` / `STUIStatusBarTimeItem` 与相应字符串视图的方法，按时间项所持有视图限定修改范围；旧 `SBStatusBarStateProvider -timeString` 仅作现代接口不可用时的回退。目标接口缺失时不启用对应 hook。类或方法存在仍不证明该版本实际走这条显示路径，需设备功能验证。

## 每次设备验证应记录

```text
Package / Version / Architecture:
SHA256:
源码位置 / revision:
Theos revision / 编译器 / SDK:
CPU slices / 最低系统:
设备型号 / iOS:
越狱与 bootstrap 版本 / rootful 或 rootless:
注入框架与兼容接口:
验证日期 / 执行者:
结果与日志位置:
```

## 验收清单

在自己有权限的测试设备中操作，先备份必要数据。构建和仓库测试不会自动安装到设备。

- 包管理器刷新源无缺失文件或哈希错误，能为该架构选择正确构建。
- 安装依赖全部可解析，没有把另一种 bootstrap 的框架强装进来。
- 读取安装清单，确认插件、资源和卸载脚本适配实际前缀。
- dylib CPU/ABI、最低系统和动态库链接与设备一致。
- 注入过滤范围正确；重启目标进程后插件正常加载，没有崩溃循环。
- HelloTweak：目标方法存在时原时间后追加一个符号；目标方法缺失时不启用；其他状态栏内容不变。
- 连续使用、锁屏解锁、语言/区域、时间格式变化下行为正确。
- 从既有版本升级，Package ID、偏好设置和依赖关系保持正确；用 Debian 版本比较确认会升级。
- 卸载/禁用后目标应用恢复原行为，不残留影响。

仓库自动测试只验证元数据和发布工程，不能确认私人插件内部逻辑、网络接口或安全性质。历史报告中的 HelloTweak 双模式记录也不能作为当前正式包的运行依据。
