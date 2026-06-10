# iOS Tweak Repository

只支持 rootful 的 iOS 插件源

## 添加源

在 Cydia/Sileo 中添加以下地址：

```
https://YOUR_USERNAME.github.io/mytweak/
```

## 目录结构

```
.
├── debs/              # deb 包存放目录
│   └── *.deb         # rootful 版本包
├── scripts/          # 构建脚本
│   └── build.sh      # 自动生成 Packages 文件
├── .github/
│   └── workflows/
│       └── deploy.yml # GitHub Actions 部署配置
└── README.md
```

## 添加新插件

1. 将编译好的 rootful deb 包放入 `debs/` 目录
2. 运行 `bash scripts/build.sh` 生成索引文件
3. 提交并推送到 GitHub，自动触发部署

## 本地测试

```bash
cd scripts
./build.sh
```

然后在 `gh-pages` 分支查看生成的文件。
