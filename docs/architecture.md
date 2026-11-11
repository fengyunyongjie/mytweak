# 架构与不变量

## 数据流

```text
外部正式插件源码 ──构建/设备测试──> 经确认的 deb ──> debs/
HelloTweak 示例 ──双模式构建──> .build/examples/（不自动进入正式包）

repo.json + debs/ + site/index.html
        │
        ▼
scripts/repo.py build
  只读 control/data 归档 → 唯一身份检查 → dpkg-scanpackages -m
  → 确定性压缩 → Release/首页 → 完整性验证
        │ 成功后替换输出；失败保留之前的有效产物
        ▼
.build/repo/
        │
scripts/deploy.py
  纯产物快照 → 与已发布 Packages 比较 → detached 临时 worktree
        │ 默认只预览；显式 publish + 确认 + 远端基线一致才提交/推送
        ▼
gh-pages → 现有 GitHub Pages 源地址
```

## 一份源，两种包

继续使用 flat APT 布局：源根目录中一个 `Packages` 收录所有版本和架构。`dpkg-scanpackages -m` 不能换成默认去重扫描，否则可能丢掉另一个构建。

| 含义 | rootful | rootless |
|---|---|---|
| Debian `Architecture` | `iphoneos-arm` | `iphoneos-arm64` |
| Theos scheme | 空值（默认） | `rootless` |
| 安装前缀 | `/` | 由 Theos rootless module 管理 |
| 示例最低构建系统 | iOS 12 | iOS 15 |

同一插件的 Package ID 和版本可相同，因为架构不同。不要创建 `iphoneos-arm64-rootless` 这样的自定义架构，也不要把 rootful 二进制改 control 后当作 rootless。`Architecture: all` 只用于真正架构无关、安装位置也适用的资源包，不能用于插件 dylib。

最低构建系统不是运行兼容保证。CPU/ABI、bootstrap、注入框架、私有 API 和设备测试各自独立，不能由一个 `rootless` 标签代替。

## 发布产物契约

```text
Packages
Packages.gz
Packages.bz2
Packages.xz
Release
index.html
.nojekyll
debs/**/*.deb
CNAME                    可选；发布时只保留基线已有值
```

- 正式包原样复制，不重打包，不改 Package ID/Version/Depends。
- `Filename` 是规范相对路径，必须在 `debs/` 内；不接受符号链接、越界路径或文件名中的空白/URL 特殊字符。
- 每个 deb 恰有一条索引记录；每条记录指向真实文件；Size、MD5、SHA1、SHA256 与文件一致。
- 三种压缩索引解压后相同；Release 是一个连续 Deb822 记录，架构集合来自实际包，哈希覆盖四个索引文件。
- 校验失败不发布。`build` 只替换空目录或通过校验的旧产物目录，拒绝覆盖无关文件；临时文件、锁和替换期间的 `.repo.previous` 备份位于输出目录的父目录。普通错误或 Ctrl-C 会尝试恢复旧产物；进程被强制终止时备份保留供手动恢复，后续构建不会覆盖它。这不是面向在线服务的零间隙目录切换，发布应使用完整快照。
- 脚本不会执行包内维护脚本。归档可解析和索引有效也不代表包可信或运行安全，正式包仍需来源和设备审查。

## 可复现性与历史

压缩不嵌入文件名和当前时间。`Release.Date` 默认使用输入 deb 中最新的文件修改时间；跨机器需要字节一致时显式设置：

```bash
SOURCE_DATE_EPOCH=1700000000 bash generate.sh
```

发布基线由 `Packages` 给出。发布前比较相同 `(Package, Version, Architecture)` 的 SHA256，不允许换内容而不升版本。当前没有持久的全历史包注册表：删除旧版本后，如果需要确保它永远不可复用，保留历史索引作为额外校验基线或保留旧包。不要声称只检查当前基线就覆盖了所有历史。

回滚推荐发布更高版本的修复包，而不是静默替换旧包或强推分支。仓库不自动删除旧版本；保留策略由维护者明确决定。

## 源码分层边界

Ack/Gck/Sck 的源码未在此仓库提供；这里不尝试重构或转换其内部实现。正式插件可继续在独立源码仓库构建，再将有来源记录的 deb 接入。

未来的源码依赖方向保持为：`Logos hook → 插件业务逻辑 → 按需兼容工具`。至少出现两个真实复用者后，再提取轻量源码模块；不提前引入共享 dylib 与跨插件 ABI 依赖。

需要运行时路径时优先使用选定 Theos 版本的 `rootless.h` / `ROOT_PATH_NS` 等官方能力，只转换插件安装路径。不要给系统路径、用户目录或应用容器统一拼接 `/var/jb`。HelloTweak 当前没有这类文件访问，因此没有空的路径适配层。
