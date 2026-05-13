# NekoScope 前端测试文档

## 测试范围

覆盖 NekoScope Electron 前端（`nekoscope/`）的 React 组件单元测试和 API 客户端测试。

## 测试技术栈

- **vitest** — 测试运行器
- **@testing-library/react** — React 组件渲染与查询
- **@testing-library/user-event** — 用户交互模拟
- **@testing-library/jest-dom** — DOM 断言扩展
- **jsdom** — 浏览器环境模拟

## 运行测试

```bash
cd nekoscope
npm run test        # 单次运行全部测试
npm run test:watch  # 监听模式
```

## 测试文件清单

### 1. API 客户端测试 (`src/renderer/api/__tests__/client.test.ts`)

| # | 测试 | 验证内容 |
|---|------|---------|
| 1 | `compile` 发送 POST 并返回结果 | fetch 调用参数正确，JSON 解析正确 |
| 2 | `compile` 在非 ok 时抛出 | HTTP 错误时抛出异常 |
| 3 | `getExamples` 返回示例列表 | GET 请求正确，返回解析后的数组 |
| 4 | `getExampleSource` 返回源码字符串 | URL encode 正确，返回 source 字段 |
| 5 | `setBaseUrl` 改变 API 地址 | baseUrl 正确更新 |

### 2. TokenPanel 测试 (`src/renderer/components/__tests__/TokenPanel.test.tsx`)

| # | 测试 | 验证内容 |
|---|------|---------|
| 1 | 渲染 token 的类型、值和行号 | 卡片显示 type/value/line 信息 |
| 2 | 显示行列号信息 | 每个 token 显示 `line:col` 格式位置 |
| 3 | 空列表提示 | `tokens=[]` 时显示 "No tokens produced" |
| 4 | null 状态提示 | `tokens=null` 时显示 "Compile source code to see tokens" |

**Token 类型颜色映射**：

| Token 类型 | 颜色 | 色值 |
|-----------|------|------|
| keyword | mauve (紫) | `#cba6f7` |
| identifier | blue (蓝) | `#89b4fa` |
| literal | green (绿) | `#a6e3a1` |
| operator | peach (橙) | `#fab387` |
| delimiter | overlay0 (灰) | `#6c7086` |
| program | pink (粉) | `#f5c2e7` |
| type (int/float/...) | sky (天蓝) | `#89dceb` |

### 3. AssemblyPanel 测试 (`src/renderer/components/__tests__/AssemblyPanel.test.tsx`)

| # | 测试 | 验证内容 |
|---|------|---------|
| 1 | 渲染汇编代码文本 | asm 字符串可见 |
| 2 | 后端选择器当前值正确 | `<select>` 默认值匹配 `backend` prop |
| 3 | null 汇编显示提示 | `assembly=null` 时显示编译提示 |
| 4 | 切换后端触发回调 | `onBackendChange` 被调用，参数正确 |

### 4. ASTPanel 测试 (`src/renderer/components/__tests__/ASTPanel.test.tsx`)

**astToFlow 单元测试**：

| # | 测试 | 验证内容 |
|---|------|---------|
| 1 | 叶子节点转为单个节点 | 无子节点的 AST 产生 1 node + 0 edge |
| 2 | 嵌套 AST 产生多节点 | FunctionDef → Block → AssignStmt → IntLiteral 产生 ≥4 nodes + ≥3 edges |
| 3 | 叶子节点显示值 | `IntLiteral(42)` 节点 label 包含 "42" |
| 4 | 有 name 的节点显示名称 | `FunctionDef("t")` 节点 label 包含 "t" |

**ASTPanel 组件测试**：

| # | 测试 | 验证内容 |
|---|------|---------|
| 5 | null AST 显示提示 | `ast=null` 时显示编译提示 |
| 6 | 提供 AST 时渲染 react-flow 容器 | DOM 中存在 `.react-flow` 元素 |

### 5. TabBar 测试 (`src/renderer/components/__tests__/TabBar.test.tsx`)

| # | 测试 | 验证内容 |
|---|------|---------|
| 1 | 渲染所有标签 | Tokens / AST / Assembly 三个按钮可见 |
| 2 | 活跃标签高亮 | 选中标签颜色为 pink `rgb(245, 194, 231)` |
| 3 | 点击触发 onChange | 点击 Assembly 后回调收到 `"assembly"` |

## 测试总数：22

| 文件 | 测试数 | 状态 |
|------|--------|------|
| `client.test.ts` | 5 | ✓ |
| `TokenPanel.test.tsx` | 4 | ✓ |
| `AssemblyPanel.test.tsx` | 4 | ✓ |
| `ASTPanel.test.tsx` | 6 | ✓ |
| `TabBar.test.tsx` | 3 | ✓ |
| **合计** | **22** | ✓ |

## 测试覆盖的边界条件

| 场景 | 覆盖组件 | 处理方式 |
|------|---------|---------|
| 数据为 null | TokenPanel, ASTPanel, AssemblyPanel | 显示"编译源码"提示文本 |
| 空列表 | TokenPanel | 显示"No tokens produced" |
| 后端切换 | AssemblyPanel | `onBackendChange` 回调验证 |
| 未知 token 类型 | TokenPanel (tokenColor) | 回退到 `overlay1` 颜色 |
| 深层嵌套 AST | ASTPanel (astToFlow) | 递归转换至叶子节点 |
| ResizeObserver 缺失 | vitest setup | mock ResizeObserver 类 |
