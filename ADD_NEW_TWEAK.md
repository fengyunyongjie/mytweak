# 📦 添加新插件到源 - 完整指南

## 🚀 快速开始（3 步完成）

### 1. 准备 .deb 文件
将你编译好的 `.deb` 文件复制到 `debs/` 目录

### 2. 生成索引文件
```bash
bash update.sh
```

### 3. 部署到 GitHub Pages
```bash
bash deploy.sh
```

---

## 📖 详细流程

### 方法 A：使用 Theos 开发新插件（推荐）

#### 1. 创建新插件项目
```bash
# 在项目根目录创建新插件
mkdir -p examples/MyNewTweak
cd examples/MyNewTweak

# 初始化 Theos 项目
nic.pl

# 选择 [iphone/tweak] 模板
```

#### 2. 配置 Makefile

**Rootless 版本（iOS 15+）：**
```makefile
TARGET := iphone:clang:latest:7.0
ARCHS = arm64
THEOS_PACKAGE_SCHEME = rootless

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = MyNewTweak

MyNewTweak_FILES = Tweak.x
MyNewTweak_CFLAGS = -fobjc-arc
MyNewTweak_FRAMEWORKS = UIKit

include $(THEOS_MAKE_PATH)/tweak.mk
```

**Rootful 版本（iOS 12-14）：**
```makefile
TARGET := iphone:clang:latest:7.0
ARCHS = armv7 arm64

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = MyNewTweak

MyNewTweak_FILES = Tweak.x
MyNewTweak_CFLAGS = -fobjc-arc
MyNewTweak_FRAMEWORKS = UIKit

include $(THEOS_MAKE_PATH)/tweak.mk
```

#### 3. 编译插件

**编译 Rootless 版本：**
```bash
make clean
make THEOS_PACKAGE_SCHEME=rootless package
# 输出: packages/com.yourname.mynewtweak_*.deb
```

**编译 Rootful 版本：**
```bash
make clean
make package
# 输出: packages/com.yourname.mynewtweak_*.deb
```

#### 4. 复制到 debs 目录
```bash
# 复制 rootless 版本
cp examples/MyNewTweak/packages/*.deb debs/

# 如果也做了 rootful 版本，复制过来
cp examples/MyNewTweak/packages/*.deb debs/
```

#### 5. 更新索引
```bash
bash update.sh
```

#### 6. 部署
```bash
bash deploy.sh
```

---

### 方法 B：使用现有的 .deb 文件

#### 1. 复制 .deb 文件
```bash
# 将你的 .deb 文件复制到 debs 目录
cp /path/to/your/tweak.deb debs/
```

#### 2. 检查 control 文件（重要！）

确保你的 .deb 包含正确的 control 信息：

**Rootless 包应该有：**
```
Package: com.yourname.tweak
Architecture: iphoneos-arm64
Depends: firmware (>= 15.0), ellekit
```

**Rootful 包应该有：**
```
Package: com.yourname.tweak
Architecture: iphoneos-arm
Depends: mobilesubstrate (>= 0.9.5000), firmware (>= 12.0)
```

#### 3. 更新和部署
```bash
bash update.sh
bash deploy.sh
```

---

## 🛠️ 自动化脚本说明

### update.sh - 更新索引文件
- 扫描 `debs/` 目录中的所有 .deb 文件
- 生成 Packages 文件（包含所有架构的包）
- 生成压缩版本（.bz2, .gz, .xz）
- 更新 Release 文件

### deploy.sh - 部署到 GitHub Pages
- 切换到 gh-pages 分支
- 复制最新的索引文件和 .deb 包
- 提交并推送到 GitHub
- 自动切回 main 分支

---

## 📋 常用命令

```bash
# 查看当前源中的所有包
cat Packages | grep "^Package:"

# 查看支持的架构
cat Release | grep "^Architectures:"

# 查看某个包的详细信息
dpkg-deb -f debs/your-package.deb

# 提取 .deb 内容查看
mkdir temp && dpkg-deb -x debs/your-package.deb temp/

# 重新生成所有索引
bash update.sh

# 部署更新
bash deploy.sh
```

---

## ⚠️ 注意事项

### 1. 架构命名规范
- ❌ **不要使用**: `iphoneos-arm64-rootless`
- ✅ **Rootless 使用**: `iphoneos-arm64`
- ✅ **Rootful 使用**: `iphoneos-arm`

### 2. 依赖项
- **Rootless**: 必须依赖 `ellekit`
- **Rootful**: 通常依赖 `mobilesubstrate`

