# NekoScope 打包

NekoScope 使用 `electron-vite` 构建前端和主进程，使用 `electron-builder` 生成 Electron 应用包。

## 本地打包

```bash
cd nekoscope
npm ci
npm run pack
```

`npm run pack` 会生成未压缩的应用目录，适合本地快速检查。

```bash
cd nekoscope
npm run dist
```

`npm run dist` 会生成可分发的安装包，输出目录为 `nekoscope/release/`。

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
- `uv.lock`

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
