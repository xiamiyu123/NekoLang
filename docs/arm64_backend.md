# NekoLang ARM64 后端

本文说明 NekoLang 自研 ARM64 后端的当前优化层。该后端面向 Apple Silicon macOS；其他平台默认使用 LLVM IR 后端。

## 优化等级

ARM64 后端支持显式优化等级：

```bash
uv run neko build examples/demo.neko --backend arm64 --opt-level 0
uv run neko build examples/demo.neko --backend arm64 --opt-level 1
uv run nekgo build --backend arm64 --opt-level 1
uv run nekgo test --backend arm64 --opt-level 1
```

`--opt-level` 不随 `--mode release` 自动变化。`release` 只控制最终 `clang` 链接命令使用 `-O2`，ARM64 汇编生成优化仍由 `--opt-level` 显式控制。

## O0

`O0` 是默认等级，目标是稳定、可调试，并尽量保持原有汇编输出结构。

特点：

- AST 直接生成 ARM64 汇编
- 表达式中间值使用固定临时栈槽
- 函数参数先按原有逻辑初始化，再 spill 到栈帧
- 不做 peephole 清理

## O1

`O1` 是第一阶段安全优化层，目标是减少明显冗余汇编，而不是追求 LLVM 级性能。

当前包含：

- AST 级常量折叠：整数算术、整数比较、布尔条件、简单 char/int 转换
- ARM64 peephole：删除跳到下一条 label 的无条件分支，删除 `mov r, r` 和相邻重复 `mov`
- 轻量指令选择：`(+ x const)` / `(- x const)` 在常量可编码时生成 `add/sub ... #const`
- 栈帧初始化优化：未被读取的局部变量跳过零初始化；函数参数直接 spill，不再先零初始化

保守边界：

- 不折叠会触发运行时行为的表达式，例如字符串拼接、argv、input、文件 I/O、随机数、函数调用、extern 调用
- 不做全局寄存器分配
- 不做函数内联
- 不做循环优化
- 不引入完整 MIR

## 后续 MIR 预留

下一阶段建议把 AST 先降到后端 MIR，再由 MIR 生成 ARM64 汇编：

```text
Function
  BasicBlock(label)
    t1 = load a
    t2 = add t1, 1
    store t2, a
    br_if t2, then_label, else_label
```

MIR 至少需要表达：

- 函数与参数类型
- 基本块与标签
- 三地址表达式
- load/store
- 直接调用与间接调用
- 条件跳转与无条件跳转
- return

有了 MIR 后，再继续做死代码删除、控制流简化、基本块内线性扫描寄存器分配和循环优化。

## 测试

非 Apple Silicon 机器可跑汇编生成测试：

```bash
uv run pytest tests/test_arm64.py -q
```

Apple Silicon macOS 可额外跑端到端慢测：

```bash
uv run pytest tests/test_arm64.py -q -m slow
uv run neko run examples/pointer_null_demo.neko --backend arm64 --opt-level 1
```

