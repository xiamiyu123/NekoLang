import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { CompileError } from "../types/compiler";

interface Props {
  errors: CompileError[];
  loading: boolean;
}

export function DiagnosticPanel({ errors, loading }: Props) {
  if (loading) {
    return (
      <section className="diagnostic-panel pending" aria-live="polite">
        <div className="diagnostic-icon"><AlertTriangle size={16} /></div>
        <div>
          <div className="diagnostic-title">正在编译</div>
          <div className="diagnostic-copy">源码改动会在短暂等待后自动进入编译管线。</div>
        </div>
      </section>
    );
  }

  if (errors.length === 0) {
    return (
      <section className="diagnostic-panel ok" aria-live="polite">
        <div className="diagnostic-icon"><CheckCircle2 size={16} /></div>
        <div>
          <div className="diagnostic-title">编译通过</div>
          <div className="diagnostic-copy">可以切换阶段查看每一步的产物。</div>
        </div>
      </section>
    );
  }

  return (
    <section className="diagnostic-panel error" aria-live="polite">
      <div className="diagnostic-icon"><AlertTriangle size={16} /></div>
      <div className="diagnostic-list">
        <div className="diagnostic-title">{errors.length} 个错误阻止了后续阶段</div>
        {errors.map((error, index) => (
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
    </section>
  );
}
