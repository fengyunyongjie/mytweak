#!/bin/bash

# iOS 插件源构建脚本
# 用于生成 Release 和 Packages 文件

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEBS_DIR="$REPO_ROOT/debs"
OUTPUT_DIR="$REPO_ROOT/output"

echo "🔨 构建插件源..."

# 清理并创建输出目录
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/rootful"
mkdir -p "$OUTPUT_DIR/rootless"

# 处理 rootful 版本
if [ -d "$DEBS_DIR/rootful" ] && [ "$(ls -A $DEBS_DIR/rootful 2>/dev/null)" ]; then
    echo "📦 处理 rootful 包..."

    # 复制所有 deb 包
    cp -r "$DEBS_DIR/rootful/"*.deb "$OUTPUT_DIR/rootful/" 2>/dev/null || true

    # 生成 Packages 文件
    cd "$OUTPUT_DIR/rootful"
    if ls *.deb 1> /dev/null 2>&1; then
        dpkg-scanpackages --multiversion . /dev/null > Packages 2>/dev/null || \
        for deb in *.deb; do
            echo "处理 $deb..."
            dpkg-deb -I "$deb" >> Packages
            echo "Filename: ./$(basename $deb)" >> Packages
            echo "Size: $(stat -f%z "$deb" 2>/dev/null || stat -c%s "$deb")" >> Packages
            echo "MD5sum: $(md5 -q "$deb" 2>/dev/null || md5sum "$deb" | cut -d' ' -f1)" >> Packages
            echo "SHA1: $(shasum -a 1 "$deb" 2>/dev/null | cut -d' ' -f1)" >> Packages
            echo "SHA256: $(shasum -a 256 "$deb" 2>/dev/null | cut -d' ' -f1)" >> Packages
            echo "" >> Packages
        done

        # 压缩 Packages 文件
        gzip -c Packages > Packages.gz
        bzip2 -k Packages

        echo "✅ Rootful 包处理完成"
    fi
fi

# 处理 rootless 版本
if [ -d "$DEBS_DIR/rootless" ] && [ "$(ls -A $DEBS_DIR/rootless 2>/dev/null)" ]; then
    echo "📦 处理 rootless 包..."

    # 复制所有 deb 包
    cp -r "$DEBS_DIR/rootless/"*.deb "$OUTPUT_DIR/rootless/" 2>/dev/null || true

    # 生成 Packages 文件
    cd "$OUTPUT_DIR/rootless"
    if ls *.deb 1> /dev/null 2>&1; then
        dpkg-scanpackages --multiversion . /dev/null > Packages 2>/dev/null || \
        for deb in *.deb; do
            echo "处理 $deb..."
            dpkg-deb -I "$deb" >> Packages
            echo "Filename: ./$(basename $deb)" >> Packages
            echo "Size: $(stat -f%z "$deb" 2>/dev/null || stat -c%s "$deb")" >> Packages
            echo "MD5sum: $(md5 -q "$deb" 2>/dev/null || md5sum "$deb" | cut -d' ' -f1)" >> Packages
            echo "SHA1: $(shasum -a 1 "$deb" 2>/dev/null | cut -d' ' -f1)" >> Packages
            echo "SHA256: $(shasum -a 256 "$deb" 2>/dev/null | cut -d' ' -f1)" >> Packages
            echo "" >> Packages
        done

        # 压缩 Packages 文件
        gzip -c Packages > Packages.gz
        bzip2 -k Packages

        echo "✅ Rootless 包处理完成"
    fi
fi

# 生成 Release 文件
cd "$OUTPUT_DIR"

# Rootful Release
cat > Release << EOF
Origin: MyTweak Repository
Label: MyTweak Repository
Suite: stable
Codename: ios
Architectures: iphoneos-arm iphoneos-arm64
Components: main
Description: iOS 插件源 - 支持 rootful 和 rootless
EOF

# 计算校验和
if [ -f "rootful/Packages" ]; then
    cat >> Release << EOF

MD5Sum:
 $(md5 -q rootful/Packages 2>/dev/null || md5sum rootful/Packages | cut -d' ' -f1) $(stat -f%z rootful/Packages 2>/dev/null || stat -c%s rootful/Packages) rootful/Packages
 $(md5 -q rootful/Packages.gz 2>/dev/null || md5sum rootful/Packages.gz | cut -d' ' -f1) $(stat -f%z rootful/Packages.gz 2>/dev/null || stat -c%s rootful/Packages.gz) rootful/Packages.gz
 $(md5 -q rootful/Packages.bz2 2>/dev/null || md5sum rootful/Packages.bz2 | cut -d' ' -f1) $(stat -f%z rootful/Packages.bz2 2>/dev/null || stat -c%s rootful/Packages.bz2) rootful/Packages.bz2
SHA1:
 $(shasum -a 1 rootful/Packages 2>/dev/null | cut -d' ' -f1) $(stat -f%z rootful/Packages 2>/dev/null || stat -c%s rootful/Packages) rootful/Packages
 $(shasum -a 1 rootful/Packages.gz 2>/dev/null | cut -d' ' -f1) $(stat -f%z rootful/Packages.gz 2>/dev/null || stat -c%s rootful/Packages.gz) rootful/Packages.gz
 $(shasum -a 1 rootful/Packages.bz2 2>/dev/null | cut -d' ' -f1) $(stat -f%z rootful/Packages.bz2 2>/dev/null || stat -c%s rootful/Packages.bz2) rootful/Packages.bz2
SHA256:
 $(shasum -a 256 rootful/Packages 2>/dev/null | cut -d' ' -f1) $(stat -f%z rootful/Packages 2>/dev/null || stat -c%s rootful/Packages) rootful/Packages
 $(shasum -a 256 rootful/Packages.gz 2>/dev/null | cut -d' ' -f1) $(stat -f%z rootful/Packages.gz 2>/dev/null || stat -c%s rootful/Packages.gz) rootful/Packages.gz
 $(shasum -a 256 rootful/Packages.bz2 2>/dev/null | cut -d' ' -f1) $(stat -f%z rootful/Packages.bz2 2>/dev/null || stat -c%s rootful/Packages.bz2) rootful/Packages.bz2
EOF
fi

# 复制 rootless Release
cp Release rootless/ 2>/dev/null || true

echo ""
echo "🎉 构建完成！"
echo "📂 输出目录: $OUTPUT_DIR"
echo ""
echo "请查看生成的文件并部署到 GitHub Pages"
