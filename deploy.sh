#!/bin/bash
set -e

echo "🚀 准备部署到 GitHub Pages..."
echo ""

# 检查是否有未提交的更改
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  检测到未提交的更改"
    echo ""
    git status --short
    echo ""
    read -p "是否继续部署？(y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 部署已取消"
        exit 1
    fi
fi

# 保存当前分支
CURRENT_BRANCH=$(git branch --show-current)

echo "📦 准备文件..."
echo ""

# 临时文件目录
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# 复制必要的文件到临时目录
echo "⏳ 复制索引文件..."
cp Packages Packages.bz2 Packages.gz Packages.xz Release "$TEMP_DIR/" 2>/dev/null || true

echo "⏳ 复制 .deb 文件..."
mkdir -p "$TEMP_DIR/debs"
cp debs/*.deb "$TEMP_DIR/debs/" 2>/dev/null || true

echo "⏳ 复制网页文件..."
cp index.html "$TEMP_DIR/" 2>/dev/null || true

# 检查是否在 gh-pages 分支
if git rev-parse --verify gh-pages >/dev/null 2>&1; then
    echo ""
    echo "⏳ 切换到 gh-pages 分支..."
    git checkout gh-pages >/dev/null 2>&1 || git checkout -b gh-pages origin/gh-pages >/dev/null 2>&1

    echo "⏳ 更新文件..."
    # 删除旧的索引和 deb 文件
    rm -f Packages Packages.bz2 Packages.gz Packages.xz Release 2>/dev/null || true
    rm -rf debs 2>/dev/null || true

    # 复制新文件
    cp "$TEMP_DIR/"* . 2>/dev/null || true
    cp -r "$TEMP_DIR/debs" . 2>/dev/null || true

    echo "⏳ 提交更改..."
    git add -A
    git commit -m "Update repository - $(date +'%Y-%m-%d %H:%M:%S')" >/dev/null 2>&1 || {
        echo "ℹ️  没有新的更改需要提交"
        git checkout "$CURRENT_BRANCH" >/dev/null 2>&1
        exit 0
    }

    echo "⏳ 推送到 GitHub..."
    git push origin gh-pages

    echo "⏳ 切回 $CURRENT_BRANCH 分支..."
    git checkout "$CURRENT_BRANCH" >/dev/null 2>&1

    echo ""
    echo "✅ 部署成功！"
    echo ""
    echo "🌐 源地址: https://fengyunyongjie.github.io/mytweak/"
    echo ""
    echo "⏳ GitHub Pages 通常需要 1-3 分钟更新"
    echo "📱 在 Sileo 中测试前请："
    echo "   1. 删除源（如果已添加）"
    echo "   2. 在设置中清除缓存"
    echo "   3. 重新添加源"
    echo "   4. 刷新源"
else
    echo "ℹ️  gh-pages 分支不存在，跳过部署"
    echo "   请先创建 gh-pages 分支："
    echo "   git checkout -b gh-pages && git push origin gh-pages"
fi
