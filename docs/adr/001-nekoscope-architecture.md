# ADR-001: NekoScope 架构决策

## 状态

已接受

## 日期

2026-05-13

## 背景

NekoLang 是一个教学用途的编译语言，需要一个可视化工具帮助学生理解编译管线各阶段的数据变换。该工具需要模仿 Compiler Explorer (godbolt.org) 的思路，但更贴合 NekoLang 的设计语言和实际编译管线。

## 决策

### 1. 核心形态：管线视图 + Godbolt 对比

**选择**：默认多面板管线视图（横向排列各阶段），双击某阶段可放大为 Godbolt 式左右对比视图。

**理由**：教学场景下，学生需要看到数据在阶段之间的流动和变换，而不是只看首尾两端。管线视图能直观展示"源码 → Tokens → AST → 汇编"的完整变换链。Godbolt 对比视图作为补充，用于深入观察某两个阶段之间的精确映射。

**替代方案**：
- 纯 Godbolt 风格（左右两栏）：只能看首尾，缺少中间阶段的教学信息
- 纯管线视图：无法做精确的行间映射对比

### 2. 部署形态：Electron 桌面应用

**选择**：Electron 桌面应用，内嵌 Web 前端。

**理由**：Electron 结合了 Web 前端的交互丰富性和桌面应用的独立性。Monaco Editor（VSCode 编辑器核心）、react-flow（AST 树形图）、react-mosaic（面板布局）等 Web 生态库可以直接使用。同时桌面应用避免了浏览器安全限制和部署服务器的复杂性。

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
- react-mosaic 用于 VSCode 风格的面板布局
- 代码高亮、行间映射等需求有丰富的社区方案

**替代方案**：
- Vue：对国内开发者友好，但可视化库生态略逊
- Svelte：轻量高效，但生态最小，特殊需求需自造轮子

### 5. AST 可视化：react-flow 交互式树形图

**选择**：用 react-flow 绘制 AST 节点-连线图，支持缩放、拖拽、点击展开/折叠。

**理由**：AST 是树形结构，react-flow 的节点-连线模型天然适合。支持交互操作（缩放、拖拽、折叠），节点可以自定义渲染（显示类型、值、源码位置）。视觉上最直观，学生能一眼看到树结构和父子关系。

**替代方案**：
- 可折叠缩进树（类似 JSON 树）：实现简单，但不如图形直观
- d3.js 自定义渲染：灵活性最高，但开发成本大

### 6. 视觉设计：全面猫咪主题

**选择**：全面猫咪化设计语言——圆角猫耳面板、粉色/紫色配色、猫咪插画、猫爪印动画。

**理由**：NekoLang 的核心特色是猫咪主题关键字（nya、meow、purr），可视化工具应延续这一设计语言。在教学场景下，有辨识度的设计能让学生对编译过程形成更强的记忆锚点。

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

### 9. Python 环境：要求用户预装

**选择**：应用启动时检测系统 Python 版本，缺少时弹窗引导安装。

**理由**：教学场景下学生通常已装 Python（课程前置条件），且 `uv` 可以一键配环境。打包体积最小（~100MB vs 内嵌 Python 的 ~300-500MB）。

**替代方案**：
- PyInstaller 内嵌 Python：零依赖，但打包体积大，llvmlite C 扩展打包易出问题
- Docker：环境一致，但 Docker Desktop 对学生是额外负担

## 影响

### 编译器改动

需要在 `neko/` 包中添加：

1. `neko/viz_serializers.py` — Token、AST、Error 的 JSON 序列化层
2. `neko/viz_api.py` — FastAPI 应用，暴露 `/api/compile`、`/api/tokens`、`/api/ast`、`/api/assembly` 等端点

编译器核心模块（lexer、parser、semantic、codegen）不需要修改。

### 新增目录

```
nekoscope/          # Electron + React 前端
├── package.json
├── electron/       # Electron 主进程
├── src/            # React 应用源码
└── assets/         # Logo、猫咪插画等静态资源
```

### 依赖

- Python 端：新增 `fastapi` + `uvicorn` 依赖
- Node 端：`electron`、`react`、`@monaco-editor/react`、`reactflow`、`react-mosaic`
