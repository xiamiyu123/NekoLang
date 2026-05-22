# NekoScope 实现路线图

> 历史规划文档已合并更新：早期 P0/P1/P2 任务中的大部分基础能力已经实现。当前实现状态请以 [实现架构](architecture.md)、[NekoScope 打包](nekoscope-packaging.md)、[NekoScope 测试文档](nekoscope-test-doc.md) 和 [ADR-001](adr/001-nekoscope-architecture.md) 为准。

## 当前已实现

- Electron + React + TypeScript + Monaco 编辑器
- FastAPI 子进程，复用 `neko.*` 编译管线
- 源码工作区、示例条、文件树、编译和运行按钮
- 主题切换：light / dark / neko
- Tokens、AST、精确语法树、符号表、四元式、DAG、优化步骤、活跃信息、目标代码展示
- AST、CST、DAG 使用 React Flow + dagre 自动布局，并支持全貌弹窗
- 编译失败和 API 连接失败分开展示
- Electron 主进程负责启动和关闭 FastAPI
- `npm run dev/build/pack/dist` 脚本
- 打包时复制当前平台 `uv` 到 Electron resources
- Linux、macOS ARM64、Windows CI 覆盖测试、构建、目录打包和内置 `uv` 检查

## 下一步

### P0：发布稳定性

- 补齐发布检查清单和平台能力说明
- 为打包应用补充后端启动失败诊断
- 继续保持 `uv.lock`、`nekoscope/out/`、`nekoscope/release/`、`nekoscope/resources/` 不进入版本控制
- 给 NekoScope 示例库加能力标签，例如“需要 C 链接”“需要 POSIX socket”“适合 DAG 优化演示”

### P1：教学交互

- 源码到 token、AST/CST、四元式行的高亮映射
- 编译阶段逐步模式
- 优化过程解释：常量折叠、公共子表达式复用和死临时删除分别给出原因
- 活跃信息视图支持基本块筛选和符号说明

### P2：项目工作区

- 更完整的多文件编辑体验
- import 依赖图展示
- extern 和项目内 C 链接配置展示
- 保存失败、权限失败、路径越界等工作区错误提示

### P3：课堂和演示能力

- 可导出演示快照
- 课堂示例集和讲解脚本
- 编译阶段耗时统计
- 更适合投影的大字号展示模式
