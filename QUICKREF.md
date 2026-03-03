# 🚀 快速参考卡 - 添加新插件

## ⚡ 三步添加新插件

```bash
# 1. 复制 .deb 文件到 debs 目录
cp your-tweak.deb debs/

# 2. 更新索引
bash update.sh

# 3. 部署到 GitHub Pages
bash deploy.sh
```

**✅ 完成！** 等待 1-3 分钟让 GitHub Pages 更新

---

## 📱 在设备上测试

1. Sileo → 编辑 → 删除源
2. 设置 → 清除缓存
3. 编辑 → 添加源 → 输入: `https://fengyunyongjie.github.io/mytweak/`
4. 搜索你的插件并安装
5. 重启 SpringBoard

---

## 🔨 使用 Theos 开发新插件

```bash
# 创建新插件
mkdir examples/MyTweak && cd examples/MyTweak
nic.pl  # 选择 [iphone/tweak]

# 编辑代码
vim Tweak.x

# 编译 Rootless 版本
make THEOS_PACKAGE_SCHEME=rootless package

# 复制到源目录
cp packages/*.deb ../../debs/

# 回到根目录更新和部署
cd ../.. && bash update.sh && bash deploy.sh
```

---

## ✅ 架构命名规范（重要！）

| 类型 | 架构名 | 依赖 |
|------|--------|------|
| **Rootless** (iOS 15+) | `iphoneos-arm64` | `ellekit` |
| **Rootful** (iOS 12-14) | `iphoneos-arm` | `mobilesubstrate` |

❌ **不要使用**: `iphoneos-arm64-rootless`

---

## 📂 项目结构

```
mytweak/
├── debs/                    # 👈 把你的 .deb 放这里
├── update.sh                # 更新索引
├── deploy.sh                # 部署
└── examples/                # 插件源码
    ├── HelloTweak/
    └── YourTweak/
```

---

## 🔍 常用命令

```bash
# 查看当前所有包
cat Packages | grep "^Package:"

# 查看支持的架构
cat Release | grep "^Architectures:"

# 检查某个 .deb 的信息
dpkg-deb -f debs/your-tweak.deb

# 查看部署状态
git log gh-pages --oneline -5
```

---

## ⚠️ 常见问题

**Q: Sileo 看不到插件？**
A: 清除缓存！删除源 → 清除缓存 → 重新添加

**Q: 架构错误？**
A: 检查你的 .deb 的 control 文件：
- Rootless: `Architecture: iphoneos-arm64`
- Rootful: `Architecture: iphoneos-arm`

**Q: 依赖错误？**
A: Rootless 必须依赖 `ellekit`，Rootful 依赖 `mobilesubstrate`

---

## 📚 完整文档

详细说明请查看：[ADD_NEW_TWEAK.md](ADD_NEW_TWEAK.md)

---

**记住：每次添加新插件都要运行 `bash update.sh` 和 `bash deploy.sh`！**
