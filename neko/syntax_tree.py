"""
具体语法树（Concrete Syntax Tree / CST / Parse Tree）

编译原理角色：
  具体语法树（CST）与抽象语法树（AST）不同之处在于：
  CST 保留了源码中所有的语法细节，包括括号、分隔符等。
  AST 则去除了这些细节，只保留语义相关的结构。

  本文件构建的 CST 是 Token 序列的一种结构化表示，
  按 S-表达式的括号嵌套关系组织成树形，每个叶子节点
  是一个词法单元（Token），内部节点对应一对括号内的语法形式。

CST vs AST 对比：
  CST (syntax_tree.py)：
    - 保留所有 Token，包括括号
    - 每个 LPAREN 创建一个 SyntaxForm 节点
    - 每个 RPAREN 结束一个 SyntaxForm 节点
    - 叶子节点是 Terminal（一个 Token）
    - 用于教学展示 Token 序列的嵌套结构
    - 给 NekoScope 前端做 CST 可视化

  AST (ast_nodes.py)：
    - 丢弃了括号等语法细节
    - 解析器按语法规则识别 (keyword ...) 的结构，
      创建对应的语义节点（AssignNode、IfNode 等）
    - 叶子节点是字面量或标识符
    - 用于编译器后续阶段的语义分析、代码生成

  示例对比 —— 源码 (+ 1 2)：
    CST 结构：
      SyntaxTree
        SyntaxForm "(+ 1 2)"
          Terminal(LPAREN)
          Terminal(PLUS)
          Terminal(INTEGER, 1)
          Terminal(INTEGER, 2)
          Terminal(RPAREN)

    AST 结构：
      BinOpNode("+")
        IntLiteralNode(1)
        IntLiteralNode(2)
"""

from __future__ import annotations

from typing import Any

from .tokens import Token, TokenType


def build_syntax_tree(tokens: list[Token]) -> dict[str, Any]:
    """
    从 Token 序列构建具体语法树（CST）。

    算法：
      使用一个栈来跟踪括号嵌套。
      - 遇到 LPAREN：创建一个 SyntaxForm 节点（代表一对括号内的结构），
        将 LPAREN 作为第一个子节点，压栈。
      - 遇到 RPAREN：将 Token 作为叶子节点添加到当前节点，然后弹出栈。
      - 其他 Token：作为叶子节点（Terminal）添加到当前栈顶节点。

    最终根节点是一个 SyntaxTree，它的子节点是最外层的 SyntaxForm。
    """
    root: dict[str, Any] = {
        "nodeType": "SyntaxTree",
        "line": 1,
        "column": 1,
        "children": [],
    }
    stack = [root]  # 栈始终至少包含根节点

    for token in tokens:
        if token.type == TokenType.EOF:
            continue

        terminal = _terminal(token)

        if token.type == TokenType.LPAREN:
            # 左括号 —— 创建新的 SyntaxForm 节点
            form = {
                "nodeType": "SyntaxForm",    # 语法形式（一对括号）
                "line": token.line,
                "column": token.column,
                "children": [terminal],      # 左括号本身作为第一个子节点
            }
            stack[-1]["children"].append(form)  # 挂到父节点
            stack.append(form)                  # 压栈，进入新层级
            continue

        # 右括号或其他 Token —— 作为叶子节点添加到当前层
        stack[-1]["children"].append(terminal)

        # 右括号 —— 弹出栈，回到上一层
        if token.type == TokenType.RPAREN and len(stack) > 1:
            stack.pop()

    return root


def _terminal(token: Token) -> dict[str, Any]:
    """
    将一个 Token 转换为 CST 叶子节点（Terminal）。

    每个 Terminal 节点包含：
      tokenType — Token 类型名称（如 "LPAREN", "PLUS", "INTEGER"）
      value     — Token 的词素值（如 "(", "+", "42"）
      line      — 源码行号（用于报错定位）
      column    — 源码列号
    """
    return {
        "nodeType": "Terminal",           # 叶子节点标记
        "tokenType": token.type.value,    # Token 类型的字符串形式
        "value": token.value,             # Token 的词法值
        "line": token.line,
        "column": token.column,
    }
