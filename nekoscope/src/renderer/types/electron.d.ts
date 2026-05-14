interface NekoScopeAPI {
  apiUrl: string;
  openFile: () => Promise<string | null>;
  openFolder: () => Promise<string | null>;
  readFile: (path: string) => Promise<string>;
}

interface Window {
  nekoscope: NekoScopeAPI;
}
