#!/bin/bash
set -e

echo "🔨 生成标准 Packages 文件..."

# 生成 Packages
dpkg-scanpackages -m debs > Packages

# 生成压缩文件
echo "🗜️  生成压缩文件..."
bzip2 -c9 Packages > Packages.bz2
xz -c9 Packages > Packages.xz
gzip -c9 Packages > Packages.gz

# 更新 Release 文件
echo "📝 更新 Release 文件..."
PACKAGES_MD5=$(md5 -q Packages)
PACKAGES_SHA1=$(shasum -a 1 Packages | cut -d' ' -f1)
PACKAGES_SHA256=$(shasum -a 256 Packages | cut -d' ' -f1)
PACKAGES_BZ2_MD5=$(md5 -q Packages.bz2)
PACKAGES_BZ2_SHA1=$(shasum -a 1 Packages.bz2 | cut -d' ' -f1)
PACKAGES_BZ2_SHA256=$(shasum -a 256 Packages.bz2 | cut -d' ' -f1)
PACKAGES_XZ_MD5=$(md5 -q Packages.xz)
PACKAGES_XZ_SHA1=$(shasum -a 1 Packages.xz | cut -d' ' -f1)
PACKAGES_XZ_SHA256=$(shasum -a 256 Packages.xz | cut -d' ' -f1)
PACKAGES_GZ_MD5=$(md5 -q Packages.gz)
PACKAGES_GZ_SHA1=$(shasum -a 1 Packages.gz | cut -d' ' -f1)
PACKAGES_GZ_SHA256=$(shasum -a 256 Packages.gz | cut -d' ' -f1)

cat > Release << EOF
Origin: fengyn
Label: MyTweak Repository
Suite: stable
Version: 1.0
Codename: ios
Architectures: iphoneos-arm iphoneos-arm64
Components: main
Description: iOS 插件源 - 支持 Rootless & Rootful
Date: $(date -u +"%a, %d %b %Y %H:%M:%S UTC")

MD5Sum:
 ${PACKAGES_MD5} $(stat -f%z Packages) Packages
 ${PACKAGES_BZ2_MD5} $(stat -f%z Packages.bz2) Packages.bz2
 ${PACKAGES_XZ_MD5} $(stat -f%z Packages.xz) Packages.xz
 ${PACKAGES_GZ_MD5} $(stat -f%z Packages.gz) Packages.gz
SHA1:
 ${PACKAGES_SHA1} $(stat -f%z Packages) Packages
 ${PACKAGES_BZ2_SHA1} $(stat -f%z Packages.bz2) Packages.bz2
 ${PACKAGES_XZ_SHA1} $(stat -f%z Packages.xz) Packages.xz
 ${PACKAGES_GZ_SHA1} $(stat -f%z Packages.gz) Packages.gz
SHA256:
 ${PACKAGES_SHA256} $(stat -f%z Packages) Packages
 ${PACKAGES_BZ2_SHA256} $(stat -f%z Packages.bz2) Packages.bz2
 ${PACKAGES_XZ_SHA256} $(stat -f%z Packages.xz) Packages.xz
 ${PACKAGES_GZ_SHA256} $(stat -f%z Packages.gz) Packages.gz
EOF

echo "✅ 完成！"
echo ""
echo "📊 包统计:"
echo "  架构: $(grep "^Architecture:" Packages | sort -u | wc -l | tr -d ' ')"
echo "  包数: $(grep "^Package:" Packages | wc -l | tr -d ' ')"
echo ""
echo "📦 架构详情:"
grep -A 1 "^Architecture:" Packages | grep -E "^(Package|Version|Architecture):" | paste - - | column -t
