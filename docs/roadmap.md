# NekoLang Roadmap

本文记录当前实现状态和后续开发方向。更细的模块关系见 [实现架构](architecture.md)，语言使用说明见 [用户指南](user-guide.zh.md)。

## 项目目标

NekoLang 是一个教学编译器项目：

- 输入：`.neko` 源程序或 `Neko.toml` 项目
- 输出：二进制可执行文件
- 后端路线：自研 ARM64 后端为课程重点，LLVM IR 后端作为跨平台 fallback
- 教学工具：NekoScope 展示词法、语法、语义、中间表示、优化、DAG、活跃信息和目标代码

项目不引入解释执行路线。

## 当前状态

当前仓库已经具备这些能力：

- 词法分析、语法分析、AST 构建和具体语法树展示
- 符号表、常量池、临时变量地址和四元式生成
- 基本语句：变量声明、赋值、条件、循环、输出、返回
- 一维数组声明、写入、读取和输出
- 函数定义、函数调用、作用域与返回值检查
- `bool` 类型与比较表达式
- lambda 表达式、`(func ...)` 函数类型和函数值传递
- `string` 类型与拼接、长度、切片、比较、包含、转换
- 字符字面量与 char/int/string 转换、字符分类、大小写转换
- 命令行参数、标准输入、随机数和基础文件读写
- `import` 多文件导入、导入链解析和循环导入检查
- 固定签名 `extern`，支持项目内 C 源码自动发现和链接配置
- `neko` 单文件命令：`check/build/run/llvm-ir/asm/ast/tokens/symbols/quads/all`
- `nekgo` 项目命令：`new/load/list/build/run/test/clean`
- LLVM IR 后端和 Apple Silicon ARM64 自研后端
- ARM64 `--opt-level 1` 的 AST 常量折叠、死变量跳过和少量 peephole
- NekoScope Electron 桌面应用、FastAPI 后端、跨平台打包脚本和 CI 检查

当前仍然存在的主要限制：

- 包管理仍只支持本地包复制和显式导出文件，尚无远程注册表、版本解析和锁文件
- `extern` 不支持 `void`、可变参数和数组作为 extern 参数或返回值
- `pointer` 仍是 opaque pointer，只能透传、比较和作为空指针状态，不支持 NekoLang 侧解引用
- 四元式 DAG、O1 分步优化和活跃信息目前只用于 NekoScope 教学展示，不参与目标代码生成
- NekoScope 已具备阶段展示和打包流程，但源码映射、逐步动画和课堂协作仍是后续功能
- 发布体验还可以继续完善，例如正式版本号、安装器说明、平台能力矩阵和示例索引

## 已完成阶段

### v0.1 语言核心

状态：已完成基础版本。

成果：

- 标准关键字与个性化别名并存
- 基础类型、数组、函数、lambda、字符串、字符和 pointer 进入当前实现
- 前端语义检查和后端可生成能力基本对齐
- README、文法、用户指南和语言元素文档持续对齐当前实现

### 函数和类型系统

状态：已完成基础版本，后续继续优化错误提示。

成果：

- 函数定义、调用、参数数量、返回值类型和作用域检查
- `return`、lambda、高阶函数和 `(func ...)` 函数类型
- `bool`、`string`、`char`、`pointer` 与数组类型检查

### 运行时能力

状态：已完成基础版本。

成果：

- 命令行参数：`argc`、`argv-int`、`argv-float`、`argv-char`、`argv-bool`、`argv-string`
- 标准输入：`input-int`、`input-float`、`input-char`、`input-bool`
- 文件读写：`read-*`、`write-*`
- 字符串和字符运行时辅助函数
- 随机数：`rand-seed`、`rand-range`

### 项目工具

状态：已完成可用版本。

成果：

