import { useCallback, useEffect, useRef } from "react";
import Editor, { type BeforeMount, type OnMount } from "@monaco-editor/react";
import { BookOpen, Play, RotateCcw } from "lucide-react";
import type { ResolvedTheme } from "../styles/theme";
import type { Example } from "../types/compiler";

interface Props {
  source: string;
  examples: Example[];
  activeExample: string | null;
  loading: boolean;
  theme: ResolvedTheme;
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
  theme,
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

  const handleBeforeMount: BeforeMount = useCallback((monaco) => {
    monaco.editor.defineTheme("nekoscope-light", {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "778292", fontStyle: "italic" },
        { token: "keyword", foreground: "775bd6", fontStyle: "bold" },
        { token: "number", foreground: "4f923f" },
        { token: "string", foreground: "b97712" },
      ],
      colors: {
        "editor.background": "#fbfcff",
        "editor.foreground": "#24313d",
        "editor.lineHighlightBackground": "#edf2fb",
        "editorLineNumber.foreground": "#9aa8b8",
        "editorCursor.foreground": "#2f73d9",
        "editor.selectionBackground": "#c9dcff",
        "editor.inactiveSelectionBackground": "#e6eefc",
      },
    });

    monaco.editor.defineTheme("nekoscope-neko", {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "b77f96", fontStyle: "italic" },
        { token: "keyword", foreground: "c65fcf", fontStyle: "bold" },
        { token: "number", foreground: "62a85b" },
        { token: "string", foreground: "e78b2f" },
      ],
      colors: {
        "editor.background": "#fffafd",
        "editor.foreground": "#463240",
        "editor.lineHighlightBackground": "#ffe8f2",
        "editorLineNumber.foreground": "#c995ad",
        "editorCursor.foreground": "#ff6fa5",
        "editor.selectionBackground": "#ffc9df",
        "editor.inactiveSelectionBackground": "#ffe3ef",
        "editorIndentGuide.background1": "#f4c9d9",
        "editorIndentGuide.activeBackground1": "#e996b6",
      },
    });
  }, []);

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
          beforeMount={handleBeforeMount}
          onMount={handleEditorMount}
          theme={theme === "dark" ? "vs-dark" : theme === "neko" ? "nekoscope-neko" : "nekoscope-light"}
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
