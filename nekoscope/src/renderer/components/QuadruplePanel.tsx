import { useState } from "react";
import type { Quadruple, QuadrupleDag, QuadrupleOptimization, QuadrupleOptimizationStep } from "../types/compiler";
import { QuadrupleDagPanel } from "./QuadrupleDagPanel";
import type { ResolvedTheme } from "../styles/theme";
import { buildQuadrupleDag } from "../quadrupleDag";

interface Props {
  quadruples: Quadruple[] | null;
  optimization?: QuadrupleOptimization | null;
  dag?: QuadrupleDag | null;
  theme: ResolvedTheme;
}

type QuadView = "initial" | "process" | "optimized";
type QuadRowTone = "normal" | "removed" | "rewritten-before" | "rewritten-after";

function explainOperand(value: string): string {
  if (value === "_") return "空";
  if (value.startsWith("C")) return "常量";
  if (value.startsWith("I")) return "变量/符号";
  if (value.startsWith("T")) return "临时值";
  if (value.startsWith("L")) return "标签";
  return "值";
}

function QuadTable({
  rows,
  label,
  tone = "normal",
}: {
  rows: Quadruple[];
  label: string;
  tone?: QuadRowTone;
}) {
  return (
    <table className="teaching-table dense" aria-label={label}>
      <thead>
        <tr>
          <th>#</th>
          <th>操作</th>
          <th>参数 1</th>
          <th>参数 2</th>
          <th>结果</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((quad, index) => (
          <tr className={tone === "normal" ? undefined : `quad-row-${tone}`} key={`${index}-${quad.op}-${quad.t}`}>
            <td className="mono-cell muted">{index}</td>
            <td><span className="op-pill">{quad.op}</span></td>
            <td className="mono-cell" title={explainOperand(quad.ob1)}>{quad.ob1}</td>
            <td className="mono-cell" title={explainOperand(quad.ob2)}>{quad.ob2}</td>
            <td className="mono-cell" title={explainOperand(quad.t)}>{quad.t}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RewrittenQuadTable({ step }: { step: QuadrupleOptimizationStep }) {
  const rows = step.rewrittenRows ?? [];
  if (rows.length === 0) return null;

  return (
    <table className="teaching-table dense" aria-label={`${step.name} 改写的四元式`}>
      <thead>
        <tr>
          <th>#</th>
          <th>改写前</th>
          <th>改写后</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={`${index}-${row.before.op}-${row.after.op}`}>
            <td className="mono-cell muted">{index}</td>
            <td>
              <QuadInlineRow quad={row.before} tone="rewritten-before" />
            </td>
            <td>
              <QuadInlineRow quad={row.after} tone="rewritten-after" />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function QuadInlineRow({ quad, tone }: { quad: Quadruple; tone: QuadRowTone }) {
  return (
    <span className={`quad-inline-row quad-row-${tone}`}>
      <span className="op-pill">{quad.op}</span>
      <code>{quad.ob1}</code>
      <code>{quad.ob2}</code>
      <code>{quad.t}</code>
    </span>
  );
}

function StepQuadTables({ step }: { step: QuadrupleOptimizationStep }) {
  const removedRows = step.removedRows ?? [];
  const rewrittenRows = step.rewrittenRows ?? [];
  const afterRows = step.afterRows ?? [];
  if (removedRows.length === 0 && rewrittenRows.length === 0 && afterRows.length === 0) return null;

  return (
    <div className="quad-step-body">
      {rewrittenRows.length > 0 ? (
        <div className="quad-step-table">
          <div className="quad-step-table-title">本阶段改写</div>
          <RewrittenQuadTable step={step} />
        </div>
      ) : null}
      {removedRows.length > 0 ? (
        <div className="quad-step-table">
          <div className="quad-step-table-title">本阶段已删除</div>
          <QuadTable rows={removedRows} label={`${step.name} 已删除的四元式`} tone="removed" />
        </div>
      ) : null}
      <div className="quad-step-table">
        <div className="quad-step-table-title">本阶段优化后</div>
        <QuadTable rows={afterRows} label={`${step.name} 优化后四元式`} />
      </div>
    </div>
  );
}

function ConstantMap({ constants }: { constants?: Record<string, string | number> }) {
  const entries = Object.entries(constants ?? {});
  if (entries.length === 0) return null;

  return (
    <div className="quad-constants" aria-label="常量地址映射">
      {entries.map(([value, address]) => (
        <code key={`${address}-${value}`}>{address} = {value}</code>
      ))}
    </div>
  );
}

export function QuadruplePanel({ quadruples, optimization, dag, theme }: Props) {
  const [activeView, setActiveView] = useState<QuadView>("initial");

  if (!quadruples) {
    return <div className="empty-panel">运行编译后可以看到四元式。</div>;
  }

  if (quadruples.length === 0) {
    return <div className="empty-panel">语义分析没有生成四元式。</div>;
  }

  const initialRows = optimization?.initial ?? quadruples;
  const optimizedRows = optimization?.optimized ?? quadruples;
  const steps = optimization?.steps ?? [];
  const fallbackDag = buildQuadrupleDag(initialRows, optimization?.initialConstants);
  const visibleDag = dag && dag.blocks.length > 0 ? dag : fallbackDag;

  return (
    <div className="quad-panel">
      <div className="quad-toolbar" role="tablist" aria-label="四元式视图">
        <button
          className={`tab-button ${activeView === "initial" ? "active" : ""}`}
          type="button"
          role="tab"
          aria-selected={activeView === "initial"}
          onClick={() => setActiveView("initial")}
        >
          初始
        </button>
        <button
          className={`tab-button ${activeView === "process" ? "active" : ""}`}
          type="button"
          role="tab"
          aria-selected={activeView === "process"}
          onClick={() => setActiveView("process")}
        >
          优化过程
        </button>
        <button
          className={`tab-button ${activeView === "optimized" ? "active" : ""}`}
          type="button"
          role="tab"
          aria-selected={activeView === "optimized"}
          onClick={() => setActiveView("optimized")}
        >
          优化结果
        </button>
      </div>

      <div className="data-panel">
        {optimization ? (
          <div className={`quad-summary ${optimization.changed ? "changed" : ""}`}>
            <div>
              <span>{optimization.source} · {optimization.level}</span>
              <strong>{optimization.changed ? "已生成优化后四元式" : "本次优化没有改变四元式"}</strong>
            </div>
            <code>{optimization.beforeCount} 行{" -> "}{optimization.afterCount} 行</code>
          </div>
        ) : null}

        {activeView === "initial" ? (
          <>
            <ConstantMap constants={optimization?.initialConstants} />
            <QuadTable rows={initialRows} label="初始四元式" />
          </>
        ) : null}

        {activeView === "process" ? (
          <div className="quad-process">
            <QuadrupleDagPanel dag={visibleDag} theme={theme} />
            <div className="quad-steps">
              {steps.length === 0 ? (
                <div className="empty-panel compact">当前编译结果没有提供优化过程。</div>
              ) : (
                steps.map((step, index) => (
                  <div className="quad-step" key={`${index}-${step.name}`}>
                    <span className={`quad-step-index ${step.changed ? "changed" : ""}`}>
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <strong>{step.name}</strong>
                      <p>{step.detail}</p>
                    </div>
                    <code>{step.beforeCount}{" -> "}{step.afterCount}</code>
                    <StepQuadTables step={step} />
                  </div>
                ))
              )}
            </div>
          </div>
        ) : null}

        {activeView === "optimized" ? (
          <>
            <ConstantMap constants={optimization?.optimizedConstants} />
            <QuadTable rows={optimizedRows} label="优化后四元式" />
          </>
        ) : null}
      </div>
    </div>
  );
}
