/** Token from lexer output */
export interface Token {
  type: string;
  value: string;
  line: number;
  column: number;
}

/** AST node — base shape shared by all node types */
export interface ASTNode {
  nodeType: string;
  line: number;
  column: number;
  [key: string]: unknown;
}

/** Compilation error */
export interface CompileError {
  phase: string;
  message: string;
  line: number;
  column: number;
  sourceLine: string;
  suggestion: string;
}

/** Full compilation result from POST /api/compile */
export interface CompileResult {
  source: string;
  tokens: Token[];
  ast: ASTNode;
  assembly: string;
  errors: CompileError[];
}

/** Example metadata from GET /api/examples */
export interface Example {
  name: string;
  description: string;
}
