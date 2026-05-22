# NekoScope 打包

NekoScope 使用 `electron-vite` 构建前端和主进程，使用 `electron-builder` 生成 Electron 应用包。

## 命令分层

| 命令 | 用途 | 是否打包 Electron |
|------|------|------------------|
| `npm run dev` | 本地开发，启动 Electron + Vite | 否 |
| `npm run build` | 只构建 `out/main`、`out/preload`、`out/renderer` | 否 |
| `npm run pack` | 生成未压缩应用目录，适合本地检查 | 是，`--dir` |
| `npm run dist` | 生成可分发安装包和压缩包 | 是 |

`pack` 和 `dist` 都会先运行 `nekoscope/scripts/package.mjs`。该脚本会从当前 `PATH` 查找 `uv`，复制到 `nekoscope/resources/bin/`，再调用 `electron-vite build` 和 `electron-builder`。

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

也可以检查后端代码资源：

```bash
test -d release/mac-arm64/NekoScope.app/Contents/Resources/backend/neko
test -f release/mac-arm64/NekoScope.app/Contents/Resources/backend/pyproject.toml
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

仓库不追踪 `uv.lock`，打包资源也不包含 `uv.lock`。后端依赖以 `pyproject.toml` 为准，由打包后的 `uv run` 在应用数据目录中创建或复用虚拟环境。

应用启动后，主进程会在打包环境中从 `process.resourcesPath/backend` 调用内置的 `resources/bin/uv` 启动 `uv run uvicorn neko.viz_api:app`。打包后的应用不再要求目标机器的 `PATH` 能访问 `uv`；uv 的虚拟环境和缓存会写入应用的用户数据目录。

打包模式下的关键路径：

| 内容 | 路径 |
|------|------|
| Python 后端源码 | `process.resourcesPath/backend` |
| 内置 uv | `process.resourcesPath/bin/uv` 或 `uv.exe` |
| uv 缓存 | Electron `userData/backend/uv-cache` |
| 后端虚拟环境 | Electron `userData/backend/.venv` |
| 运行产物 | `~/.nekoscope/runs/` |

NekoScope 的运行按钮不会在前端内嵌 stdout。后端会先编译到 `~/.nekoscope/runs/nekoscope-run`，Electron 再打开系统终端执行该文件。

## 自动打包

GitHub Actions 工作流 `.github/workflows/nekoscope-package.yml` 支持：

- 手动触发 `workflow_dispatch`
- 推送 `nekoscope-v*` tag 时触发

工作流会在 Linux、macOS ARM64、Windows runner 上并行运行测试并生成安装包：

- Linux：`.AppImage` / `.deb`
- macOS：`.dmg` / `.zip`
- Windows：`.exe` / `.zip`

每个平台的产物都会作为 workflow artifact 保存，并上传到 GitHub Release。手动触发时，如果没有填写版本号，会使用当前 UTC 时间戳生成 `nekoscope-vyyyyMMddHHmm`；推送 `nekoscope-v*` tag 时，会使用 tag 中的版本号。

## CI 兼容性检查

主 CI 中的 `NekoScope compatibility` job 会在 Linux、macOS ARM64、Windows 上执行：

1. `npm ci`
2. `node ./scripts/dev.mjs --help`
3. `npm test`
4. `npm run build`
5. `npm run pack`
6. 检查打包产物中存在内置 `uv`

Python 依赖安装使用 `uv sync --group dev`，不使用 `--frozen`，因为仓库不追踪 `uv.lock`。

## 常见问题

### 打包时报找不到 uv

确认当前 shell 能找到 `uv`：

```bash
uv --version
which uv
```

`scripts/package.mjs` 只会从 `PATH` 中复制当前平台的 `uv` 或 `uv.exe`。

### 后端启动失败

从终端直接运行应用，观察主进程输出的 `[FastAPI]` 日志。常见原因：

- 目标机器无法执行内置 `uv`
- `pyproject.toml` 与后端源码不匹配
- 端口 `8000` 被占用
- 目标机器缺少 `clang`，导致“运行”时无法链接可执行文件

### 构建产物进入工作区

`nekoscope/out/`、`nekoscope/release/`、`nekoscope/resources/` 和 `uv.lock` 都应保持 ignored 状态，不应提交。
