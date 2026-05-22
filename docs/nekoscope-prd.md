# NekoScope — 编译管线可视化教学工具 PRD

> 历史规划文档：本文保留早期产品设想，用于理解 NekoScope 的设计来源。当前实现状态请以 [实现架构](architecture.md)、[NekoScope 打包](nekoscope-packaging.md)、[NekoScope 测试文档](nekoscope-test-doc.md) 和 [ADR-001](adr/001-nekoscope-architecture.md) 为准。

## 概述

NekoScope 是 NekoLang 的编译管线可视化教学工具。它以 Electron 桌面应用的形式，将 NekoLang 编译器的每个阶段（词法分析、语法分析、语义分析、代码生成）以交互式面板的形式呈现，帮助学生直观理解编译过程中的数据变换。

命名：NekoScope — "Scope" 既指编译器的作用域概念，也有"观察镜"的含义。

## 目标用户

- NekoLang 课程的学生：需要理解编译原理的初学者
- 课程教师：用于课堂演示编译过程

## 设计语言

全面猫咪主题设计语言：

- 圆角猫耳面板、粉色/紫色配色
- 暗色主题为主
- 阶段间过渡动画用猫爪印
- Logo：猫耳编译器图标
- 错误状态用猫咪表情
- Loading 用猫咪走路动画

## 架构

```
┌─────────────────────────────────────────────┐
│  Electron Shell                             │
│  ┌───────────────────────────────────────┐  │
│  │  React 前端                           │  │
│  │  Monaco Editor + react-flow           │  │
│  │  猫咪主题 UI · 面板布局               │  │
│  └──────────┬────────────────────────────┘  │
│             │ HTTP (localhost)               │
│  ┌──────────▼────────────────────────────┐  │
│  │  FastAPI 子进程                       │  │
│  │  直接 import neko.* 调用编译管线      │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### 技术栈

| 层 | 技术 | 理由 |
|---|------|------|
| 桌面壳 | Electron | 跨平台桌面应用，Web 技术栈 |
| 前端框架 | React | 生态成熟，可视化库丰富 |
| 代码编辑器 | Monaco Editor | VSCode 内核，语法高亮、自动补全 |
| AST 可视化 | react-flow | 交互式节点-连线图，支持缩放/拖拽 |
| 布局 | React 组件 + CSS Grid | 管理源码工作区、阶段面板和全貌弹窗 |
| 后端 API | FastAPI | Python 异步 HTTP 服务，自动 OpenAPI 文档 |
| 编译器 | neko.* 模块 | 直接复用现有编译管线，零重复实现 |
| Python 环境 | 开发模式系统 `uv`，打包模式内置 `uv` | 依赖由 `pyproject.toml` 创建，不追踪 `uv.lock` |

## 核心功能

### 1. 阶段视图（默认视图）

当前实现采用源码工作区 + 阶段导航 + 单阶段教学面板，每个阶段展示编译管线的一个产物：

| 面板 | 数据来源 | 可视化方式 |
|------|----------|-----------|
| 源码 | 用户输入 | Monaco Editor，内置示例库 |
| Tokens | `Lexer.tokenize()` | Token 卡片列表，颜色区分类型 |
| AST / CST | `Parser.parse()` / `syntax_tree.py` | React Flow 交互式树形图 |
| Symbol Table | `SemanticAnalyzer.symbol_table` | 表格视图，作用域缩进区分 |
| Quads | `SemanticAnalyzer.dump_quadruples()` | 四元式表格、DAG、优化过程、活跃信息 |
| Assembly | `generate_assembly()` / `generate_ir()` | 代码高亮，下拉切换后端 |

### 2. 图形全貌视图

AST、CST 和 DAG 面板提供全貌弹窗，便于查看较大的图形产物。源码到产物的精确高亮映射仍属于后续增强。

### 3. 阶段间高亮映射

点击任意阶段的数据元素，高亮关联的上下游元素：

- **MVP（单向）**：点击源码 → 高亮对应 Token、AST 节点、汇编行
- **后续（双向）**：点击 Token/AST/汇编 → 回溯高亮源码和其他阶段

实现前置条件：编译器各阶段需携带源码位置信息（`SourceLocation`）。

### 4. 逐步动画模式

"Step" 按钮推进编译阶段，每次切换时：

- 源码面板高亮当前正在处理的代码行
- 对应阶段面板的数据以动画形式"流入"
- 类似调试器的 step-over 体验

### 5. 实时编译

编辑器内容变化后 500ms debounce 自动重新编译，刷新所有面板。

### 6. 错误定位

编译失败时：

- 错误发生的阶段面板显示红色错误卡片（中文错误信息 + 建议）
- 之前的阶段面板保留正常输出
- 后续阶段面板显示"因 XX 阶段错误而终止"
- 源码编辑器中用红色波浪线标记出错位置

### 7. 内置示例库

侧边栏提供教学示例程序，点击加载到编辑器：

- 基础：hello.neko、变量声明、条件判断
- 循环：fibonacci、阶乘
- 函数：递归、高阶函数
- 数据结构：数组操作
- 进阶：lambda、字符串操作

## 早期 MVP 范围（P0，历史）

第一版只做四个核心面板，覆盖"前端-中端-后端"三大编译阶段：

```
源码 → Tokens → AST → Assembly
```

具体功能：

- [ ] Electron 应用壳 + FastAPI 子进程
- [ ] Monaco Editor 代码输入 + 示例库加载
- [ ] Tokens 面板：Token 卡片列表，颜色区分类型
- [ ] AST 面板：React Flow 交互式树形图
- [ ] Assembly 面板：代码高亮，ARM64/LLVM IR 下拉切换
- [ ] 实时编译（500ms debounce）
- [ ] 单向高亮映射（源码 → 下游）
- [ ] 错误定位到阶段面板
- [ ] 猫咪主题 UI

不包含：

- 多文件项目（import/extern）
- 双向高亮映射
- 逐步动画
- Symbol Table 面板
- Quads 面板
- 优化对比

## API 设计

### FastAPI 端点

Python API 服务暴露以下 HTTP 端点，所有返回 JSON：

```
POST /api/compile
  Body: { "source": string, "backend": "arm64"|"llvm"|"auto" }
  Response: {
    "tokens": Token[],
    "ast": ASTNode (JSON tree),
    "assembly": string,
    "errors": Error[]
  }
