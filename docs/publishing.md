# 发布、回滚与故障处理

## 环境

源生成和校验依赖 Python 3.9+、`dpkg`、`dpkg-deb`、`dpkg-scanpackages`；发布还需要 Git 和现有 `gh-pages` 分支。开发依赖由使用者自行安装，脚本不自动安装工具或配置 GitHub。

`repo.json` 是源元数据的唯一配置入口。默认输入 `debs/`，输出 `.build/repo/`。参数可覆盖目录：

```bash
python3 -I scripts/repo.py build \
  --debs /absolute/path/to/packages \
  --output /absolute/path/to/generated-repo
python3 -I scripts/repo.py validate --repo /absolute/path/to/generated-repo
bash deploy.sh --repo /absolute/path/to/generated-repo
```

生成器拒绝覆盖无关目录。旧输出损坏、遗留锁或 `.repo.previous` 备份时，先查明原因；可选择一个新的输出目录重新生成。强制终止可能留下完整旧备份供恢复，不要盲目递归删除目录、备份或移除仍在使用的锁。

## 1. 本地生成与预览

```bash
bash update.sh
bash deploy.sh
```

`deploy.sh` 默认：

1. 使用本地 `refs/heads/gh-pages`，没有则使用 `refs/remotes/origin/gh-pages` 作为发布基线。
2. 复制已生成目录中的发布白名单到本次临时快照，保留基线已有 `CNAME`，读取基线 `Packages`。
3. 校验快照与基线，同版本同架构必须同 SHA256。
4. 在 detached 临时 worktree 中展示变化，退出时清理本次临时资源。

默认模式不联网、不提交、不推送。开发分支和暂存区不变；即使开发工作树有改动，也不会被加入发布。旧发布分支中的脚本、工具配置等不属于产物，预览会显示它们将被移除。

没有有效基线会失败，而不是跳过不可变检查或偷偷初始化发布分支。当前仓库已有发布历史；初始化一个全新的源属于单独操作。

## 2. 显式发布

只有准备好改变线上源时运行：

```bash
bash deploy.sh --publish
```

脚本先展示并要求确认，再检查远端。无人值守的明确授权可用 `--publish --yes`；不要把该参数加入默认本地任务或拉取请求 CI。

发布前远端 `gh-pages` 必须与本次检查的基线一致；随后使用普通 push，不 force push。远端变更、校验失败、提交失败、推送失败都会返回非零，不伪装为“没有更改”。

### 远端比本地基线更新

默认不擅自移动共享的本地 `gh-pages` 分支；通过 push URL 发布也不依赖 tracking ref 自动更新。成功发布后或发现远端有更新时，显式同步远端，再用 tracking ref 重新预览、确认：

```bash
git fetch origin gh-pages
bash deploy.sh --baseline-ref refs/remotes/origin/gh-pages
bash deploy.sh --baseline-ref refs/remotes/origin/gh-pages --publish
```

`git fetch` 和 `--publish` 都属于明确联网操作，离线检查不需要执行。即使预览后远端再次改变，发布也应失败并重新审查，而不是覆盖其他修改。

## 3. 线上和设备验收

本地验证不说明 Pages 已更新。真正发布后再检查源根目录的 `Release`、`Packages` 和索引指向的 deb HTTP 可访问性；包管理器刷新、依赖解析、安装升级与运行表现见 [兼容验收](compatibility.md)。

除非确认是缓存问题，不要把“删除源并清空全部缓存”作为所有故障的默认修复。

## 回滚

- 保留前一个发布 commit 和构建证据。
- 推荐发布更高 Debian 版本号的修复包，确保已安装客户端能升级。
- 如需回退源的可见内容，先审查对应历史产物与版本影响，再显式发布；本脚本不会强推或替换已发布的同版本包。
- 当前基线只覆盖当前索引。长期不可变性需要保留旧包或额外保存历史索引；签名、渠道分离与历史留存策略尚未自动化。

## CI

`.github/workflows/validate.yml` 仅测试和生成校验，权限为 `contents: read`，没有部署、token 发布或 Pages 设置步骤。它不替代设备测试，也不会通过推送 main 自动更新线上源。

当前未配置 `InRelease` / `Release.gpg`。哈希用于一致性校验，不提供发布者认证；不要在故障处理时建议全局关闭客户端签名校验。
