#!/bin/bash
set -e

echo "🔨 正在更新源索引..."
echo ""

# 检查 debs 目录是否存在
if [ ! -d "debs" ]; then
    echo "❌ 错误: debs 目录不存在"
    echo "   请先创建 debs 目录并放入 .deb 文件"
    exit 1
fi

# 检查是否有 .deb 文件
DEB_COUNT=$(find debs -name "*.deb" -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$DEB_COUNT" -eq 0 ]; then
    echo "❌ 错误: debs 目录中没有 .deb 文件"
    exit 1
fi

echo "📦 发现 $DEB_COUNT 个 .deb 文件"
echo ""

# 生成 Packages
echo "⏳ 生成 Packages 文件..."
dpkg-scanpackages -m debs > Packages 2>/dev/null || {
    echo "❌ 生成 Packages 失败"
    exit 1
}

# 生成压缩文件
echo "⏳ 生成压缩文件..."
bzip2 -c9 Packages > Packages.bz2
xz -c9 Packages > Packages.xz
gzip -c9 Packages > Packages.gz

# 统计信息
PACKAGE_COUNT=$(grep "^Package:" Packages | wc -l | tr -d ' ')
ARCH_COUNT=$(grep "^Architecture:" Packages | sort -u | wc -l | tr -d ' ')

echo ""
echo "✅ 索引更新完成！"
echo ""
echo "📊 统计信息:"
echo "  • .deb 文件: $DEB_COUNT"
echo "  • 包数量: $PACKAGE_COUNT"
echo "  • 架构数量: $ARCH_COUNT"
echo ""
echo "📦 支持的架构:"
grep "^Architecture:" Packages | sort -u | sed 's/Architecture: /  • /'
echo ""
echo "📋 包列表:"
grep "^Package:" Packages | sed 's/Package: /  • /' | sed 's/$/:/' && grep "^Name:" Packages | sed 's/Name: /    /' | paste - - | column -t
echo ""
echo "🚀 下一步: 运行 'bash deploy.sh' 部署到 GitHub Pages"
