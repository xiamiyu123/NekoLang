import type { LucideIcon } from "lucide-react";

export interface StageInfo {
  key: string;
  label: string;
  shortLabel: string;
  outputName: string;
  description: string;
  focus: string;
  blockedByErrors?: boolean;
  icon: LucideIcon;
}

interface Props {
  stages: StageInfo[];
  activeStage: string;
  completedStages: Set<string>;
  onSelect: (stage: string) => void;
}

export function StageGuide({ stages, activeStage, completedStages, onSelect }: Props) {
  return (
    <nav className="stage-guide" aria-label="编译阶段">
      {stages.map((stage, index) => {
        const Icon = stage.icon;
        const isActive = activeStage === stage.key;
        const isComplete = completedStages.has(stage.key);
        return (
          <button
            className={`stage-step ${isActive ? "active" : ""} ${isComplete ? "complete" : ""}`}
            key={stage.key}
            onClick={() => onSelect(stage.key)}
            type="button"
          >
            <span className="stage-index">{String(index + 1).padStart(2, "0")}</span>
            <span className="stage-icon"><Icon size={16} /></span>
            <span>
              <span className="stage-label">{stage.label}</span>
              <span className="stage-output">{stage.outputName}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
