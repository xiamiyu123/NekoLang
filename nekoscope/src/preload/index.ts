import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("nekoscope", {
  apiUrl: "http://localhost:8000",
  openFile: () => ipcRenderer.invoke("dialog:openFile"),
  openFolder: () => ipcRenderer.invoke("dialog:openFolder"),
  readFile: (path: string) => ipcRenderer.invoke("fs:readFile", path),
});
