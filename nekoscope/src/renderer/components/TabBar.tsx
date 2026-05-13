import { colors } from "../styles/theme";

export interface Tab {
  key: string;
  label: string;
}

interface Props {
  tabs: Tab[];
  active: string;
  onChange: (key: string) => void;
}

export function TabBar({ tabs, active, onChange }: Props) {
  return (
    <div style={{ display: "flex", gap: 2, borderBottom: `1px solid ${colors.surface0}` }}>
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            style={{
              background: isActive ? colors.surface0 : "transparent",
              color: isActive ? colors.pink : colors.overlay0,
              border: "none",
              padding: "6px 14px",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              borderRadius: "6px 6px 0 0",
              transition: "background 0.15s, color 0.15s",
            }}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
