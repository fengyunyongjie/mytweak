# 接入插件

## 1. 确认源码或构建来源

本仓库不自动下载、转换或重打包第三方插件。新包应来自自己可维护的源码或经过确认的构建产物。至少记录：源码位置/revision、Theos revision、SDK/编译器、Package/Version/Architecture、SHA256 以及实机测试结果。

当前 Ack/Gck/Sck 仅有成品包。要提供它们的 rootless 版本，应在原源码中完成链接、资源、路径与 ABI 适配，再用 Theos rootless scheme 构建，不能改现有 rootful 包的 Architecture 或文件名代替。

## 2. 检查真实包元数据

```bash
dpkg-deb --field /absolute/path/to/plugin.deb
dpkg-deb --contents /absolute/path/to/plugin.deb
```

这些命令只读取 control 与归档清单，不会安装或运行维护脚本。

- Package ID 保持稳定；现有 `com.yourcompany.ack/gck/sck` 即使像占位名，也不能顺手改名。
- rootful `Architecture: iphoneos-arm`，rootless `Architecture: iphoneos-arm64`。
- `Depends` 依据真实源码和目标环境。示例使用 `mobilesubstrate (>= 0.9.5000)` 兼容接口，但仍需验证目标框架是否提供该接口/虚拟包；rootless 不等于必须直接依赖 ElleKit。
- `firmware` 最低版本要与编译 deployment target 及业务需要一致。不要为了允许安装降低声明，而二进制依然依赖更高版本 API。
- `Filename/Size/MD5sum/SHA1/SHA256` 由仓库生成，不写入 deb 的 control。
- 依赖最低版本只有在兼容依据明确时才添加；不要凭猜测重写 Sck 对 Ack/Gck 的约束。

独立 control 示例见 [控制文件模板](../debs/CONTROL_TEMPLATE.md)。

## 3. 检查版本与归档

任何字节变化（含依赖或维护脚本）都需要新版本。用 Debian 比较，不用字符串排序或仅看日期：

```bash
dpkg --compare-versions '1.0.0-2' gt '1.0.0-1'
```

例如 `1.0.0-1+debug` 不一定比 `1.0.0-1` 更旧；不要靠去掉 `+debug` 认为客户端会升级。预发布版本可按明确策略使用 `~` 并以 `dpkg --compare-versions` 核验。本仓库暂不拆 stable/beta 源。

需要解包深入检查时，每个包使用新的空临时目录；检查脚本放在另一目录，路径作为参数，Python 使用 `-I`。不要从解包目录启动解释器、构建工具或运行包内脚本。

## 4. 接纳产物

审查通过后手动复制**指定的一个文件**到 `debs/`。保留默认 `Package_Version_Architecture.deb` 命名，避免通配符误复制旧包。也可以使用 `debs/rootful/`、`debs/rootless/` 子目录；现有顶层包不必迁移。

不要覆盖已存在的同版本产物。若只是移动目录、字节未变，索引路径可变化，但应考虑客户端缓存旧 Filename 的时间窗口，避免过早删除旧下载地址。

## 5. 生成、验证和预览

```bash
bash update.sh
python3 -I scripts/repo.py validate
bash deploy.sh
```

`update.sh` 和 `generate.sh` 都会生成 `.build/repo/`，包含 Release 与所有压缩索引。发布预览会对本地 `gh-pages` 基线检查不可变规则，不会连接线上源。确认实际发布请看 [发布指南](publishing.md)。

也可以显式检查某份历史索引：

```bash
python3 -I scripts/repo.py validate --baseline /absolute/path/to/old/Packages
```

新包只有进入 `debs/`、通过完整校验并真正发布后，才是源中可安装的包。示例构建成功不会自动完成上述步骤。
