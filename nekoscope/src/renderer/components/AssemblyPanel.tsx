interface Props {
  assembly: string | null;
  backend: string;
  onBackendChange: (backend: string) => void;
}

export function AssemblyPanel({ assembly, backend, onBackendChange }: Props) {
  return (
    <div className="assembly-panel">
      <div className="backend-control">
        <span>目标后端</span>
        <select
          value={backend}
          onChange={(e) => onBackendChange(e.target.value)}
        >
          <option value="llvm">LLVM IR</option>
          <option value="arm64">ARM64</option>
        </select>
      </div>
      {assembly == null ? (
        <div className="empty-panel">
          运行编译后可以看到目标代码。
        </div>
      ) : (
        <pre className="code-output">
          {assembly}
        </pre>
      )}
    </div>
  );
}