- `Neko.toml` 项目清单
- `nekgo new/build/run/test/clean`
- 默认输出到项目 `build/` 目录，`run --ephemeral` 提供临时运行
- `nekgo load/list` 支持本地包复制和自动导出导入
- `[c]` 配置支持项目内 C 源码、include 目录、库目录和链接库

### 自研 ARM64 后端

状态：已完成课程可演示版本，仍可继续优化。

成果：

- Apple Silicon macOS 上生成 ARM64 汇编并用 `clang` 链接
- 栈帧、局部变量、控制流、函数调用、运行时调用和 extern 调用
- `--opt-level 1` 支持 AST 级常量折叠、未使用变量跳过、常量运算指令选择和 peephole
- macOS ARM64 CI 覆盖 LLVM 与自研后端测试

### NekoScope

状态：已完成教学可视化基础版本。

成果：

- Electron + React + Monaco + React Flow 前端
- FastAPI 后端复用 `neko.*` 编译管线
- 源码工作区、示例库、编译、运行、文件树和主题切换
- Tokens、抽象 AST、精确语法树、符号表、四元式、DAG、优化过程、活跃信息、目标代码展示
- 打包脚本复制 `uv`，应用启动时用内置 `uv` 创建后端环境
- Linux、macOS ARM64、Windows CI 覆盖测试、构建、目录打包和内置 `uv` 检查

## 下一步优先级

### P0：文档和发布体验

目标：让新用户可以从 README、安装文档和示例顺畅跑通。

任务：

- 持续补齐功能、实现、测试、部署打包文档
- 为 NekoScope 发布产物补平台能力矩阵和常见故障排查
- 整理示例索引，标注哪些示例依赖 clang、macOS ARM64、POSIX socket 或项目内 C
- 为首个可展示版本准备 changelog 和 release checklist

### P1：NekoScope 教学体验

目标：让中间产物展示更适合课堂讲解。

任务：

- 源码到 token/AST/四元式的高亮映射
- 编译阶段逐步模式
- 优化过程的更细解释，例如每条改写的原因、CSE 复用来源和死临时删除原因
- DAG 和 CST 的大图性能优化
- 运行输出的终端启动提示和失败诊断优化

### P2：代码生成与优化链路

目标：让当前教学优化和真实目标代码生成之间的关系更清晰。

任务：

- 明确四元式优化是否进入真实中端；如果进入，需要定义 AST、四元式、目标代码生成之间的新边界
- 为 ARM64 后端补更多 O1 指令选择与寄存器使用优化
- 增加跨后端一致性的端到端测试
- 继续保持“教学展示优化”和“真实 codegen 优化”的文档区分

### P3：extern 和 C 适配层增强

目标：降低与系统库、第三方 C 库集成的成本。

任务：

- 评估 `extern` 的 `void` 返回支持
- 设计数组或 buffer 传给 extern 的安全边界
- 为常见 C 适配模式提供模板示例
- 更清晰地诊断 C 链接失败，例如缺库、符号缺失、签名不匹配

### P4：包管理和模块系统

目标：从本地包复制走向可复现项目依赖。

任务：

- 设计包版本和依赖解析模型
- 设计 `Neko.lock` 或等价锁文件
- 支持本地路径依赖之外的包来源
- 明确跨包名称隔离、导出规则和冲突诊断

### P5：远期语言特性

这些方向提升语言表达力，但不阻塞当前课程目标：

- 结构体 / 记录类型
- 更完整的标准库
- 宏系统或受控的编译期扩展
- 更丰富的错误恢复和诊断建议

## 验收标准

短期版本可以按以下条件判断是否稳定：

- README 中的单文件和 `nekgo` 项目命令可在干净环境跑通
- `uv run pytest tests/ -q -m "not slow" -n auto` 通过
- 慢测在安装 clang 的环境通过
- macOS ARM64 后端测试通过
- NekoScope 在三大平台完成 `npm test`、`npm run build`、`npm run pack`
- 文档中不再把历史规划描述成当前实现
