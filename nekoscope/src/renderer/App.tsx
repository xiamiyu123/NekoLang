import { useState, useEffect, useCallback, useRef } from "react";
import Editor from "@monaco-editor/react";
import { compile, getExamples, getExampleSource } from "./api/client";
import type { CompileResult, Example } from "./types/compiler";

const DEFAULT_SOURCE = `(nya t
  (nyan ((a int) (b int)))
  (paw
    (:= a 10)
    (:= b (+ a 32))
    (meow b)))`;

export default function App() {
  const [source, setSource] = useState(DEFAULT_SOURCE);
  const [result, setResult] = useState<CompileResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [examples, setExamples] = useState<Example[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Load examples on mount
  useEffect(() => {
    getExamples().then(setExamples).catch(console.error);
  }, []);

  // Compile on source change (debounced)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setLoading(true);
      compile(source, "llvm")
        .then(setResult)
        .catch(console.error)
        .finally(() => setLoading(false));
    }, 500);
    return () => clearTimeout(debounceRef.current);
  }, [source]);

  const loadExample = useCallback(async (name: string) => {
    const src = await getExampleSource(name);
    setSource(src);
  }, []);

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      {/* Sidebar */}
      <div style={{ width: 200, background: "#1e1e2e", color: "#cdd6f4", padding: 12, overflowY: "auto" }}>
        <h3 style={{ margin: "0 0 8px", fontSize: 14, color: "#f5c2e7" }}>
          NekoScope
        </h3>
        <div style={{ fontSize: 11, color: "#6c7086", marginBottom: 12 }}>
          Examples
        </div>
        {examples.map((ex) => (
          <div
            key={ex.name}
            onClick={() => loadExample(ex.name)}
            style={{
              padding: "6px 8px",
              cursor: "pointer",
              borderRadius: 4,
              fontSize: 13,
              marginBottom: 2,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#313244")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            {ex.description}
          </div>
        ))}
      </div>

      {/* Editor */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <div style={{ flex: 1, borderBottom: "1px solid #313244" }}>
          <Editor
            height="100%"
            defaultLanguage="scheme"
            value={source}
            onChange={(v) => setSource(v ?? "")}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              lineNumbersMinChars: 3,
              scrollBeyondLastLine: false,
            }}
          />
        </div>

        {/* Output */}
        <div style={{ height: "45%", overflow: "auto", background: "#181825", padding: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ color: "#f5c2e7", fontWeight: 600, fontSize: 13 }}>
              Compilation Result
            </span>
            {loading && <span style={{ color: "#6c7086", fontSize: 12 }}>compiling...</span>}
            {result && !loading && (
              <span style={{ color: result.errors.length ? "#f38ba8" : "#a6e3a1", fontSize: 12 }}>
                {result.errors.length
                  ? `${result.errors.length} error(s)`
                  : `${result.tokens.length} tokens`}
              </span>
            )}
          </div>
          {result && (
            <pre style={{
              color: "#cdd6f4",
              fontSize: 12,
              lineHeight: 1.5,
              whiteSpace: "pre-wrap",
              margin: 0,
            }}>
              {result.errors.length > 0
                ? result.errors.map((e) => `[${e.phase}] Line ${e.line}: ${e.message}`).join("\n")
                : `AST: ${result.ast.nodeType}(${(result.ast as Record<string, unknown>).name ?? ""})
Tokens: ${result.tokens.length}
Assembly (${result.assembly.includes("define") ? "LLVM" : "ARM64"}):
${result.assembly.slice(0, 500)}${result.assembly.length > 500 ? "\n..." : ""}`}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
