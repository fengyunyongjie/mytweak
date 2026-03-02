#!/bin/bash

# 编译脚本 - 自动编译 rootless 和 rootful 版本

set -e

THEOS=${THEOS:-$HOME/theos}

if [ ! -d "$THEOS" ]; then
    echo "❌ 错误: 未找到 Theos"
    echo "请先安装 Theos: https://theos.dev/docs/installation"
    exit 1
fi

echo "🔨 开始编译 HelloTweak..."

cd "$(dirname "$0")/HelloTweak"

# 编译 rootless 版本
echo ""
echo "📦 编译 Rootless 版本..."
make clean
make package THEOS_PACKAGE_SCHEME=rootless

if [ -f ".theos/packages/"*.rootless.*.deb ]; then
    ROOTLESS_DEB=$(ls .theos/packages/*.rootless.*.deb | head -1)
    echo "✅ Rootless 版本编译成功: $ROOTLESS_DEB"

    # 复制到 debs 目录
    cp "$ROOTLESS_DEB" ../../debs/rootless/
    echo "📋 已复制到 debs/rootless/"
fi

# 编译 rootful 版本
echo ""
echo "📦 编译 Rootful 版本..."
make clean
make package THEOS_PACKAGE_SCHEME=rootful

if [ -f ".theos/packages/"*.deb ]; then
    # 找到非 rootless 的 deb 包
    ROOTFUL_DEB=$(ls .theos/packages/*.deb | grep -v rootless | head -1)
    echo "✅ Rootful 版本编译成功: $ROOTFUL_DEB"

    # 复制到 debs 目录
    cp "$ROOTFUL_DEB" ../../debs/rootful/
    echo "📋 已复制到 debs/rootful/"
fi

echo ""
echo "🎉 编译完成！"
echo ""
echo "下一步："
echo "  cd ../.."
echo "  git add debs/"
echo "  git commit -m 'Add HelloTweak'"
echo "  git push"
