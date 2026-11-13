# HelloTweak 1.0.0-3 升级与降级测试

日期：2026-11-12。环境：iPad7,11 / iPadOS 18.7.12，rootless `iphoneos-arm64`，ElleKit 1.2。

## 版本差异与正式源

- `1.0.0-2`：时间后显示 🔥，保留原始两架构包。
- `1.0.0-3`：时间后显示 🔥✨，保留相同 Package ID、架构与依赖。空值保持原样，旧火焰后缀转换为新后缀，重复更新不继续追加。
- 两个版本均提供 rootful `iphoneos-arm`、rootless `iphoneos-arm64`。rootful 仅构建验证，未做设备测试。
- 正式源：<https://fengyunyongjie.github.io/mytweak/>。
- 发布提交：`d04343cf7f152fd1502b8ca223f1dacd643202d2`。
- 源中共 7 个构建，包含 HelloTweak 两版本共 4 个包以及原有 Ack/Gck/Sck。旧包字节与 SHA256 保持不变。

新包 SHA256：

| 架构 | SHA256 |
|---|---|
| `iphoneos-arm` | `e975b45b620d8d177c5f03dd18420db766e32c3f13d431ef42781d677af8e20a` |
| `iphoneos-arm64` | `f5a6ebfc7df4b103c32d93f60d5f682678de11917c0b7d7e4cc75ae94aa2a4a4` |

本地两模式实际构建和 95 项回归测试通过。线上全部索引、压缩文件、Release、首页及 7 个 deb 均返回 HTTP 200，逐字节与本地发布产物一致，下载后的隔离副本通过完整仓库校验。

## APT 测试结果

先模拟每次安装，只允许 HelloTweak 的 Inst/Conf；实际操作没有升级、安装或移除其他包。通过 APT 精确版本选择测试，未上传 deb 或用本地 `dpkg -i` 替代源下载。

| 步骤 | 版本变化 | APT/安装结果 | 载荷校验 | 显示证据 |
|---|---|---|---|---|
| 初始 | `1.0.0-2` | 已安装 | 旧版 | 之前用户确认 🔥 |
| 升级 | `1.0.0-2 → 1.0.0-3` | 正式源下载 5598 B，安装成功 | 新版 dylib SHA256 匹配 | 中间阶段未单独目视确认 |
| 显式降级 | `1.0.0-3 → 1.0.0-2` | 使用 `--allow-downgrades`，正式源下载 5572 B，安装成功 | 恢复旧版 dylib SHA256 | 中间阶段未单独目视确认 |
| 再升级 | `1.0.0-2 → 1.0.0-3` | 复用 APT 已校验缓存，安装成功 | 新版 dylib SHA256 匹配 | 用户最终确认显示 🔥✨ |

旧版 dylib SHA256：`d3dd59f88802e3de23d984f26f78eb2d61e1c186a40a8dcc3fd353d9e7bda536`。
新版 dylib SHA256：`0599050f4809147ee217e94170e505f21827a63054eef23114ae56ae53e9ea82`。

每步 `dpkg-query` 均显示对应版本、`iphoneos-arm64`、`install ok installed`。最终 `apt-cache policy` 的 Installed/Candidate 均为 `1.0.0-3`，旧 `1.0.0-2` 仍在正式源版本列表中。

每步均调用 `sbreload`；该命令输出过 `Requestor lacks required entitlement` 警告，不能只凭退出码断言重载。后续实际确认 SpringBoard PID 依次为 5126、5216、5306，最终进程持续运行，未发现新增 SpringBoard 崩溃报告。

## 签名与配置边界

正式源尚无 APT 签名。首次默认信任策略下仅刷新该源失败，报 `Release is not signed`。测试在独立临时 `.sources` 文件中仅为这个明确指定源设置 `Trusted: yes`，保持 HTTPS 和已核对的线上索引/包哈希；安装也仅使用此临时源配置。没有关闭全局签名校验，没有修改设备原有 Sileo 源配置。临时源文件和目录已删除。

这只是受控测试的单源信任处理，不替代源签名。普通客户端仍遵循其自身对未签名源的策略。

## 未覆盖与复测命令

未操作 Sileo 的图形界面，不声称其旧版本选择 UI 已验证。未逐步观察中间升级和降级后的图标，未验证长期运行、全部布局、其他系统或 rootful 实机。

客户端刷新并信任该源后，可精确指定版本（先去掉 `-s` 前确认模拟计划）：

```bash
apt-cache policy com.fengyn.hellotweak
apt-get -s --no-remove install com.fengyn.hellotweak=1.0.0-3
apt-get --no-remove install com.fengyn.hellotweak=1.0.0-3
apt-get --no-remove --allow-downgrades install com.fengyn.hellotweak=1.0.0-2
```

切换版本后需要重载 SpringBoard 并重新确认显示。最终设备保留 `1.0.0-3`。原始 APT 输出与线上验证脚本位于本地忽略目录 `.build/release-hellotweak-1.0.0-3/`。
