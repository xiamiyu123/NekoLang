# NekoScope 实现路线图

## 总体策略

分阶段迭代，每阶段独立可用。先搭骨架，再填功能。

---

## P0：MVP 四面板（目标：4-6 周）

### 第 1 周：项目骨架 + API

#### 1.1 初始化 Electron + React 项目

```bash
mkdir nekoscope
cd nekoscope
npm init
npm install electron vite @vitejs/plugin-react react react-dom
npm install typescript @types/react @types/react-dom
npm install @monaco-editor/react reactflow react-mosaic
```

- [ ] 配置 Vite + React + TypeScript
- [ ] 配置 Electron 主进程 (`electron/main.ts`)
- [ ] 配置预加载脚本 (`electron/preload.ts`)
- [ ] 实现最小 Electron 窗口，加载 React 页面
- [ ] 验证 `npm run dev` 可启动 Electron 窗口

#### 1.2 实现 FastAPI 数据序列化层

在 `neko/viz_serializers.py` 中：

- [ ] `serialize_token(token) -> dict` — Token → `{ type, value, line, col }`
- [ ] `serialize_ast(node) -> dict` — ASTNode → 递归 JSON 树
- [ ] `serialize_error(error) -> dict` — NekoError → `{ stage, message, line, col, suggestion }`
- [ ] `serialize_quadruples(analyzer) -> list[dict]` — Quadruple → `{ index, op, arg1, arg2, result }`
- [ ] `serialize_symbol_table(table) -> list[dict]` — SymbolTable → `[{ name, type, cat, addr }]`

#### 1.3 实现 FastAPI 服务

在 `neko/viz_api.py` 中：

- [ ] `POST /api/compile` — 完整编译，返回所有阶段数据
- [ ] `POST /api/tokens` — 只返回 Token 列表
- [ ] `POST /api/ast` — 只返回 AST
- [ ] `POST /api/assembly` — 只返回汇编（支持 `backend` 参数）
- [ ] `GET /api/examples` — 返回内置示例列表
- [ ] `GET /api/examples/{name}` — 返回示例源码
- [ ] CORS 配置（允许 Electron 前端访问）
- [ ] 启动时自动找空闲端口，将端口号写入临时文件供 Electron 读取

#### 1.4 Electron 主进程集成 Python

- [ ] Electron 启动时 spawn FastAPI 子进程
- [ ] 等待 Python 服务就绪（轮询 health check）
- [ ] 读取端口号，传递给前端
- [ ] Electron 退出时 kill Python 子进程
- [ ] 错误处理：Python 未安装时弹窗提示

### 第 2 周：前端框架 + 源码面板

#### 2.1 猫咪主题基础

- [ ] 设计色板：主色（粉/紫）、暗色背景、高亮色
- [ ] CSS 变量 / styled-components 主题系统
- [ ] 猫耳圆角面板组件 (`NekoPanel`)
- [ ] Logo SVG（猫耳编译器图标）

#### 2.2 面板布局

- [ ] 使用 react-mosaic 实现可拖拽面板布局
- [ ] 四个面板槽位：源码、Tokens、AST、Assembly
- [ ] 面板标题栏：阶段名称 + 猫咪图标
- [ ] 面板可最大化/最小化/关闭

#### 2.3 源码面板

- [ ] 集成 Monaco Editor (`@monaco-editor/react`)
- [ ] 配置 `.neko` 语法高亮（基于关键字列表）
- [ ] 侧边栏示例列表
- [ ] 点击示例加载到编辑器
- [ ] 编辑器内容变化 → 500ms debounce → 调用 `/api/compile`

### 第 3 周：Tokens + Assembly 面板

#### 3.1 Tokens 面板

- [ ] Token 卡片组件：类型标签 + 值 + 行号
- [ ] 颜色区分：关键字（紫）、标识符（蓝）、字面量（绿）、运算符（橙）、分隔符（灰）
- [ ] 滚动容器，Token 数量多时可滚动
- [ ] 点击 Token 高亮源码对应位置

#### 3.2 Assembly 面板

