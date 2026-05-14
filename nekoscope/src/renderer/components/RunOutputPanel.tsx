import { Terminal } from "lucide-react";
import type { RunResult } from "../types/compiler";

interface Props {
  result: RunResult | null;
  running: boolean;
}

function visibleText(value: string): string {
  return value.length > 0 ? value : "无输出";
}

export function RunOutputPanel({ result, running }: Props) {
  if (!result && !running) return null;

  const status = running
    ? "运行中"
    : result?.timedOut
      ? "运行超时"
      : `退出码 ${result?.exitCode ?? "-"}`;

  return (
    <section className={`run-output-panel ${result?.timedOut ? "timeout" : ""}`} aria-live="polite">
      <div className="run-output-head">
        <div>
          <Terminal size={16} />
          <strong>运行结果</strong>
        </div>
        <code>{status}</code>
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
        <div className="run-output-pending">正在编译并运行当前源码。</div>
      ) : result && result.errors.length === 0 && !result.compileError ? (
        <div className="run-output-grid">
          <div>
            <span>stdout</span>
            <pre className="run-output-block">{visibleText(result.stdout)}</pre>
          </div>
          <div>
            <span>stderr</span>
            <pre className="run-output-block">{visibleText(result.stderr)}</pre>
          </div>
        </div>
      ) : null}
    </section>
  );
}
