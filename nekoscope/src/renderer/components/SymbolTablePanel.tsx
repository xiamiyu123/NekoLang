import type { SymbolTableSnapshot } from "../types/compiler";

interface Props {
  symbols: SymbolTableSnapshot | null;
}

const categoryLabel: Record<string, string> = {
  v: "变量",
  f: "函数",
  p: "参数",
};

export function SymbolTablePanel({ symbols }: Props) {
  if (!symbols) {
    return <div className="empty-panel">运行编译后可以看到符号表。</div>;
  }

  const constants = Object.entries(symbols.constants);

  return (
    <div className="data-panel">
      <div className="table-card">
        <div className="table-title">标识符登记表</div>
        {symbols.entries.length === 0 ? (
          <div className="empty-panel compact">还没有登记任何名字。</div>
        ) : (
          <table className="teaching-table">
            <thead>
              <tr>
                <th>名字</th>
                <th>类型</th>
                <th>类别</th>
                <th>地址</th>
              </tr>
            </thead>
            <tbody>
              {symbols.entries.map((entry) => (
                <tr key={`${entry.name}-${entry.address}`}>
                  <td className="mono-cell">{entry.name}</td>
                  <td>{entry.type}</td>
                  <td>{categoryLabel[entry.category] ?? entry.category}</td>
                  <td className="mono-cell">{entry.address}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="table-card">
        <div className="table-title">常量池</div>
        {constants.length === 0 ? (
          <div className="empty-panel compact">这个程序暂时没有可展示的常量。</div>
        ) : (
          <table className="teaching-table">
            <thead>
              <tr>
                <th>字面量</th>
                <th>地址</th>
              </tr>
            </thead>
            <tbody>
              {constants.map(([literal, address]) => (
                <tr key={literal}>
                  <td className="mono-cell">{literal}</td>
                  <td className="mono-cell">{address}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
