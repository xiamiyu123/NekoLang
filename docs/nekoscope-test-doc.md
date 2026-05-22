# NekoScope 测试文档

本文说明 NekoScope 当前前端、主进程和打包脚本的测试范围。编译器后端 API 和序列化层测试见仓库根目录 `tests/`，例如 `tests/test_viz_api.py`、`tests/test_viz_serializers.py`、`tests/test_quadruple_optimizer.py`。

## 测试技术栈

| 工具 | 用途 |
|------|------|
| `vitest` | TypeScript 单元测试运行器 |
| `@testing-library/react` | React 组件渲染和 DOM 查询 |
| `@testing-library/user-event` | 用户交互模拟 |
| `@testing-library/jest-dom` | DOM 断言扩展 |
| `jsdom` | 浏览器环境模拟 |

## 运行测试

```bash
cd nekoscope
npm test
npm run test:watch
```

CI 会在 Linux、macOS ARM64 和 Windows 上运行 `npm test`，并继续执行 `npm run build`、`npm run pack` 与内置 `uv` 检查。

## 测试文件清单

当前共有 14 个测试文件、77 个测试用例。

| 文件 | 测试数 | 覆盖范围 |
|------|--------|----------|
| `src/main/__tests__/lifecycle.test.ts` | 6 | Electron 主进程生命周期、FastAPI 启停、macOS 窗口重开行为 |
| `src/renderer/__tests__/App.test.tsx` | 5 | 编译错误展示、源码区键盘缩放、阶段说明折叠、概览跳转、运行动作 |
| `src/renderer/api/__tests__/client.test.ts` | 10 | `/compile`、`/run`、示例列表、示例源码、后端错误透传、DAG 示例兜底 |
| `src/renderer/components/__tests__/ASTPanel.test.tsx` | 10 | AST/CST 转 React Flow、Terminal 叶子样式、AST/CST 切换、全貌弹窗 |
| `src/renderer/components/__tests__/AssemblyPanel.test.tsx` | 4 | 汇编文本、后端选择器、空状态、后端切换回调 |
| `src/renderer/components/__tests__/QuadrupleDagPanel.test.tsx` | 9 | DAG 节点/边转换、交换律操作数排序、别名排序、空块、全貌弹窗 |
| `src/renderer/components/__tests__/QuadruplePanel.test.tsx` | 7 | 四元式表格、优化过程/结果切换、DAG 内嵌、前端 DAG 兜底、活跃信息 |
| `src/renderer/components/__tests__/SourceWorkbench.test.tsx` | 3 | Monaco 自动布局、编译/运行按钮、示例条中的 DAG 优化样例 |
| `src/renderer/components/__tests__/StageGuide.test.tsx` | 2 | 阶段标签、产物名称、阶段选择 |
| `src/renderer/components/__tests__/SymbolTablePanel.test.tsx` | 2 | 标识符/常量池展示、空状态 |
| `src/renderer/components/__tests__/TabBar.test.tsx` | 3 | 标签渲染、活跃态、切换回调 |
| `src/renderer/components/__tests__/TokenPanel.test.tsx` | 4 | token 类型和值、行列号、空列表、未编译提示 |
| `src/scripts/dev.test.ts` | 4 | 开发脚本跨平台启动、环境变量清理、参数透传、本地 bin 解析 |
| `src/scripts/package.test.ts` | 8 | 发布版本生成、参数透传、electron-builder bin 解析、内置 `uv` 路径和文件名 |

## 关键回归点

### 语法树

`ASTPanel` 默认展示抽象 AST。传入 `syntaxTree` 后，用户可切换到“精确语法树”，看到括号、关键字、运算符、标识符和字面量等 `Terminal` 叶子。全貌弹窗跟随当前模式展示。

### 四元式优化

`QuadruplePanel` 覆盖初始四元式、优化过程、优化结果和活跃信息。优化过程会区分本阶段删除行、改写行和阶段输出；DAG 数据缺失时，前端可以用四元式构造基础展示。

### DAG 展示

`QuadrupleDagPanel` 覆盖基本块选择、空块过滤、全貌弹窗，以及与后端一致的交换律操作数排序：常量优先，命名变量其次，临时变量最后。

### 主进程与打包脚本

主进程测试关注 FastAPI 后端是否随窗口生命周期正确启动和关闭。脚本测试关注跨平台命令启动和打包前复制 `uv`，避免在 Windows 或打包 CI 中依赖 POSIX-only shell 行为。

## 与 Python 测试的分工

NekoScope 前端测试只断言 UI 和 TypeScript 数据转换。编译器真实行为由 Python 测试负责：

| Python 测试 | 覆盖范围 |
|-------------|----------|
| `tests/test_viz_serializers.py` | 编译产物 JSON 字段、CST、DAG、优化步骤、活跃信息 |
| `tests/test_quadruple_optimizer.py` | 常量折叠、公共子表达式消除、死临时赋值删除 |
| `tests/test_viz_api.py` | FastAPI 端点、项目模式、运行接口 |
| `tests/test_llvm.py` / `tests/test_arm64.py` | 目标代码生成和真实编译运行 |

## CI 中的 NekoScope 检查

主 CI 的 `NekoScope compatibility` job 在三大平台执行：

```bash
npm ci
node ./scripts/dev.mjs --help
npm test
npm run build
npm run pack
```

随后检查打包目录内存在可执行的内置 `uv`。发布工作流 `.github/workflows/nekoscope-package.yml` 会在测试通过后执行 `npm run dist`，生成 Linux、macOS ARM64 和 Windows 安装包。
