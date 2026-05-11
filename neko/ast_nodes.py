from dataclasses import dataclass, field


class ASTNode:
    line: int = 0
    column: int = 0


@dataclass
class ProgramNode(ASTNode):
    name: str = ""
    block: 'BlockNode' = field(default_factory=lambda: BlockNode())
    line: int = 0
    column: int = 0


@dataclass
class BlockNode(ASTNode):
    var_decls: list['VarDeclNode'] = field(default_factory=list)
    body: 'BeginBlockNode' = field(default_factory=lambda: BeginBlockNode())
    line: int = 0
    column: int = 0


@dataclass
class VarDeclNode(ASTNode):
    variables: list[tuple[str, str]] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class BeginBlockNode(ASTNode):
    statements: list[ASTNode] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class AssignNode(ASTNode):
    target: str = ""
    value: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class IfNode(ASTNode):
    condition: ASTNode = field(default_factory=ASTNode)
    then_branch: ASTNode = field(default_factory=ASTNode)
    else_branch: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class WhileNode(ASTNode):
    condition: ASTNode = field(default_factory=ASTNode)
    body: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class PrintNode(ASTNode):
    value: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class BinOpNode(ASTNode):
    op: str = ""
    left: ASTNode = field(default_factory=ASTNode)
    right: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class IdentifierNode(ASTNode):
    name: str = ""
    line: int = 0
    column: int = 0


@dataclass
class IntLiteralNode(ASTNode):
    value: int = 0
    line: int = 0
    column: int = 0


@dataclass
class FloatLiteralNode(ASTNode):
    value: float = 0.0
    line: int = 0
    column: int = 0


@dataclass
class BoolLiteralNode(ASTNode):
    value: bool = False
    line: int = 0
    column: int = 0


@dataclass
class StringLiteralNode(ASTNode):
    value: str = ""
    line: int = 0
    column: int = 0


@dataclass
class FuncDefNode(ASTNode):
    name: str = ""
    params: list[tuple[str, str]] = field(default_factory=list)
    return_type: str = ""
    body: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class FuncCallNode(ASTNode):
    name: str = ""
    args: list[ASTNode] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class ReturnNode(ASTNode):
    value: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class ArrayAccessNode(ASTNode):
    name: str = ""
    index: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class ArrayAssignNode(ASTNode):
    name: str = ""
    index: ASTNode = field(default_factory=ASTNode)
    value: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class ArrayPrintNode(ASTNode):
    name: str = ""
    index: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class ArgcNode(ASTNode):
    line: int = 0
    column: int = 0


@dataclass
class ArgvNode(ASTNode):
    value_type: str = "int"
    index: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class FileReadNode(ASTNode):
    value_type: str = "int"
    path: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class FileWriteNode(ASTNode):
    value_type: str = "int"
    path: ASTNode = field(default_factory=ASTNode)
    value: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


def dump_ast(node: ASTNode, indent: int = 0) -> str:
    prefix = "  " * indent
    if isinstance(node, ProgramNode):
        result = f"{prefix}Program({node.name})\n"
        result += dump_ast(node.block, indent + 1)
        return result
    elif isinstance(node, BlockNode):
        result = f"{prefix}Block\n"
        for decl in node.var_decls:
            result += dump_ast(decl, indent + 1)
        result += dump_ast(node.body, indent + 1)
        return result
    elif isinstance(node, VarDeclNode):
        vars_str = ", ".join(f"({n}:{t})" for n, t in node.variables)
        return f"{prefix}VarDecl[{vars_str}]\n"
    elif isinstance(node, BeginBlockNode):
        result = f"{prefix}BeginBlock\n"
        for stmt in node.statements:
            result += dump_ast(stmt, indent + 1)
        return result
    elif isinstance(node, AssignNode):
        result = f"{prefix}Assign({node.target})\n"
        result += dump_ast(node.value, indent + 1)
        return result
    elif isinstance(node, IfNode):
        result = f"{prefix}If\n"
        result += f"{prefix}  Condition:\n"
        result += dump_ast(node.condition, indent + 2)
        result += f"{prefix}  Then:\n"
        result += dump_ast(node.then_branch, indent + 2)
        result += f"{prefix}  Else:\n"
        result += dump_ast(node.else_branch, indent + 2)
        return result
    elif isinstance(node, WhileNode):
        result = f"{prefix}While\n"
        result += f"{prefix}  Condition:\n"
        result += dump_ast(node.condition, indent + 2)
        result += f"{prefix}  Body:\n"
        result += dump_ast(node.body, indent + 2)
        return result
    elif isinstance(node, PrintNode):
        result = f"{prefix}Print\n"
        result += dump_ast(node.value, indent + 1)
        return result
    elif isinstance(node, BinOpNode):
        result = f"{prefix}BinOp({node.op})\n"
        result += dump_ast(node.left, indent + 1)
        result += dump_ast(node.right, indent + 1)
        return result
    elif isinstance(node, IdentifierNode):
        return f"{prefix}Ident({node.name})\n"
    elif isinstance(node, IntLiteralNode):
        return f"{prefix}Int({node.value})\n"
    elif isinstance(node, FloatLiteralNode):
        return f"{prefix}Float({node.value})\n"
    elif isinstance(node, BoolLiteralNode):
        return f"{prefix}Bool({node.value})\n"
    elif isinstance(node, StringLiteralNode):
        return f'{prefix}String("{node.value}")\n'
    elif isinstance(node, FuncDefNode):
        params_str = ", ".join(f"({n}:{t})" for n, t in node.params)
        result = f"{prefix}FuncDef({node.name}, [{params_str}], {node.return_type})\n"
        result += dump_ast(node.body, indent + 1)
        return result
    elif isinstance(node, FuncCallNode):
        result = f"{prefix}FuncCall({node.name})\n"
        for arg in node.args:
            result += dump_ast(arg, indent + 1)
        return result
    elif isinstance(node, ReturnNode):
        result = f"{prefix}Return\n"
        result += dump_ast(node.value, indent + 1)
        return result
    elif isinstance(node, ArrayAccessNode):
        result = f"{prefix}ArrayAccess({node.name})\n"
        result += dump_ast(node.index, indent + 1)
        return result
    elif isinstance(node, ArrayAssignNode):
        result = f"{prefix}ArrayAssign({node.name})\n"
        result += dump_ast(node.index, indent + 1)
        result += dump_ast(node.value, indent + 1)
        return result
    elif isinstance(node, ArrayPrintNode):
        result = f"{prefix}ArrayPrint({node.name})\n"
        result += dump_ast(node.index, indent + 1)
        return result
    elif isinstance(node, ArgcNode):
        return f"{prefix}Argc\n"
    elif isinstance(node, ArgvNode):
        result = f"{prefix}Argv({node.value_type})\n"
        result += dump_ast(node.index, indent + 1)
        return result
    elif isinstance(node, FileReadNode):
        result = f"{prefix}FileRead({node.value_type})\n"
        result += dump_ast(node.path, indent + 1)
        return result
    elif isinstance(node, FileWriteNode):
        result = f"{prefix}FileWrite({node.value_type})\n"
        result += dump_ast(node.path, indent + 1)
        result += dump_ast(node.value, indent + 1)
        return result
    else:
        return f"{prefix}Unknown({type(node).__name__})\n"
