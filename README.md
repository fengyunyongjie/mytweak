# MyTweak Repository

个人 iOS 插件 APT 源。**一个源收录 rootful 和 rootless 的独立构建**，按 deb 的真实包架构生成索引，不复制两套业务源码或用重命名模拟兼容。

源地址：<https://fengyunyongjie.github.io/mytweak/>

> `debs/` 保留 HelloTweak `1.0.0-2`（🔥）和 `1.0.0-3`（🔥✨）的 rootful/rootless 包，可用于升级与显式降级测试；另含 Ack、Gck、Sck 的 rootful 包。HelloTweak `1.0.0-2` rootless 已在 iPad7,11 / iPadOS 18.7.12 验证基本显示，新版本设备切换结果见测试记录。rootful 仅构建通过。Ack/Gck/Sck 的源码不在此仓库，其 rootless 构建尚未提供。后续构建仍不会自动发布。

## 快速开始

运行环境：Python 3.9+、Bash、Git、`dpkg`（包含 `dpkg-deb`、`dpkg-scanpackages`）。macOS 可安装 Homebrew 的 `dpkg`；Debian/Ubuntu 使用 `dpkg` 和 `dpkg-dev`。仅生成源不需要 Theos。

```bash
# 将经过检查的新 deb 放到 debs/，也可以使用子目录。
# 生成完整、已校验的 .build/repo/；generate.sh 与 update.sh 是同一入口。
bash update.sh

# 单独重新校验 deb、索引、压缩文件和 Release
python3 -I scripts/repo.py validate

# 默认只预览相对于 gh-pages 的变化，不提交、不推送、不联网
bash deploy.sh

# 仅在确实准备发布时运行；会再次要求确认
bash deploy.sh --publish
```

所有入口都可从其他工作目录通过绝对路径调用。默认产物在本仓库 `.build/`，不再写到源码根目录。

## 双模式示例

```bash
# 使用已安装的 Theos 和 iOS SDK；自动检查工具，不下载依赖
THEOS=/opt/theos bash examples/compile.sh --scheme both
```

- rootful：默认/空 Theos scheme，Debian 架构 `iphoneos-arm`。
- rootless：Theos 官方 `rootless` scheme，Debian 架构 `iphoneos-arm64`。
- `arm64`、`arm64e` 是 **Mach-O CPU 架构**，不是上面两个包架构的别名。
- 构建产物留在独立的 `.build/examples/` 运行目录，不自动复制到 `debs/`。

具体工具链、最低系统和产物检查见 [HelloTweak](examples/HelloTweak/README.md)。

## 目录与职责

```text
repo.json                 源名称、URL 等非敏感元数据
scripts/repo.py           唯一的仓库生成与完整性校验实现
scripts/deploy.py         显式确认的隔离发布
scripts/build_example.py  示例双模式构建
mk/                      可复用的轻量 Theos 配置
examples/HelloTweak/      示例源码
site/index.html          生成源首页的模板
debs/                    已接纳的正式 deb，可包含子目录
tests/                   本地自动化测试
docs/                    接入、发布、架构和兼容性规则
.build/                  本地生成产物，不提交
```

## 质量与发布边界

```bash
python3 -I -m unittest discover -s tests -v
```

自动化覆盖同包双架构、多版本、坏包、重复身份、路径检查、哈希、发布基线及临时本地 Git 发布。CI 只跑测试、生成和校验，**不会自动部署、不会构建或安装正式插件**。

发布前会对比基线：同一 `(Package, Version, Architecture)` 的内容不能被覆盖；任何修改都应提升 Debian `Version`。脚本不会执行 deb 中的维护脚本，也不把“索引正确”当作“设备运行兼容”。

- [架构与不变量](docs/architecture.md)
- [接入插件与 control 模板](docs/adding-packages.md)
- [发布、回滚与故障处理](docs/publishing.md)
- [兼容矩阵与实机验收](docs/compatibility.md)

历史报告 [DEPLOYMENT_SUCCESS.md](DEPLOYMENT_SUCCESS.md) 不代表当前线上状态。此仓库暂未配置 APT 签名，完整性哈希不能替代来源认证。
