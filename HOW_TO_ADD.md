# 接入与维护入口

- [README：当前架构与快速开始](README.md)
- [添加插件：来源、版本、架构和依赖检查](docs/adding-packages.md)
- [发布：本地预览、显式确认与失败处理](docs/publishing.md)
- [兼容性：正式包状态与设备验收](docs/compatibility.md)
- [HelloTweak：一份源码分别构建 rootful / rootless](examples/HelloTweak/README.md)

`bash update.sh` 完整生成 `.build/repo/`；`bash deploy.sh` 默认只预览。CI 只校验，不自动发布。

[2026-03-03 部署报告](DEPLOYMENT_SUCCESS.md) 是历史快照，不代表当前包数量、架构支持或线上状态。
