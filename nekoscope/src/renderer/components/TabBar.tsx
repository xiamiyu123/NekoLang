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
    <div className="tab-bar">
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            className={`tab-button ${isActive ? "active" : ""}`}
            onClick={() => onChange(tab.key)}
            type="button"
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
