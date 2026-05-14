import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Binary,
  Boxes,
  Cat,
  Cpu,
  GitBranch,
  ListTree,
  Monitor,
  Moon,
  Route,
  SearchCode,
  Sun,
} from "lucide-react";
import { CompileFailureError, compile, getExamples, getExampleSource } from "./api/client";
import { AssemblyPanel } from "./components/AssemblyPanel";
import { ASTPanel } from "./components/ASTPanel";
import { DiagnosticPanel } from "./components/DiagnosticPanel";
import { QuadruplePanel } from "./components/QuadruplePanel";
import { SourceWorkbench } from "./components/SourceWorkbench";
import { StageGuide, type StageInfo } from "./components/StageGuide";
import { StageLesson } from "./components/StageLesson";
import { SymbolTablePanel } from "./components/SymbolTablePanel";
import { TokenPanel } from "./components/TokenPanel";
import {
  isThemePreference,
  nextThemePreference,
  resolveTheme,
  THEME_STORAGE_KEY,
  themePreferenceDescriptions,
  themePreferenceLabels,
  type ResolvedTheme,
  type ThemePreference,
} from "./styles/theme";
import type { CompileResult, Example } from "./types/compiler";
import "./styles/app.css";

const DEFAULT_SOURCE = `(nya t
  (nyan ((a int) (b int)))
  (paw
    (:= a 10)
    (:= b (+ a 32))
    (meow b)))`;

const STAGES: StageInfo[] = [
  {
    key: "overview",
    label: "路线图",
    shortLabel: "Pipeline",
    outputName: "全局观察",
    description: "展示源码经过词法分析、语法分析、语义分析、中间表示和代码生成后的完整产物。",
    focus: "提供编译管线的总览、状态和关键产物统计。",
    icon: Route,
  },
  {
    key: "tokens",
    label: "词法分析",
    shortLabel: "Lexing",
    outputName: "Tokens",
    description: "词法分析把源码文本切分为带类型和值的位置化 Token。",
    focus: "展示 Token 类型、字面值以及源码行列位置。",
    icon: Binary,
  },
  {
    key: "ast",
    label: "语法分析",
    shortLabel: "Parsing",
    outputName: "AST",
    description: "语法分析把 Token 序列组织成抽象语法树，呈现程序的层级结构。",
    focus: "展示表达式、语句、块和程序节点之间的父子关系。",
    icon: GitBranch,
  },
  {
    key: "symbols",
    label: "语义分析",
    shortLabel: "Semantic",
    outputName: "符号表",
    description: "语义分析检查声明、类型和可引用性，并产出符号表与常量池。",
    focus: "展示变量、函数、参数和常量的登记结果。",
    blockedByErrors: true,
    icon: Boxes,
  },
  {
    key: "quads",
    label: "中间表示",
    shortLabel: "IR",
    outputName: "四元式",
    description: "四元式将语义结果转换为线性中间表示，用于后续优化和代码生成。",
    focus: "展示每条中间指令的操作、参数和结果位置。",
    blockedByErrors: true,
    icon: ListTree,
  },
  {
    key: "assembly",
    label: "代码生成",
    shortLabel: "Codegen",
    outputName: "LLVM / ARM64",
    description: "代码生成输出目标后端文本，支持 LLVM IR 和 ARM64 之间切换。",
    focus: "展示当前后端生成的目标代码。",
    blockedByErrors: true,
    icon: Cpu,
  },
];

function findStage(key: string): StageInfo {
  return STAGES.find((stage) => stage.key === key) ?? STAGES[0];
}

function computeCompletedStages(result: CompileResult | null): Set<string> {
  const completed = new Set<string>(["overview"]);
  if (!result) return completed;
  if (result.tokens.length > 0) completed.add("tokens");
  if (result.ast) completed.add("ast");
  if (result.symbols.entries.length > 0 || Object.keys(result.symbols.constants).length > 0) {
    completed.add("symbols");
  }
  if (result.quadruples.length > 0) completed.add("quads");
  if (result.assembly.trim().length > 0) completed.add("assembly");
  return completed;
}

