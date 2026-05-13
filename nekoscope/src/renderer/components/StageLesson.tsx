import type { StageInfo } from "./StageGuide";

interface Props {
  stage: StageInfo;
}

export function StageLesson({ stage }: Props) {
  return (
    <aside className="lesson-panel">
      <div className="lesson-kicker">{stage.shortLabel}</div>
      <h2>{stage.label}</h2>
      <p>{stage.description}</p>
      <div className="lesson-focus">
        <span>阶段职责</span>
        <strong>{stage.focus}</strong>
      </div>
    </aside>
  );
}
