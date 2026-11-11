# 添加新插件

完整规则统一维护在 [接入插件指南](docs/adding-packages.md)，避免多份 control/构建示例互相漂移。

```bash
# 手动接纳已检查的 deb 到 debs/ 后：
bash update.sh
python3 -I scripts/repo.py validate
bash deploy.sh                      # 只预览，不发布
```

实际发布需显式 `bash deploy.sh --publish` 并确认。生成产物位于 `.build/repo/`，不是仓库根目录。

- [双模式示例](examples/HelloTweak/README.md)
- [控制文件模板](debs/CONTROL_TEMPLATE.md)
- [发布指南](docs/publishing.md)
- [兼容性与设备测试](docs/compatibility.md)
