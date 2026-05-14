interface NekoScopeAPI {
  apiUrl: string;
  openFile: () => Promise<string | null>;
  openFolder: () => Promise<string | null>;
  readFile: (path: string) => Promise<string>;
  writeFile: (path: string, content: string) => Promise<void>;
  saveFile: (defaultPath?: string) => Promise<string | null>;
}

interface Window {
  nekoscope: NekoScopeAPI;
}
