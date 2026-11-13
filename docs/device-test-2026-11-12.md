# HelloTweak rootless 设备测试：2026-11-12

结论：**`1.0.0-1` 已加载但未显示火焰；定位旧 hook 缺失后升级到 `1.0.0-2`，用户已目视确认主屏幕时间后出现 🔥。该设备的安装、加载、基本显示功能与短时稳定性通过。** 不据此宣称所有 iPadOS 18 设备或长期稳定性均已验证。

## 环境与测试对象

- 设备：iPad7,11，CPU arm64（T8010）。
- 系统：iPadOS 18.7.12，build 22H390。
- 包管理器架构：`iphoneos-arm64`，`/var/jb` 指向 preboot 中的 Procursus bootstrap。
- 环境存在 `/dev/rmd0` 和 `/cores/binpack/usr/lib/systemhook.dylib`，与 checkra1n/palera1n 系列布局相符；未独立确认越狱工具的具体版本。
- 插件：`com.fengyn.hellotweak`，版本 `1.0.0-1`，`iphoneos-arm64`。
- 对应旧版本本地构建：`.build/examples/hellotweak-amcj2at0/rootless/`；这是修复前 `1.0.0-1` 的源码，修复后的构建为 `.build/examples/hellotweak-sh4ca_fh/rootless/`。
- 本地 deb SHA256：`ce0ac6405d0d125936d5db42f620e6834c21be1d2a2a7aa472339104e495e390`。
- 设备已安装 dylib 与该包内 dylib 的 SHA256 均为 `5a171779134c87e71939586a39de6342551d2dfc6e4e8382b5d54f82d539aac1`。设备最初已有解包文件，本次没有重新上传或替换插件包；不声称设备安装数据库保存了原 deb 的完整哈希。

## 操作与结果

1. SSH 只读检查发现 HelloTweak 为 `install ok unpacked`，缺少提供 `mobilesubstrate` 接口的注入框架。
2. APT 模拟显示只需新增 ElleKit 1.2，不升级、删除其他包。
3. 经用户明确确认后，执行 `apt-get --yes --no-remove --no-upgrade install ellekit=1.2`。从设备已配置的官方 ElleKit 源安装成功，并自动完成 HelloTweak 配置。
4. `dpkg-query` 确认 ElleKit 和 HelloTweak 都为 `install ok installed`。ElleKit 提供 `mobilesubstrate (= 99)`，满足现有版本依赖，未强制忽略依赖。
5. 经用户确认的 `sbreload` 成功执行。SpringBoard PID 从 35 变为 3013；后续约三分钟观察中 PID 不变，未发现新的 SpringBoard 崩溃报告。
6. ElleKit 将兼容路径 `Library/MobileSubstrate/DynamicLibraries` 链接至 `usr/lib/TweakInject`。HelloTweak 的 dylib 和 plist 都位于实际注入目录。
7. 使用临时 arm64 命令行工具，仅通过 `proc_pidinfo(PROC_PIDREGIONINFO)` 与 `proc_regionfilename` 查询 SpringBoard 的文件映射，无调试附加、目标内存写入或进程注入。698 个区域中明确找到 `usr/lib/TweakInject/HelloTweak.dylib` 的映射，输出 `HelloTweak_mapped=yes`；也找到 systemhook、ElleKit 和 MobileSafety 映射。
8. 临时诊断工具和设备临时目录已移除。HelloTweak、ElleKit 保持安装，未改正式仓库包或发布线上源。

## 旧版本未显示的定位与适配

用户确认 `1.0.0-1` 未显示火焰后，使用只匹配 SpringBoard 的临时诊断模块在主线程读取状态栏类、方法及状态栏视图类型。诊断证实：

- `SBStatusBarStateProvider` 类存在，但没有 `timeString`，原守卫正确跳过了旧 hook。这是旧实现不生效的已确认原因。
- 设备实际使用 `STUIStatusBar` / `STUIStatusBarStringView`；后者继承 UILabel。
- `STUIStatusBarTimeItem` 有 `timeView`、`shortTimeView`、`pillTimeView`、对应 setter 和 `applyUpdate:toDisplayItem:`（运行时返回类型为对象）。UIKit 前缀对应接口也存在。

修复版 `1.0.0-2` 使用两个独立的现代分组，标记时间项持有的文本视图，再仅对有标记的 string view 追加符号；不标记 `dateView`，不按全局文本匹配时间，保留 nil/空值并避免重复追加。旧 hook 仅在现代接口不可用时回退。所有入口保留方法存在性检查。

两模式 release 构建通过，rootless 包已通过正常 `dpkg -i` 从 `1.0.0-1` 升级到 `1.0.0-2`，状态为 `install ok installed`。本地 deb SHA256 为 `d2a0e63dbcf1a5bd3abb6f551b3521886cbb594829d1c7780936913ce127aeac`；设备 dylib SHA256 为 `d3dd59f88802e3de23d984f26f78eb2d61e1c186a40a8dcc3fd353d9e7bda536`。

修复后的自动采样只看到了电量/充电状态文字，没有可见时间视图；随后用户在主屏幕目视确认时间后出现 🔥。因此基本显示功能标为通过，证据来源为用户确认，未取得截图。

临时诊断模块、plist、设备报告与上传 deb 已删除，原始诊断结果保留在本地忽略目录 `.build/device-tests/2026-11-12-ipad/`。最后一次 `sbreload` 输出过 `Requestor lacks required entitlement` 警告；后续确认 SpringBoard PID 已变为 3519、运行正常，设备上诊断文件不存在。未为此添加特权或调整系统安全配置。完整本地回归 95 项通过。

## 未覆盖

- 未取得屏幕截图；主屏幕火焰显示由用户目视确认。电脑可识别连接的同型号/系统 iPad，但 `idevicescreenshot` 返回 `Could not start screenshotr service: Invalid service`；未为此挂载 Developer Disk Image 或修改设备开发者环境。
- 临时模块仅核对了类/方法与视图，未调用目标更新方法来制造显示证据；最终功能结论依据用户对修复版的实际观察。
- 未验证多次锁屏/解锁、区域与语言变化、分钟更新后是否持续正确、长期运行、禁用/卸载恢复或包管理器源下载安装流程。已验证一次本地 deb 升级，不等于完整升级矩阵通过。
- 未测试 rootful 设备，也未扩展旧 arm64e ABI 的支持承诺。

本次 rootless 基本功能验收在上述特定设备环境通过；未覆盖项目保留为后续测试。
