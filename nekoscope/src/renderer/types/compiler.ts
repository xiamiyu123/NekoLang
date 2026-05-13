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

/** Symbol table entry emitted by semantic analysis */
export interface SymbolEntry {
  name: string;
  type: string;
  category: string;
  address: number;
}

/** Symbol table snapshot emitted by semantic analysis */
export interface SymbolTableSnapshot {
  entries: SymbolEntry[];
  constants: Record<string, number | string>;
}

/** Three-address style intermediate representation row */
export interface Quadruple {
  op: string;
  ob1: string;
  ob2: string;
  t: string;
}

/** Full compilation result from POST /api/compile */
export interface CompileResult {
  source: string;
  tokens: Token[];
  ast: ASTNode;
  symbols: SymbolTableSnapshot;
  quadruples: Quadruple[];
  assembly: string;
  errors: CompileError[];
  backend: string;
}

/** Example metadata from GET /api/examples */
export interface Example {
  name: string;
  description: string;
}
