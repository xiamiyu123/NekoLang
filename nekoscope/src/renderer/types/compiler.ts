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
  address: number | null;
  addressName?: string;
  scope?: string;
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

export interface QuadrupleOptimizationStep {
  name: string;
  detail: string;
  beforeCount: number;
  afterCount: number;
  changed: boolean;
}

export interface QuadrupleOptimization {
  level: string;
  source: string;
  enabled: boolean;
  changed: boolean;
  beforeCount: number;
  afterCount: number;
  initial: Quadruple[];
  optimized: Quadruple[];
  initialConstants: Record<string, string | number>;
  optimizedConstants: Record<string, string | number>;
  steps: QuadrupleOptimizationStep[];
  diagnostics: CompileError[];
}

/** Full compilation result from POST /api/compile */
export interface CompileResult {
  source: string;
  tokens: Token[];
  ast: ASTNode;
  symbols: SymbolTableSnapshot;
  quadruples: Quadruple[];
  quadrupleOptimization?: QuadrupleOptimization;
  assembly: string;
  errors: CompileError[];
  backend: string;
}

export interface RunResult {
  executablePath: string;
  errors: CompileError[];
  compileError: string;
}

/** Example metadata from GET /api/examples */
export interface Example {
  name: string;
  description: string;
}
