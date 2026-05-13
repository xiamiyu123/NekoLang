import Editor from "@monaco-editor/react";
import { BookOpen, Play, RotateCcw } from "lucide-react";
import type { Example } from "../types/compiler";

interface Props {
  source: string;
  examples: Example[];
  activeExample: string | null;
  loading: boolean;
  onSourceChange: (source: string) => void;
  onExampleLoad: (name: string) => void;
  onCompileNow: () => void;
  onReset: () => void;
}

export function SourceWorkbench({
  source,
  examples,
  activeExample,
  loading,
  onSourceChange,
  onExampleLoad,
  onCompileNow,
  onReset,
}: Props) {
  return (
    <section className="source-workbench">
      <header className="panel-heading">
        <div>
          <div className="panel-kicker">Source</div>
          <h2>源码编辑器</h2>
        </div>
        <div className="toolbar">
          <button className="icon-button" type="button" onClick={onCompileNow} title="立即编译">
            <Play size={16} />
          </button>
          <button className="icon-button" type="button" onClick={onReset} title="恢复默认示例">
            <RotateCcw size={16} />
          </button>
        </div>
      </header>

      <div className="editor-shell">
        <Editor
          height="100%"
          defaultLanguage="scheme"
          value={source}
          onChange={(value) => onSourceChange(value ?? "")}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            fontLigatures: true,
            lineNumbersMinChars: 3,
            scrollBeyondLastLine: false,
            tabSize: 2,
            wordWrap: "on",
          }}
        />
      </div>

      <div className="example-strip" aria-label="示例程序">
        <div className="example-strip-title">
          <BookOpen size={15} />
          示例
        </div>
        <div className="example-list">
          {examples.map((example) => (
            <button
              className={`example-chip ${activeExample === example.name ? "active" : ""}`}
              type="button"
              key={example.name}
              onClick={() => onExampleLoad(example.name)}
            >
              {example.description}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="compile-pulse">编译中</div>}
    </section>
  );
}
