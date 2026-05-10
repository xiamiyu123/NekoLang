from .tokens import Token, TokenType
from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode, VarDeclNode, PawBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode,
    FuncDefNode, FuncCallNode, ArrayAccessNode, ArrayAssignNode, ArrayPrintNode,
)
from .errors import ParseError


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.source_lines: list[str] = []

    def set_source(self, source: str):
        self.source_lines = source.splitlines()

    def _current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, "", 0, 0)

    def _advance(self) -> Token:
        tok = self._current()
        self.pos += 1
        return tok

    def _expect(self, tok_type: TokenType) -> Token:
        tok = self._current()
        if tok.type != tok_type:
            src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
            raise ParseError(
                f"期望 {tok_type.value}，但得到 {tok.value!r} ({tok.type.value})",
                line=tok.line, column=tok.column,
                source_line=src
            )
        return self._advance()

    def _match(self, tok_type: TokenType) -> bool:
        if self._current().type == tok_type:
            self._advance()
            return True
        return False

    def parse(self) -> ProgramNode:
        self._expect(TokenType.LPAREN)
        self._expect(TokenType.NYA)
        name_tok = self._expect(TokenType.IDENTIFIER)
        block = self._parse_block()
        self._expect(TokenType.RPAREN)
        return ProgramNode(name=name_tok.value, block=block,
                           line=name_tok.line, column=name_tok.column)

    def _parse_block(self) -> BlockNode:
        var_decls = []
        while self._current().type == TokenType.LPAREN:
            # Peek ahead to see if it's a nyan declaration
            saved = self.pos
            self._advance()  # consume '('
            if self._current().type == TokenType.NYAN:
                self.pos = saved  # put back '('
                var_decls.append(self._parse_var_decl())
            else:
                self.pos = saved  # put back '('
                break
        body = self._parse_paw_block()
        return BlockNode(var_decls=var_decls, body=body)

    def _parse_var_decl(self) -> VarDeclNode:
        tok = self._current()
        self._expect(TokenType.LPAREN)
        self._expect(TokenType.NYAN)
        self._expect(TokenType.LPAREN)  # outer list

        variables = []
        while self._current().type == TokenType.LPAREN:
            self._advance()  # consume '('
            name_tok = self._expect(TokenType.IDENTIFIER)
            type_tok = self._advance()  # type keyword (int, float, char, litter-box, etc.)
            type_name = type_tok.value

            # Handle litter-box array type: (litter-box int 10)
            if type_tok.type == TokenType.LITTER_BOX:
                elem_type = self._expect(TokenType.IDENTIFIER).value
                size_tok = self._expect(TokenType.INTEGER)
                type_name = f"(array {elem_type} {size_tok.value})"

            self._expect(TokenType.RPAREN)
            variables.append((name_tok.value, type_name))

        self._expect(TokenType.RPAREN)  # close outer list
        self._expect(TokenType.RPAREN)  # close (nyan ...)
        return VarDeclNode(variables=variables, line=tok.line, column=tok.column)

    def _parse_paw_block(self, paren_consumed: bool = False) -> PawBlockNode:
        tok = self._current()
        if not paren_consumed:
            self._expect(TokenType.LPAREN)
        self._expect(TokenType.PAW)
        statements = []
        while self._current().type != TokenType.RPAREN:
            statements.append(self._parse_statement())
        self._expect(TokenType.RPAREN)
        return PawBlockNode(statements=statements, line=tok.line, column=tok.column)

    def _parse_statement(self) -> ASTNode:
        self._expect(TokenType.LPAREN)
        tok = self._current()

        if tok.type == TokenType.MEOW:
            return self._parse_assign()
        elif tok.type == TokenType.IF_NYA:
            return self._parse_if()
        elif tok.type == TokenType.PURR_WHILE:
            return self._parse_while()
        elif tok.type == TokenType.PURR:
            return self._parse_print()
        elif tok.type == TokenType.PAW:
            return self._parse_paw_block(paren_consumed=True)
        elif tok.type == TokenType.NYAA_DEF:
            return self._parse_func_def()
        elif tok.type == TokenType.MEOW_ARR:
            return self._parse_array_assign()
        elif tok.type == TokenType.PURR_ARR:
            return self._parse_array_print()
        else:
            src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
            raise ParseError(
                f"未知的语句关键字: {tok.value!r}",
                line=tok.line, column=tok.column,
                source_line=src
            )

    def _parse_assign(self) -> AssignNode:
        tok = self._advance()  # consume 'meow'
        target_tok = self._expect(TokenType.IDENTIFIER)
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return AssignNode(target=target_tok.value, value=value,
                          line=tok.line, column=tok.column)

    def _parse_if(self) -> IfNode:
        tok = self._advance()  # consume 'if-nya'
        condition = self._parse_expression()
        then_branch = self._parse_statement()
        else_branch = self._parse_statement()
        self._expect(TokenType.RPAREN)
        return IfNode(condition=condition, then_branch=then_branch,
                      else_branch=else_branch, line=tok.line, column=tok.column)

    def _parse_while(self) -> WhileNode:
        tok = self._advance()  # consume 'purr-while'
        condition = self._parse_expression()
        body = self._parse_statement()
        self._expect(TokenType.RPAREN)
        return WhileNode(condition=condition, body=body,
                         line=tok.line, column=tok.column)

    def _parse_print(self) -> PrintNode:
        tok = self._advance()  # consume 'purr'
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return PrintNode(value=value, line=tok.line, column=tok.column)

    def _parse_func_def(self) -> FuncDefNode:
        tok = self._advance()  # consume 'nyaa-def'
        name_tok = self._expect(TokenType.IDENTIFIER)
        self._expect(TokenType.LPAREN)  # param list
        params = []
        while self._current().type == TokenType.LPAREN:
            self._advance()
            p_name = self._expect(TokenType.IDENTIFIER).value
            p_type = self._advance().value
            self._expect(TokenType.RPAREN)
            params.append((p_name, p_type))
        self._expect(TokenType.RPAREN)  # close param list
        return_type = self._advance().value
        body = self._parse_statement()
        self._expect(TokenType.RPAREN)
        return FuncDefNode(name=name_tok.value, params=params,
                           return_type=return_type, body=body,
                           line=tok.line, column=tok.column)

    def _parse_array_assign(self) -> ArrayAssignNode:
        tok = self._advance()  # consume 'meow-arr'
        name_tok = self._expect(TokenType.IDENTIFIER)
        index = self._parse_expression()
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return ArrayAssignNode(name=name_tok.value, index=index, value=value,
                               line=tok.line, column=tok.column)

    def _parse_array_print(self) -> ArrayPrintNode:
        tok = self._advance()  # consume 'purr-arr'
        name_tok = self._expect(TokenType.IDENTIFIER)
        index = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return ArrayPrintNode(name=name_tok.value, index=index,
                              line=tok.line, column=tok.column)

    def _parse_expression(self) -> ASTNode:
        tok = self._current()
        if tok.type == TokenType.LPAREN:
            self._advance()  # consume '('
            op_tok = self._current()
            # Check if it's a function call: (func_name arg1 arg2 ...)
            if op_tok.type == TokenType.IDENTIFIER:
                self._advance()
                args = []
                while self._current().type != TokenType.RPAREN:
                    args.append(self._parse_expression())
                self._expect(TokenType.RPAREN)
                return FuncCallNode(name=op_tok.value, args=args,
                                    line=op_tok.line, column=op_tok.column)
            # Otherwise it's a binary operator expression
            self._advance()  # consume operator
            left = self._parse_expression()
            right = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return BinOpNode(op=op_tok.value, left=left, right=right,
                             line=op_tok.line, column=op_tok.column)
        elif tok.type == TokenType.IDENTIFIER:
            self._advance()
            return IdentifierNode(name=tok.value, line=tok.line, column=tok.column)
        elif tok.type == TokenType.INTEGER:
            self._advance()
            return IntLiteralNode(value=int(tok.value), line=tok.line, column=tok.column)
        elif tok.type == TokenType.FLOAT:
            self._advance()
            return FloatLiteralNode(value=float(tok.value), line=tok.line, column=tok.column)
        else:
            src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
            raise ParseError(
                f"表达式中遇到意外的 token: {tok.value!r}",
                line=tok.line, column=tok.column,
                source_line=src
            )