function pipelineStats(result: CompileResult | null) {
  return [
    { label: "Tokens", value: result?.tokens.length ?? 0 },
    { label: "Symbols", value: result?.symbols.entries.length ?? 0 },
    { label: "Quads", value: result?.quadruples.length ?? 0 },
    { label: "Errors", value: result?.errors.length ?? 0 },
  ];
}

function getInitialThemePreference(): ThemePreference {
  if (typeof window === "undefined") return "system";
  const storedPreference = window.localStorage.getItem(THEME_STORAGE_KEY);
  return isThemePreference(storedPreference) ? storedPreference : "system";
}

function getSystemPrefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return true;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export default function App() {
  const [source, setSource] = useState(DEFAULT_SOURCE);
  const [result, setResult] = useState<CompileResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [examples, setExamples] = useState<Example[]>([]);
  const [activeStage, setActiveStage] = useState("overview");
  const [activeExample, setActiveExample] = useState<string | null>(null);
  const [backend, setBackend] = useState("llvm");
  const [apiError, setApiError] = useState<string | null>(null);
  const [compileFailure, setCompileFailure] = useState<string | null>(null);
  const [themePreference, setThemePreference] = useState<ThemePreference>(getInitialThemePreference);
  const [systemPrefersDark, setSystemPrefersDark] = useState(getSystemPrefersDark);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestIdRef = useRef(0);

  const runCompile = useCallback(async (nextSource = source, nextBackend = backend) => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setApiError(null);
    setCompileFailure(null);
    try {
      const nextResult = await compile(nextSource, nextBackend);
      if (requestId === requestIdRef.current) {
        setResult(nextResult);
      }
    } catch (error) {
      if (requestId === requestIdRef.current) {
        if (error instanceof CompileFailureError) {
          setResult(null);
          setCompileFailure(error.detail);
        } else {
          setApiError(error instanceof Error ? error.message : "无法连接 NekoScope API");
        }
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [backend, source]);

  useEffect(() => {
    getExamples().then(setExamples).catch((error) => {
      setApiError(error instanceof Error ? error.message : "示例列表加载失败");
    });
  }, []);

  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (event: MediaQueryListEvent) => setSystemPrefersDark(event.matches);
    setSystemPrefersDark(query.matches);
    query.addEventListener("change", handleChange);
    return () => query.removeEventListener("change", handleChange);
  }, []);

  const resolvedTheme = resolveTheme(themePreference, systemPrefersDark);

  useEffect(() => {
    document.documentElement.dataset.themePreference = themePreference;
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.style.colorScheme = resolvedTheme === "dark" ? "dark" : "light";
    window.localStorage.setItem(THEME_STORAGE_KEY, themePreference);
  }, [resolvedTheme, themePreference]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void runCompile(source, backend);
    }, 500);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [backend, runCompile, source]);

  const loadExample = useCallback(async (name: string) => {
    try {
      const nextSource = await getExampleSource(name);
      setCompileFailure(null);
      setActiveExample(name);
      setSource(nextSource);
      setActiveStage("overview");
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "示例加载失败");
    }
  }, []);

  const resetSource = useCallback(() => {
    setActiveExample(null);
    setSource(DEFAULT_SOURCE);
    setActiveStage("overview");
  }, []);

  const completedStages = useMemo(() => computeCompletedStages(result), [result]);
  const activeStageInfo = findStage(activeStage);
  const stats = pipelineStats(result);
  const errors = result?.errors ?? [];
  const ThemeIcon = themePreference === "light"
    ? Sun
    : themePreference === "dark"
      ? Moon
      : themePreference === "neko"
        ? Cat
        : Monitor;
  const themeButtonLabel = `${themePreferenceDescriptions[themePreference]}，当前为 ${themePreferenceLabels[themePreference]}`;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <button
            className="brand-mark"
            type="button"
            onClick={() => setThemePreference((preference) => nextThemePreference(preference))}
            title={themeButtonLabel}
            aria-label={themeButtonLabel}
          >
            <SearchCode className="brand-code-icon" size={22} aria-hidden="true" />
            <ThemeIcon className="brand-theme-icon" size={14} aria-hidden="true" />
          </button>
          <div>
            <h1>NekoScope</h1>
            <p>NekoLang 编译管线可视化平台 · {themePreferenceLabels[themePreference]}</p>
          </div>
        </div>
        <div className="status-cluster">
          {stats.map((item) => (
            <div className="stat-pill" key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </header>

      <main className="workspace-grid">
        <SourceWorkbench
          source={source}
          examples={examples}
          activeExample={activeExample}
          loading={loading}
          theme={resolvedTheme}
          onSourceChange={(nextSource) => {
            setSource(nextSource);
            setActiveExample(null);
          }}
          onExampleLoad={loadExample}
          onCompileNow={() => void runCompile(source, backend)}
          onReset={resetSource}
        />

        <section className="teaching-workbench">
          <StageGuide
            stages={STAGES}
            activeStage={activeStage}
            completedStages={completedStages}
            onSelect={setActiveStage}
          />

          {apiError ? (
            <div className="api-error">
              <strong>API 连接失败</strong>
              <span>{apiError}</span>
            </div>
          ) : compileFailure ? (
            <div className="api-error">
              <strong>编译失败</strong>
              <span>{compileFailure}</span>
            </div>
          ) : (
            <DiagnosticPanel errors={errors} loading={loading} />
          )}

          <div className="stage-content-grid">
            <StageLesson stage={activeStageInfo} />
            <section className="artifact-panel">
              <header className="panel-heading">
                <div>
                  <div className="panel-kicker">Artifact</div>
                  <h2>{activeStageInfo.outputName}</h2>
                </div>
              </header>
              <ArtifactView
                activeStage={activeStage}
                result={result}
                backend={backend}
                theme={resolvedTheme}
                onBackendChange={setBackend}
              />
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}

interface ArtifactViewProps {
  activeStage: string;
  result: CompileResult | null;
  backend: string;
  theme: ResolvedTheme;
  onBackendChange: (backend: string) => void;
}

function ArtifactView({ activeStage, result, backend, theme, onBackendChange }: ArtifactViewProps) {
  if (activeStage === "overview") {
    return <PipelineOverview result={result} />;
  }
  if (activeStage === "tokens") {
    return <TokenPanel tokens={result?.tokens ?? null} theme={theme} />;
  }
  if (activeStage === "ast") {
    return <ASTPanel ast={result?.ast ?? null} theme={theme} />;
  }
  if (activeStage === "symbols") {
    return <SymbolTablePanel symbols={result?.symbols ?? null} />;
  }
  if (activeStage === "quads") {
    return <QuadruplePanel quadruples={result?.quadruples ?? null} />;
  }
  return (
    <AssemblyPanel
      assembly={result?.assembly ?? null}
      backend={backend}
      onBackendChange={onBackendChange}
    />
  );
}

function PipelineOverview({ result }: { result: CompileResult | null }) {
  const rows = [
    { name: "源码", detail: "输入的 NekoLang 文本", value: `${result?.source.split(/\r?\n/).length ?? 0} 行` },
    { name: "Tokens", detail: "带类别和位置的词法单元", value: `${result?.tokens.length ?? 0} 个` },
    { name: "AST", detail: "表达程序结构的树", value: result?.ast?.nodeType ?? "等待编译" },
    { name: "符号表", detail: "变量、函数、常量的登记结果", value: `${result?.symbols.entries.length ?? 0} 项` },
    { name: "四元式", detail: "线性的中间表示", value: `${result?.quadruples.length ?? 0} 行` },
    { name: "目标代码", detail: "LLVM IR 或 ARM64 文本", value: result?.assembly ? `${result.assembly.split(/\r?\n/).length} 行` : "等待生成" },
  ];

  return (
    <div className="overview-panel">
      {rows.map((row, index) => (
        <div className="overview-row" key={row.name}>
          <div className="overview-number">{index + 1}</div>
          <div>
            <strong>{row.name}</strong>
            <span>{row.detail}</span>
          </div>
          <code>{row.value}</code>
        </div>
      ))}
    </div>
  );
}
