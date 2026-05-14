import { PanelLeftClose } from "lucide-react";
import type { StageInfo } from "./StageGuide";

interface Props {
  stage: StageInfo;
  onCollapse: () => void;
}

export function StageLesson({ stage, onCollapse }: Props) {
  return (
    <aside className="lesson-panel">
      <div className="lesson-header">
        <div>
          <div className="lesson-kicker">{stage.shortLabel}</div>
          <h2>{stage.label}</h2>
        </div>
        <button
          className="icon-button lesson-toggle"
          type="button"
          onClick={onCollapse}
          title="折叠阶段说明"
          aria-label="折叠阶段说明"
        >
          <PanelLeftClose size={16} />
        </button>
      </div>
      <p>{stage.description}</p>
      <div className="lesson-focus">
        <span>阶段职责</span>
        <strong>{stage.focus}</strong>
      </div>
    </aside>
  );
}
