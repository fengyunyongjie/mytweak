# 🎉 添加新插件工作流程已就绪！

## ✅ 已创建的文件

### 📚 文档
1. **[README.md](README.md)** - 项目介绍和快速开始
2. **[QUICKREF.md](QUICKREF.md)** - 快速参考卡（推荐收藏！）
3. **[ADD_NEW_TWEAK.md](ADD_NEW_TWEAK.md)** - 完整的添加插件指南
4. **[DEPLOYMENT_SUCCESS.md](DEPLOYMENT_SUCCESS.md)** - 当前部署状态

### 🛠️ 脚本
1. **update.sh** - 更新源索引（生成 Packages 文件）
2. **deploy.sh** - 部署到 GitHub Pages
3. **generate.sh** - 生成所有索引文件（手动使用）

---

## 🚀 最简单的工作流程

### 添加新插件只需 3 步：

```bash
# 1. 把你的 .deb 文件放到 debs 目录
cp /path/to/your-tweak.deb debs/

# 2. 更新索引
bash update.sh

# 3. 部署到 GitHub Pages
bash deploy.sh
```

**就这么简单！** ✨

---

## 📱 使用 Theos 开发新插件

```bash
# 1. 创建新插件项目
mkdir examples/MyAwesomeTweak && cd examples/MyAwesomeTweak

# 2. 初始化 Theos
nic.pl  # 选择 [iphone/tweak]

# 3. 编辑你的代码
vim Tweak.x

# 4. 编译 Rootless 版本（iOS 15+）
make THEOS_PACKAGE_SCHEME=rootless package

# 5. 复制到源目录
cp packages/*.deb ../../debs/

# 6. 回到根目录并部署
cd ../..
bash update.sh
bash deploy.sh
```

---

## 📋 快速参考

### 架构命名规范（重要！）

| 类型 | 架构名 | 依赖 | 文件名示例 |
|------|--------|------|-----------|
| **Rootless** (iOS 15+) | `iphoneos-arm64` | `ellekit` | `tweak_1.0.0-1_iphoneos-arm64.deb` |
| **Rootful** (iOS 12-14) | `iphoneos-arm` | `mobilesubstrate` | `tweak_1.0.0-1_iphoneos-arm.deb |

### Makefile 配置

**Rootless 版本：**
```makefile
TARGET := iphone:clang:latest:7.0
ARCHS = arm64
THEOS_PACKAGE_SCHEME = rootless
```

**Rootful 版本：**
```makefile
TARGET := iphone:clang:latest:7.0
ARCHS = armv7 arm64
```

---

## 🎯 常用命令

```bash
# 查看当前所有包
cat Packages | grep "^Package:"

# 查看支持的架构
cat Release | grep "^Architectures:"

# 检查某个 .deb 的信息
dpkg-deb -f debs/your-tweak.deb | grep -E "^(Package|Version|Architecture|Depends):"

# 更新索引
bash update.sh

# 部署
bash deploy.sh
```

---

## ⚠️ 重要提示

1. **架构命名**
   - ❌ 永远不要使用 `iphoneos-arm64-rootless`
   - ✅ Rootless 使用 `iphoneos-arm64`
   - ✅ Rootful 使用 `iphoneos-arm`

2. **依赖项**
   - Rootless 必须依赖 `ellekit`
   - Rootful 依赖 `mobilesubstrate`

3. **清除缓存**
   - 每次部署后，用户需要在 Sileo 中清除缓存

---

## 📊 当前状态

```
✅ 源地址: https://fengyunyongjie.github.io/mytweak/
✅ 支持架构: iphoneos-arm, iphoneos-arm64
✅ 当前插件: 1 个 (Hello Tweak)
✅ 自动化脚本: 已配置
✅ 文档: 已创建
```

---

## 🔧 测试流程

部署后按以下步骤测试：

1. **等待 1-3 分钟**让 GitHub Pages 更新
2. 在 Sileo 中删除源（如果已添加）
3. 在设置中清除缓存
4. 重新添加源：`https://fengyunyongjie.github.io/mytweak/`
5. 刷新源
6. 搜索并安装你的插件
7. 重启 SpringBoard

---

## 📂 项目结构

```
mytweak/
├── debs/                    # 👈 放置 .deb 文件的地方
│   ├── *.deb
│   └── *.deb
├── examples/                # 插件源代码
│   ├── HelloTweak/
│   └── YourTweak/          # 在这里开发新插件
├── Packages                 # 自动生成
├── Packages.bz2             # 自动生成
├── Packages.gz              # 自动生成
├── Packages.xz              # 自动生成
├── Release                  # 自动生成
├── update.sh                # ⭐ 更新索引脚本
├── deploy.sh                # ⭐ 部署脚本
├── README.md                # 📚 项目介绍
├── QUICKREF.md              # 📚 快速参考
└── ADD_NEW_TWEAK.md         # 📚 完整指南
```

---

## 🎓 下一步

1. **阅读 [QUICKREF.md](QUICKREF.md)** - 快速了解工作流程
2. **查看 [ADD_NEW_TWEAK.md](ADD_NEW_TWEAK.md)** - 了解详细流程
3. **开始开发你的插件！**

---

## 💡 提示

- 每次添加新插件后运行 `bash update.sh && bash deploy.sh`
- 保持架构命名正确，否则 Sileo 无法识别
- 部署后等待 1-3 分钟让 GitHub Pages 更新
- 记得告诉用户清除缓存

---

**现在你可以轻松添加新插件了！🎉**