- [ ] 代码高亮渲染（使用 Monaco readonly 模式或 Prism.js）
- [ ] 顶部下拉切换 ARM64 / LLVM IR
- [ ] 默认根据平台自动选择
- [ ] 行号显示

### 第 4 周：AST 面板

#### 4.1 AST 数据结构适配

- [ ] 设计 AST 的 react-flow 节点格式
- [ ] 实现 `ast_to_flow(ast) -> { nodes, edges }` 转换函数
- [ ] 节点类型映射：ProgramNode → 紫色、BinOpNode → 橙色、LiteralNode → 绿色等

#### 4.2 AST 树形图

- [ ] react-flow 基础集成
- [ ] 自定义节点组件：显示节点类型 + 值
- [ ] 自动布局（dagre 或 elkjs）
- [ ] 缩放 + 拖拽
- [ ] 点击节点折叠/展开子树
- [ ] 点击节点高亮源码对应位置

### 第 5 周：高亮映射 + 错误处理

#### 5.1 单向高亮映射

- [ ] 定义 `SourceLocation { line, col, endLine, endCol }` 类型
- [ ] 各阶段数据携带源码位置信息
- [ ] 点击源码行 → 计算对应 Token 范围 → 高亮
- [ ] 点击源码行 → 计算对应 AST 节点 → 高亮
- [ ] 点击源码行 → 计算对应 Assembly 行 → 高亮

#### 5.2 错误定位

- [ ] 错误卡片组件：红色背景、猫咪表情、错误信息、建议
- [ ] 编译失败时，错误阶段面板显示错误卡片
- [ ] 后续阶段面板显示"因 XX 阶段错误而终止"
- [ ] 源码编辑器红色波浪线标记出错位置

### 第 6 周：打磨 + 测试

- [ ] 动画过渡：面板间切换的过渡效果
- [ ] 猫爪印加载动画
- [ ] 响应式布局适配
- [ ] 快捷键支持（Ctrl+O 打开文件、Ctrl+S 保存等）
- [ ] 内置示例程序完善（至少 8 个覆盖各语言特性的示例）
- [ ] 端到端测试：启动 Electron → 加载示例 → 验证四个面板内容

---

## P1：双向映射 + 逐步动画（目标：3-4 周）

### 双向映射

- [ ] 各阶段数据携带 `sourceLocation` 字段
- [ ] 点击 Token → 高亮源码 + AST 节点 + Assembly 行
- [ ] 点击 AST 节点 → 高亮源码 + Token + Assembly 行
- [ ] 点击 Assembly 行 → 高亮源码 + AST 节点
- [ ] 高亮样式：选中项高亮 + 关联项半透明高亮

### 逐步动画

- [ ] "Step" 按钮组件
- [ ] 状态机：`idle → lexing → parsing → semantic → codegen → done`
- [ ] 每步触发对应面板的数据流入动画
- [ ] 源码面板高亮当前正在处理的代码行
- [ ] 支持"Reset"回到初始状态

### Symbol Table 面板

- [ ] 表格组件：Name、Type、Category、Address 列
- [ ] 作用域用缩进/颜色区分（全局作用域 vs 函数作用域）
- [ ] 点击符号高亮源码声明位置

---

## P2：Quads + 优化对比（目标：3-4 周）

### Quads 面板

- [ ] 表格组件：Index、Operator、Arg1、Arg2、Result 列
- [ ] 地址标注颜色区分（变量 I、临时 T、常量 C）
- [ ] 点击四元式高亮对应 AST 节点

### 优化对比

- [ ] 优化前后 AST 并排显示
- [ ] 高亮变化节点（常量折叠、指令合并等）
- [ ] Diff 模式：只显示有变化的子树

---

## P3：多文件支持（目标：2-3 周）

- [ ] 多文件编辑器（标签页切换）
- [ ] Import 解析可视化：显示依赖图
- [ ] 合并前后的 AST 对比
- [ ] Extern 声明展示面板

---

## P4：高级教学功能（目标：4-6 周）

- [ ] 录屏回放：记录编译过程，支持播放/暂停/回放
- [ ] Quick Fix：错误修复建议一键应用
- [ ] 课堂模式：教师广播代码，学生实时看到编译结果
- [ ] 编译性能分析面板：各阶段耗时统计
