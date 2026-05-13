import { contextBridge } from "electron";

contextBridge.exposeInMainWorld("nekoscope", {
  apiUrl: "http://localhost:8000",
});
