# 常用命令

```bash
# 同一入口，生成完整已验证产物到 .build/repo/
bash update.sh

# 重新验证现有产物
python3 -I scripts/repo.py validate

# 本地预览（不联网、不提交、不推送）
bash deploy.sh

# 有明确发布意图时才运行，脚本继续要求确认
bash deploy.sh --publish

# 构建双模式示例，不进入正式 debs/
THEOS=/opt/theos bash examples/compile.sh --scheme both

# 本地自动化测试，不操作设备或真实远端
python3 -I -m unittest discover -s tests -v

# 检查指定包元数据和文件清单，不运行维护脚本
dpkg-deb --field /absolute/path/to/plugin.deb
dpkg-deb --contents /absolute/path/to/plugin.deb
```

| 模式 | Debian 架构 | Theos scheme |
|---|---|---|
| rootful | `iphoneos-arm` | 空值/默认 |
| rootless | `iphoneos-arm64` | `rootless` |

包架构不等于 CPU 架构；框架依赖由目标环境和源码决定，不用“rootless 必须 ElleKit”代替验证。改动任何已发布包都要提升 Version。

更多：[接入](docs/adding-packages.md) · [发布](docs/publishing.md) · [兼容矩阵](docs/compatibility.md)
