import { useState } from "react";
import { ChevronRight, File, Folder, FolderOpen } from "lucide-react";
import type { WorkspaceFile } from "../types/workspace";

interface Props {
  files: WorkspaceFile[];
  activeFilePath: string | null;
  onFileSelect: (file: WorkspaceFile) => void;
}

export function FileTree({ files, activeFilePath, onFileSelect }: Props) {
  if (files.length === 0) {
    return (
      <div className="file-tree-empty">
        <File size={16} />
        <span>No .neko files found</span>
      </div>
    );
  }

  return (
    <div className="file-tree" role="tree">
      {files.map((file) => (
        <FileTreeNode
          key={file.path}
          file={file}
          depth={0}
          activeFilePath={activeFilePath}
          onFileSelect={onFileSelect}
        />
      ))}
    </div>
  );
}

interface NodeProps {
  file: WorkspaceFile;
  depth: number;
  activeFilePath: string | null;
  onFileSelect: (file: WorkspaceFile) => void;
}

function FileTreeNode({ file, depth, activeFilePath, onFileSelect }: NodeProps) {
  const [expanded, setExpanded] = useState(depth < 1);
  const isActive = file.path === activeFilePath;

  if (file.isDirectory) {
    const hasChildren = file.children && file.children.length > 0;
    return (
      <div role="treeitem" aria-expanded={expanded}>
        <button
          className={`file-tree-node directory ${isActive ? "active" : ""}`}
          style={{ paddingLeft: `${8 + depth * 16}px` }}
          onClick={() => hasChildren && setExpanded(!expanded)}
          type="button"
        >
          <ChevronRight
            size={14}
            className={`chevron ${expanded ? "expanded" : ""}`}
            style={{ visibility: hasChildren ? "visible" : "hidden" }}
          />
          {expanded ? <FolderOpen size={15} /> : <Folder size={15} />}
          <span>{file.name}</span>
        </button>
        {expanded && file.children && (
          <div role="group">
            {file.children.map((child) => (
              <FileTreeNode
                key={child.path}
                file={child}
                depth={depth + 1}
                activeFilePath={activeFilePath}
                onFileSelect={onFileSelect}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div role="treeitem">
      <button
        className={`file-tree-node file ${isActive ? "active" : ""}`}
        style={{ paddingLeft: `${22 + depth * 16}px` }}
        onClick={() => onFileSelect(file)}
        type="button"
      >
        <File size={15} />
        <span>{file.name}</span>
      </button>
    </div>
  );
}
