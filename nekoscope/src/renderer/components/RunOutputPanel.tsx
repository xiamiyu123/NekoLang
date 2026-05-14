import { Terminal } from "lucide-react";
import type { RunResult } from "../types/compiler";

interface Props {
  result: RunResult | null;
  running: boolean;
}

export function RunOutputPanel({ result, running }: Props) {
  if (!result && !running) return null;

  return (
    <section className="run-output-panel" aria-live="polite">
      <div className="run-output-head">
        <div>
          <Terminal size={16} />
          <strong>运行结果</strong>
        </div>
        <code>{running ? "编译中" : result?.executablePath ? "已启动终端" : "编译失败"}</code>
      </div>

      {result?.compileError ? (
        <pre className="run-output-block error">{result.compileError}</pre>
      ) : null}

      {result && result.errors.length > 0 ? (
        <div className="run-output-errors">
          {result.errors.map((error, index) => (
            <article className="error-card" key={`${error.phase}-${error.line}-${error.column}-${index}`}>
              <div className="error-head">
                <span>{error.phase}</span>
                <span>第 {error.line} 行，第 {error.column} 列</span>
              </div>
              <div className="error-message">{error.message}</div>
              {error.sourceLine && <code className="error-source">{error.sourceLine}</code>}
              {error.suggestion && <div className="error-suggestion">{error.suggestion}</div>}
            </article>
          ))}
        </div>
      ) : null}

      {running ? (
        <div className="run-output-pending">正在编译并在终端中启动程序。</div>
      ) : result && result.errors.length === 0 && !result.compileError && result.executablePath ? (
        <div className="run-output-pending" style={{ color: "var(--leaf)" }}>
          程序已在系统终端中启动。
        </div>
      ) : null}
    </section>
  );
}
