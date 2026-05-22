"""Concrete syntax tree construction from lexer tokens."""

from __future__ import annotations

from typing import Any

from .tokens import Token, TokenType


def build_syntax_tree(tokens: list[Token]) -> dict[str, Any]:
    root: dict[str, Any] = {
        "nodeType": "SyntaxTree",
        "line": 1,
        "column": 1,
        "children": [],
    }
    stack = [root]

    for token in tokens:
        if token.type == TokenType.EOF:
            continue

        terminal = _terminal(token)
        if token.type == TokenType.LPAREN:
            form = {
                "nodeType": "SyntaxForm",
                "line": token.line,
                "column": token.column,
                "children": [terminal],
            }
            stack[-1]["children"].append(form)
            stack.append(form)
            continue

        stack[-1]["children"].append(terminal)
        if token.type == TokenType.RPAREN and len(stack) > 1:
            stack.pop()

    return root


def _terminal(token: Token) -> dict[str, Any]:
    return {
        "nodeType": "Terminal",
        "tokenType": token.type.value,
        "value": token.value,
        "line": token.line,
        "column": token.column,
    }