```

```
POST /api/tokens
  Body: { "source": string }
  Response: { "tokens": Token[] }
```

```
POST /api/ast
  Body: { "source": string }
  Response: { "ast": ASTNode }
```

```
POST /api/assembly
  Body: { "source": string, "backend": "arm64"|"llvm" }
  Response: { "assembly": string }
```

```
POST /api/examples
  Response: { "examples": Example[] }
```

```
POST /api/examples/{name}
  Response: { "source": string }
```

### 数据序列化

`CompilationResult` 中的数据需要序列化为 JSON：

- **Token**：`{ type, value, line, col }`
- **ASTNode**：递归 JSON 树，每个节点包含 `{ type, children, location, ...properties }`
- **Error**：`{ stage, message, line, col, suggestion }`

需要在 `neko/` 包中添加序列化层，将现有数据结构转换为 JSON-safe 的 dict。

## 项目结构

```
NekoLang/
├── neko/                        # 现有编译器包
│   ├── viz_api.py               # 新增：FastAPI 可视化 API
│   ├── viz_serializers.py       # 新增：数据序列化（Token/AST → JSON）
│   └── ...                      # 现有模块
├── nekoscope/                   # 新增：Electron 前端
│   ├── package.json
│   ├── electron/
│   │   ├── main.ts              # Electron 主进程
│   │   └── preload.ts           # 预加载脚本
│   ├── src/
│   │   ├── App.tsx              # React 根组件
│   │   ├── components/
│   │   │   ├── PipelineView.tsx # 管线视图容器
│   │   │   ├── SourcePanel.tsx  # 源码编辑器面板
│   │   │   ├── TokenPanel.tsx   # Tokens 面板
│   │   │   ├── ASTPanel.tsx     # AST 树形图面板
│   │   │   ├── AssemblyPanel.tsx# 汇编面板
│   │   │   ├── ErrorCard.tsx    # 错误卡片组件
│   │   │   └── Sidebar.tsx      # 示例库侧边栏
│   │   ├── hooks/
│   │   │   └── useCompile.ts    # 编译 API hook
│   │   ├── api/
│   │   │   └── client.ts        # FastAPI 客户端
│   │   ├── styles/
│   │   │   └── neko-theme.ts    # 猫咪主题样式
│   │   └── types/
│   │       └── compiler.ts      # TypeScript 类型定义
│   ├── assets/
│   │   └── neko-logo.svg        # 猫耳编译器 Logo
│   └── vite.config.ts           # Vite 构建配置
└── docs/
    └── nekoscope-prd.md         # 本文档
```

## 长期路线图

### P0：早期 MVP

早期目标是源码、Tokens、AST、Assembly 四个核心视图 + 实时编译 + 单向映射 + 错误定位。当前实现已经扩展为源码工作区、阶段导航和单阶段教学面板。

### P1：双向映射 + 逐步动画

- 双向高亮映射（任意阶段间互相追踪）
- 逐步动画模式（Step 按钮推进编译阶段）
- Symbol Table 面板（表格视图，作用域缩进）

### P2：Quads + 优化对比

- Quads 面板（类汇编表格）
- 优化前后 AST 对比（并排显示常量折叠等变化）
- Diff 模式：高亮优化前后的差异节点

### P3：多文件支持

- 多文件输入（编辑多个 `.neko` 文件）
- Import 解析可视化（合并前后的 AST 对比）
- Extern 声明展示

### P4：高级教学功能

- 录屏回放整个编译过程
- Quick Fix 错误修复建议
- 课堂模式：教师广播代码，学生实时看到编译结果
- 编译性能分析面板（各阶段耗时）

## 验收标准

### MVP 验收标准

1. `npm run dev` 启动 NekoScope，自动启动 FastAPI 子进程
2. Monaco Editor 可编辑 `.neko` 代码，支持语法高亮
3. 内置示例库可点击加载
4. 编辑代码后 500ms 内自动编译，核心阶段视图同步更新
5. Tokens 面板显示颜色区分的 Token 列表
6. AST 面板显示可交互的树形图（缩放、拖拽、折叠）
7. Assembly 面板可切换 ARM64/LLVM IR
8. 编译错误在对应阶段面板显示红色错误卡片
9. 点击源码行高亮对应 Token 和 AST 节点
10. UI 符合猫咪主题设计语言
