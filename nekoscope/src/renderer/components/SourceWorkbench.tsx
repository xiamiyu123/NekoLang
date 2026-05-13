import { useCallback, useEffect, useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
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
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const shellRef = useRef<HTMLDivElement | null>(null);
  const layoutFrameRef = useRef<number | null>(null);

  const layoutEditor = useCallback(() => {
    if (layoutFrameRef.current != null) {
      cancelAnimationFrame(layoutFrameRef.current);
    }
    layoutFrameRef.current = requestAnimationFrame(() => {
      layoutFrameRef.current = null;
      editorRef.current?.layout();
    });
  }, []);

  const handleEditorMount: OnMount = useCallback((editor) => {
    editorRef.current = editor;
    layoutEditor();
  }, [layoutEditor]);

  useEffect(() => {
    const shell = shellRef.current;
    if (!shell) return undefined;

    const observer = new ResizeObserver(layoutEditor);
    observer.observe(shell);
    window.addEventListener("resize", layoutEditor);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", layoutEditor);
      if (layoutFrameRef.current != null) {
        cancelAnimationFrame(layoutFrameRef.current);
      }
    };
  }, [layoutEditor]);

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

      <div className="editor-shell" ref={shellRef}>
        <Editor
          height="100%"
          defaultLanguage="scheme"
          value={source}
          onChange={(value) => onSourceChange(value ?? "")}
          onMount={handleEditorMount}
          theme="vs-dark"
          options={{
            automaticLayout: true,
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
