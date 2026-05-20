# NekoScope 打包

NekoScope 使用 `electron-vite` 构建前端和主进程，使用 `electron-builder` 生成 Electron 应用包。

## 本地打包

首次打包前安装 NekoScope 的 Node 依赖：

```bash
cd nekoscope
npm ci
```

生成未压缩的应用目录：

```bash
npm run pack
```

`npm run pack` 适合本地快速检查，输出目录固定在 `nekoscope/release/`。按平台不同，常见产物位置为：

- macOS ARM64：`nekoscope/release/mac-arm64/NekoScope.app`
- macOS x64：`nekoscope/release/mac/NekoScope.app`
- Linux x64：`nekoscope/release/linux-unpacked/`
- Windows x64：`nekoscope/release/win-unpacked/`

在 macOS 上可以直接运行：

```bash
open release/mac-arm64/NekoScope.app
```

也可以从终端启动以查看主进程日志：

```bash
release/mac-arm64/NekoScope.app/Contents/MacOS/NekoScope
```

如果只是想确认后端运行时已经打进包，可以检查：

```bash
test -x release/mac-arm64/NekoScope.app/Contents/Resources/bin/uv
```

生成可分发安装包：

```bash
cd nekoscope
npm run dist
```

`npm run dist` 同样输出到 `nekoscope/release/`，但会生成安装/分发文件，例如：

- Linux：`.AppImage` / `.deb`
- macOS：`.dmg` / `.zip`
- Windows：`.exe` / `.zip`

默认产物版本号使用当前 UTC 时间戳，精确到分钟，格式为 `yyyyMMddHHmm`。如需指定版本，可设置环境变量：

```bash
cd nekoscope
NEKOSCOPE_RELEASE_VERSION=202605132305 npm run dist
```

## 后端资源

打包配置会把以下资源复制到 Electron 的 `resources/backend/`：

- `neko/`
- `examples/`
- `runtime/`
- `pyproject.toml`

`npm run pack` / `npm run dist` 会先从当前 `PATH` 找到 `uv`，复制到 `nekoscope/resources/bin/`，再由 electron-builder 放入 Electron 的 `resources/bin/`。

应用启动后，主进程会在打包环境中从 `process.resourcesPath/backend` 调用内置的 `resources/bin/uv` 启动 `uv run uvicorn neko.viz_api:app`。打包后的应用不再要求目标机器的 `PATH` 能访问 `uv`；uv 的虚拟环境和缓存会写入应用的用户数据目录。

## 自动打包

GitHub Actions 工作流 `.github/workflows/nekoscope-package.yml` 支持：

- 手动触发 `workflow_dispatch`
- 推送 `nekoscope-v*` tag 时触发

工作流会在 Linux、macOS ARM64、Windows runner 上并行运行测试并生成安装包：

- Linux：`.AppImage` / `.deb`
- macOS：`.dmg` / `.zip`
- Windows：`.exe` / `.zip`

每个平台的产物都会作为 workflow artifact 保存，并上传到 GitHub Release。手动触发时，如果没有填写版本号，会使用当前 UTC 时间戳生成 `nekoscope-vyyyyMMddHHmm`；推送 `nekoscope-v*` tag 时，会使用 tag 中的版本号。
