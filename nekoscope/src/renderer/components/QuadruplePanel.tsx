import type { Quadruple } from "../types/compiler";

interface Props {
  quadruples: Quadruple[] | null;
}

function explainOperand(value: string): string {
  if (value === "_") return "空";
  if (value.startsWith("C")) return "常量";
  if (value.startsWith("I")) return "变量/符号";
  if (value.startsWith("T")) return "临时值";
  if (value.startsWith("L")) return "标签";
  return "值";
}

export function QuadruplePanel({ quadruples }: Props) {
  if (!quadruples) {
    return <div className="empty-panel">运行编译后可以看到四元式。</div>;
  }

  if (quadruples.length === 0) {
    return <div className="empty-panel">语义分析没有生成四元式。</div>;
  }

  return (
    <div className="data-panel">
      <table className="teaching-table dense">
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
          {quadruples.map((quad, index) => (
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
    </div>
  );
}
