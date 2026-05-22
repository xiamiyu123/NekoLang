# ADR-001: NekoScope 架构决策

## 状态

已接受

## 日期

2026-05-13

## 背景

NekoLang 是一个教学用途的编译语言，需要一个可视化工具帮助学生理解编译管线各阶段的数据变换。该工具借鉴 Compiler Explorer 的阶段对照思路，但更贴合 NekoLang 的设计语言和实际编译管线。

## 决策

### 1. 核心形态：源码工作区 + 阶段教学面板

**选择**：默认源码工作区 + 阶段导航 + 单阶段教学面板。语法树和 DAG 等图形视图在面板内提供全貌弹窗。

**理由**：教学场景下，学生需要按阶段理解数据变换。当前实现把源码编辑、编译/运行、工作区文件树放在左侧，把阶段说明和当前产物放在右侧，避免多个大型可视化面板同时挤在一个窗口里。AST、CST、DAG 这类图形产物可通过全貌弹窗放大查看。

**替代方案**：
- 纯左右对比风格：只能看首尾，缺少中间阶段的教学信息
- 同屏展示全部阶段：信息密度过高，AST/DAG 这类图形容易过小

### 2. 部署形态：Electron 桌面应用

**选择**：Electron 桌面应用，内嵌 Web 前端。

**理由**：Electron 结合了 Web 前端的交互丰富性和桌面应用的独立性。Monaco Editor（VSCode 编辑器核心）和 React Flow（AST、CST、DAG 图）可以直接使用。同时桌面应用避免了浏览器安全限制和部署服务器的复杂性。

**替代方案**：
- 纯 Web 应用：需要部署服务器，学生需要网络连接
- 本地 GUI (PyQt/Tkinter)：Python GUI 生态的可视化库远不如 Web 生态丰富
- CLI + 生成 HTML：交互性受限，无法实时编译

### 3. Python-Node 桥接：FastAPI HTTP 子进程

**选择**：Electron 启动时内嵌一个 FastAPI HTTP 服务（localhost），前端通过 HTTP API 调用编译管线。

**理由**：FastAPI 可以直接 `import neko.*` 复用现有编译器模块，返回结构化 JSON 数据。不需要解析 CLI 文本输出，也不需要在编译器中添加 IPC 机制。HTTP 协议调试直观（浏览器 DevTools、Postman），且 FastAPI 自动生成 OpenAPI 文档。

**替代方案**：
- 子进程调用 CLI (`child_process`)：需要多次调用不同命令解析文本输出，无法共享编译状态
- JSON-RPC via stdin/stdout：比 HTTP 轻量，但调试不如 HTTP 直观

### 4. 前端框架：React

**选择**：React + TypeScript

**理由**：
- Monaco Editor 有成熟的 React 封装 (`@monaco-editor/react`)
- react-flow 用于 AST 交互式树形图
- React 组件和 CSS Grid 管理源码区、阶段区和弹窗布局
- 代码高亮、行间映射等需求有丰富的社区方案

**替代方案**：
- Vue：对国内开发者友好，但可视化库生态略逊
- Svelte：轻量高效，但生态最小，特殊需求需自造轮子

### 5. AST 可视化：react-flow 交互式树形图

**选择**：用 React Flow 绘制 AST、CST 和四元式 DAG 的节点-连线图，支持缩放、拖拽和全貌查看。

**理由**：AST、CST 和 DAG 都适合用节点-连线模型展示。React Flow 支持交互操作和自定义节点，配合 dagre 自动布局后，学生能直观看到树结构、终结符叶子和公共子表达式复用关系。

**替代方案**：
- 可折叠缩进树（类似 JSON 树）：实现简单，但不如图形直观
- d3.js 自定义渲染：灵活性最高，但开发成本大

### 6. 视觉设计：全面猫咪主题

**选择**：保留猫咪主题，但提供 light/dark/neko 三套主题偏好。

**理由**：NekoLang 的核心特色是猫咪主题关键字（nya、meow、purr），可视化工具应延续这一设计语言。同时编译产物阅读需要较高对比度，所以默认提供深色/浅色可切换主题，猫猫模式作为个性化选择。

**替代方案**：
- 极简专业 + 猫咪点缀：平衡方案，但辨识度不够强
- 纯专业风格：最清晰，但失去 NekoLang 特色

### 7. 后端切换：ARM64/LLVM 双后端

**选择**：Assembly 面板顶部下拉切换 ARM64 Assembly / LLVM IR，默认根据平台自动选择。

**理由**：NekoLang 有两个代码生成后端，各有教学价值——LLVM IR 更适合教学 SSA 和中端优化概念，ARM64 更贴近"真实机器码"。双后端切换让学生可以对比两种后端的输出差异。

### 8. 项目结构：Monorepo

**选择**：NekoScope 代码放在 NekoLang 仓库内的 `nekoscope/` 目录，Python API 模块放在 `neko/viz_api.py`。

**理由**：编译器和可视化工具紧密耦合——前端直接调用编译器模块获取各阶段数据。拆仓库会导致版本同步和依赖管理的额外负担。Monorepo 让编译器改动可以立即在可视化工具中验证。

**替代方案**：
- 独立仓库：干净分离，但跨仓库开发调试麻烦

### 9. Python 环境：开发依赖系统 uv，打包依赖内置 uv

**选择**：开发模式直接调用系统 `uv`；打包模式把 `uv` 可执行文件复制到 Electron resources，并用它在应用数据目录中创建后端虚拟环境。

**理由**：`uv` 可以按 `pyproject.toml` 管理 Python 环境，不需要追踪 `uv.lock`。打包应用不再要求目标机器的 `PATH` 中有 `uv`，同时避免把完整 Python 解释器和依赖预打进安装包。

**替代方案**：
- PyInstaller 内嵌 Python：零依赖，但打包体积大，llvmlite C 扩展打包易出问题
- Docker：环境一致，但 Docker Desktop 对学生是额外负担

## 影响

### 编译器改动

需要在 `neko/` 包中添加：

1. `neko/viz_serializers.py` — Token、AST、Error 的 JSON 序列化层
2. `neko/viz_api.py` — FastAPI 应用，暴露 `/api/compile`、`/api/run`、`/api/workspace/*` 等端点
3. `neko/syntax_tree.py`、`neko/dag.py`、`neko/quadruple_optimizer.py`、`neko/quadruple_liveness.py` — CST、DAG、优化过程和活跃信息展示产物

编译器核心模块（lexer、parser、semantic、codegen）仍是真实编译链路；NekoScope 的优化与活跃信息目前只用于教学展示。

### 新增目录

```
nekoscope/          # Electron + React 前端
├── package.json
├── scripts/        # dev/pack 脚本，打包时复制 uv
└── src/
    ├── main/       # Electron 主进程
    ├── preload/    # 安全 IPC 暴露
    └── renderer/   # React 应用源码
```

### 依赖

- Python 端：新增 `fastapi` + `uvicorn` 依赖
- Node 端：`electron`、`react`、`@monaco-editor/react`、`reactflow`、`dagre`、`lucide-react`