### 3. 固件版本
- **Rootless**: `firmware (>= 15.0)`
- **Rootful**: `firmware (>= 12.0)`

### 4. 版本号
推荐使用语义化版本：`VERSION-BUILD`
- 例如：`1.0.0-1`
- 带调试标记：`1.0.0-1+debug`

---

## 🎯 完整工作流示例

假设你要添加一个名为 "MyAwesomeTweak" 的新插件：

```bash
# 1. 创建插件目录
mkdir examples/MyAwesomeTweak
cd examples/MyAwesomeTweak

# 2. 初始化 Theos 项目
nic.pl
# 选择 [iphone/tweak]

# 3. 编辑你的 Tweak.x 和配置文件
vim Tweak.x
vim Makefile
vim control

# 4. 编译（假设做 rootless 版本）
make THEOS_PACKAGE_SCHEME=rootless package

# 5. 复制 .deb 到源目录
cp packages/*.deb ../../debs/

# 6. 回到项目根目录
cd ../..

# 7. 更新索引
bash update.sh

# 8. 部署
bash deploy.sh

# ✅ 完成！等待几分钟让 GitHub Pages 更新
```

---

## 📱 测试你的插件

在设备上测试：

1. **添加源**（如果还没添加）:
   ```
   https://fengyunyongjie.github.io/mytweak/
   ```

2. **清除缓存**（重要！）:
   - Sileo: 编辑 → 添加源 → 删除此源 → 设置 → 清除缓存 → 重新添加

3. **搜索并安装**你的插件

4. **重启 SpringBoard**:
   ```bash
   # Rootless
   killall -9 SpringBoard

   # Rootful
   killall -9 SpringBoard
   ```

---

## 🔧 故障排查

### 问题 1: Sileo 看不到插件
**解决方案**:
```bash
# 确认 Packages 文件包含你的包
cat Packages | grep "Package: com.yourname.tweak"

# 确认架构正确
cat Packages | grep -A 3 "Package: com.yourname.tweak" | grep Architecture

# 清除 Sileo 缓存后重试
```

### 问题 2: 安装后不生效
**解决方案**:
```bash
# 检查 plist 文件是否正确
dpkg-deb -x debs/your-tweak.deb temp/
cat temp/var/jb/Library/MobileSubstrate/DynamicLibraries/*.plist

# 重启 SpringBoard
killall -9 SpringBoard
```

### 问题 3: 依赖错误
**解决方案**:
```bash
# 检查 control 文件
dpkg-deb -f debs/your-tweak.deb | grep Depends

# 确保 rootless 使用 ellekit，rootful 使用 mobilesubstrate
```

---

## 📚 项目结构

```
mytweak/
├── debs/                          # 存放所有 .deb 包
│   ├── tweak1_1.0.0-1_iphoneos-arm64.deb
│   └── tweak1_1.0.0-1_iphoneos-arm.deb
├── examples/                      # 插件源代码
│   ├── HelloTweak/
│   └── MyNewTweak/
├── Packages                       # 包索引（自动生成）
├── Packages.bz2                   # 压缩索引（自动生成）
├── Packages.gz                    # 压缩索引（自动生成）
├── Packages.xz                    # 压缩索引（自动生成）
├── Release                        # 发行信息（自动生成）
├── update.sh                      # 更新索引脚本
├── deploy.sh                      # 部署脚本
└── index.html                     # 源主页
```

---

## 🎓 进阶技巧

### 同时发布 Rootless 和 Rootful 版本

```bash
# 1. 编译 rootless 版本
make THEOS_PACKAGE_SCHEME=rootless package
mv packages/*.deb ../../debs/tweak_1.0.0-1_iphoneos-arm64.deb

# 2. 修改 Makefile，去掉 THEOS_PACKAGE_SCHEME
vim Makefile

# 3. 编译 rootful 版本
make clean
make package
mv packages/*.deb ../../debs/tweak_1.0.0-1_iphoneos-arm.deb

# 4. 更新和部署
cd ../..
bash update.sh
bash deploy.sh
```

### 使用预构建脚本

创建 `examples/MyNewTweak/build.sh`:
```bash
#!/bin/bash
set -e

echo "🔨 编译 Rootless 版本..."
make clean
make THEOS_PACKAGE_SCHEME=rootless package
cp packages/*.deb ../../debs/

echo "🔨 编译 Rootful 版本..."
make clean
make package
cp packages/*.deb ../../debs/

echo "✅ 编译完成！现在运行: cd ../.. && bash update.sh && bash deploy.sh"
```

---

**记住：每次添加新插件后，都要运行 `bash update.sh` 和 `bash deploy.sh`！**
