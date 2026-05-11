from .tokens import Token, TokenType
from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode, VarDeclNode, BeginBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode, BoolLiteralNode, StringLiteralNode,
    FuncDefNode, FuncCallNode, ReturnNode,
    ArrayAccessNode, ArrayAssignNode, ArrayPrintNode,
    ArgcNode, ArgvNode, FileReadNode, FileWriteNode,
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
        self._expect(TokenType.PROGRAM)
        name_tok = self._expect(TokenType.IDENTIFIER)
        block = self._parse_block()
        self._expect(TokenType.RPAREN)
        return ProgramNode(name=name_tok.value, block=block,
                           line=name_tok.line, column=name_tok.column)

    def _parse_block(self) -> BlockNode:
        var_decls = []
        while self._current().type == TokenType.LPAREN:
            # Peek ahead to see if it's a var declaration.
            saved = self.pos
            self._advance()  # consume '('
            if self._current().type == TokenType.VAR:
                self.pos = saved  # put back '('
                var_decls.append(self._parse_var_decl())
            else:
                self.pos = saved  # put back '('
                break
        body = self._parse_begin_block()
        return BlockNode(var_decls=var_decls, body=body)

    def _parse_var_decl(self) -> VarDeclNode:
        tok = self._current()
        self._expect(TokenType.LPAREN)
        self._expect(TokenType.VAR)
        self._expect(TokenType.LPAREN)  # outer list

        variables = []
        while self._current().type == TokenType.LPAREN:
            self._advance()  # consume '('
            name_tok = self._expect(TokenType.IDENTIFIER)
            type_tok = self._advance()  # type keyword or '(' for array
            type_name = type_tok.value

            # Handle array type: (array int 10) or ((array int 10)).
            if type_tok.type == TokenType.LPAREN:
                # Parenthesized type like (array int 10).
                inner = self._advance()
                if inner.type == TokenType.ARRAY:
                    elem_type_tok = self._advance()
                    elem_type = elem_type_tok.value
                    size_tok = self._expect(TokenType.INTEGER)
                    type_name = f"(array {elem_type} {size_tok.value})"
                    self._expect(TokenType.RPAREN)  # close (array ...)
                else:
                    type_name = inner.value
            elif type_tok.type == TokenType.ARRAY:
                elem_type_tok = self._advance()
                elem_type = elem_type_tok.value
                size_tok = self._expect(TokenType.INTEGER)
                type_name = f"(array {elem_type} {size_tok.value})"

            self._expect(TokenType.RPAREN)
            variables.append((name_tok.value, type_name))

        self._expect(TokenType.RPAREN)  # close outer list
        self._expect(TokenType.RPAREN)  # close (var ...)
        return VarDeclNode(variables=variables, line=tok.line, column=tok.column)

    def _parse_begin_block(self, paren_consumed: bool = False) -> BeginBlockNode:
        tok = self._current()
        if not paren_consumed:
            self._expect(TokenType.LPAREN)
        self._expect(TokenType.BEGIN)
        statements = []
        while self._current().type != TokenType.RPAREN:
            statements.append(self._parse_statement())
        self._expect(TokenType.RPAREN)
        return BeginBlockNode(statements=statements, line=tok.line, column=tok.column)

    def _parse_statement(self) -> ASTNode:
        self._expect(TokenType.LPAREN)
        tok = self._current()

        if tok.type == TokenType.ASSIGN:
            return self._parse_assign()
        elif tok.type == TokenType.IF:
            return self._parse_if()
        elif tok.type == TokenType.WHILE:
            return self._parse_while()
        elif tok.type == TokenType.PRINT:
            return self._parse_print()
        elif tok.type == TokenType.RETURN:
            return self._parse_return()
        elif tok.type == TokenType.BEGIN:
            return self._parse_begin_block(paren_consumed=True)
        elif tok.type == TokenType.FUNCTION:
            return self._parse_func_def()
        elif tok.type == TokenType.ARRAY_SET:
            return self._parse_array_assign()
        elif tok.type == TokenType.ARRAY_PRINT:
            return self._parse_array_print()
        elif tok.type in {
            TokenType.WRITE_INT,
            TokenType.WRITE_FLOAT,
            TokenType.WRITE_CHAR,
            TokenType.WRITE_BOOL,
        }:
            return self._parse_file_write()
        else:
            src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
            raise ParseError(
                f"未知的语句关键字: {tok.value!r}",
                line=tok.line, column=tok.column,
                source_line=src
            )

    def _parse_assign(self) -> AssignNode:
        tok = self._advance()  # consume ':='
        target_tok = self._expect(TokenType.IDENTIFIER)
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return AssignNode(target=target_tok.value, value=value,
                          line=tok.line, column=tok.column)

    def _parse_if(self) -> IfNode:
        tok = self._advance()  # consume 'if'
        condition = self._parse_expression()
        then_branch = self._parse_statement()
        else_branch = self._parse_statement()
        self._expect(TokenType.RPAREN)
        return IfNode(condition=condition, then_branch=then_branch,
                      else_branch=else_branch, line=tok.line, column=tok.column)

    def _parse_while(self) -> WhileNode:
        tok = self._advance()  # consume 'while'
        condition = self._parse_expression()
        body = self._parse_statement()
        self._expect(TokenType.RPAREN)
        return WhileNode(condition=condition, body=body,
                         line=tok.line, column=tok.column)

    def _parse_print(self) -> PrintNode:
        tok = self._advance()  # consume 'print'
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return PrintNode(value=value, line=tok.line, column=tok.column)

    def _parse_func_def(self) -> FuncDefNode:
        tok = self._advance()  # consume 'function'
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

    def _parse_return(self) -> ReturnNode:
        tok = self._advance()  # consume 'return'
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return ReturnNode(value=value, line=tok.line, column=tok.column)

    def _parse_array_assign(self) -> ArrayAssignNode:
        tok = self._advance()  # consume 'array-set'
        name_tok = self._expect(TokenType.IDENTIFIER)
        index = self._parse_expression()
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return ArrayAssignNode(name=name_tok.value, index=index, value=value,
                               line=tok.line, column=tok.column)

    def _parse_array_print(self) -> ArrayPrintNode:
        tok = self._advance()  # consume 'array-print'
        name_tok = self._expect(TokenType.IDENTIFIER)
        index = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return ArrayPrintNode(name=name_tok.value, index=index,
                              line=tok.line, column=tok.column)

    def _parse_file_write(self) -> FileWriteNode:
        tok = self._advance()
        path = self._parse_expression()
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return FileWriteNode(
            value_type=self._builtin_value_type(tok.type),
            path=path,
            value=value,
            line=tok.line,
            column=tok.column,
        )

    def _parse_expression(self) -> ASTNode:
        tok = self._current()
        if tok.type == TokenType.LPAREN:
            self._advance()  # consume '('
            op_tok = self._current()
            if op_tok.type == TokenType.ARGC:
                self._advance()
                self._expect(TokenType.RPAREN)
                return ArgcNode(line=op_tok.line, column=op_tok.column)
            if op_tok.type in {
                TokenType.ARGV_INT,
                TokenType.ARGV_FLOAT,
                TokenType.ARGV_CHAR,
                TokenType.ARGV_BOOL,
            }:
                self._advance()
                index = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return ArgvNode(
                    value_type=self._builtin_value_type(op_tok.type),
                    index=index,
                    line=op_tok.line,
                    column=op_tok.column,
                )
            if op_tok.type in {
                TokenType.READ_INT,
                TokenType.READ_FLOAT,
                TokenType.READ_CHAR,
                TokenType.READ_BOOL,
            }:
                self._advance()
                path = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return FileReadNode(
                    value_type=self._builtin_value_type(op_tok.type),
                    path=path,
                    line=op_tok.line,
                    column=op_tok.column,
                )
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
        elif tok.type == TokenType.BOOLEAN:
            self._advance()
            return BoolLiteralNode(value=(tok.value == "true"), line=tok.line, column=tok.column)
        elif tok.type == TokenType.STRING:
            self._advance()
            return StringLiteralNode(value=tok.value, line=tok.line, column=tok.column)
        else:
            src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
            raise ParseError(
                f"表达式中遇到意外的 token: {tok.value!r}",
                line=tok.line, column=tok.column,
                source_line=src
            )

    def _builtin_value_type(self, token_type: TokenType) -> str:
        mapping = {
            TokenType.ARGV_INT: "int",
            TokenType.ARGV_FLOAT: "float",
            TokenType.ARGV_CHAR: "char",
            TokenType.ARGV_BOOL: "bool",
            TokenType.READ_INT: "int",
            TokenType.READ_FLOAT: "float",
            TokenType.READ_CHAR: "char",
            TokenType.READ_BOOL: "bool",
            TokenType.WRITE_INT: "int",
            TokenType.WRITE_FLOAT: "float",
            TokenType.WRITE_CHAR: "char",
            TokenType.WRITE_BOOL: "bool",
        }
        return mapping[token_type]
