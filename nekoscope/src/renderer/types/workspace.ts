export interface WorkspaceFile {
  name: string;
  path: string;
  relativePath: string;
  isDirectory: boolean;
  children?: WorkspaceFile[];
}

export interface WorkspaceInfo {
  rootPath: string;
  projectName: string;
  entryFile: string | null;
  tree: WorkspaceFile;
}
