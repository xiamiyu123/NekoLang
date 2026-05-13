import type { Token } from "../types/compiler";
import { tokenColor } from "../styles/theme";

interface Props {
  tokens: Token[] | null;
}

export function TokenPanel({ tokens }: Props) {
  if (!tokens) {
    return (
      <div className="empty-panel">运行编译后可以看到词法单元。</div>
    );
  }
  if (tokens.length === 0) {
    return (
      <div className="empty-panel">没有生成词法单元。</div>
    );
  }
  return (
    <div className="token-grid">
      {tokens.map((t, i) => (
        <div
          key={i}
          className="token-card"
        >
          <span
            className="token-type"
            style={{ background: tokenColor(t.type) }}
          >
            {t.type}
          </span>
          <span className="token-value">{t.value}</span>
          <span className="token-location">
            {t.line}:{t.column}
          </span>
        </div>
      ))}
    </div>
  );
}
