import { useState } from "react";
import type { Quadruple, QuadrupleOptimization } from "../types/compiler";

interface Props {
  quadruples: Quadruple[] | null;
  optimization?: QuadrupleOptimization | null;
}

type QuadView = "initial" | "process" | "optimized";

function explainOperand(value: string): string {
  if (value === "_") return "空";
  if (value.startsWith("C")) return "常量";
  if (value.startsWith("I")) return "变量/符号";
  if (value.startsWith("T")) return "临时值";
  if (value.startsWith("L")) return "标签";
  return "值";
}

function QuadTable({ rows, label }: { rows: Quadruple[]; label: string }) {
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
          <tr key={`${index}-${quad.op}-${quad.t}`}>
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

export function QuadruplePanel({ quadruples, optimization }: Props) {
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
                </div>
              ))
            )}
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
