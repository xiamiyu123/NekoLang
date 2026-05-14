import { app, BrowserWindow } from "electron";
import { spawn, ChildProcess } from "child_process";
import { join } from "path";
import {
  handleActivate,
  handleBeforeQuit,
  handleReady,
  handleWindowAllClosed,
  type NekoScopeLifecycle,
} from "./lifecycle";

const API_PORT = 8000;
let apiProcess: ChildProcess | null = null;

function getBackendRoot(): string {
  if (app.isPackaged) {
    return join(process.resourcesPath, "backend");
  }
  return join(__dirname, "../../..");
}

function getUvCommand(): string {
  if (app.isPackaged) {
    return join(process.resourcesPath, "bin", process.platform === "win32" ? "uv.exe" : "uv");
  }
  return "uv";
}

function createBackendEnv(): NodeJS.ProcessEnv {
  if (!app.isPackaged) return process.env;

  const backendDataRoot = join(app.getPath("userData"), "backend");
  return {
    ...process.env,
    UV_CACHE_DIR: join(backendDataRoot, "uv-cache"),
    UV_PROJECT_ENVIRONMENT: join(backendDataRoot, ".venv"),
  };
}

async function ensureFastAPIReady(): Promise<void> {
  if (apiProcess) return;

  apiProcess = spawn(getUvCommand(), ["run", "uvicorn", "neko.viz_api:app", "--port", String(API_PORT)], {
    cwd: getBackendRoot(),
    env: createBackendEnv(),
    stdio: ["ignore", "pipe", "pipe"],
  });

  apiProcess.stdout?.on("data", (data: Buffer) => {
    console.log(`[FastAPI] ${data.toString().trim()}`);
  });

  apiProcess.stderr?.on("data", (data: Buffer) => {
    console.error(`[FastAPI] ${data.toString().trim()}`);
  });

  apiProcess.on("exit", (code) => {
    console.log(`[FastAPI] exited with code ${code}`);
    apiProcess = null;
  });

  apiProcess.on("error", (error) => {
    console.error(`[FastAPI] failed to start: ${error.message}`);
    apiProcess = null;
  });

  await new Promise((resolve) => setTimeout(resolve, 1500));
}

function stopFastAPI(): void {
  if (apiProcess) {
    apiProcess.kill("SIGTERM");
    apiProcess = null;
  }
}

async function createWindow(): Promise<void> {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (!app.isPackaged) {
    // electron-vite sets ELECTRON_RENDERER_URL in dev mode
    const devUrl = process.env.ELECTRON_RENDERER_URL;
    if (devUrl) {
      await win.loadURL(devUrl);
    } else {
      // fallback to default Vite port
      await win.loadURL("http://localhost:5173");
    }
    win.webContents.openDevTools();
  } else {
    await win.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

const lifecycle: NekoScopeLifecycle = {
  platform: process.platform,
  getWindowCount: () => BrowserWindow.getAllWindows().length,
  ensureFastAPIReady,
  stopFastAPI,
  createWindow,
  quitApp: () => app.quit(),
};

app.whenReady().then(async () => {
  await handleReady(lifecycle);

  app.on("activate", async () => {
    await handleActivate(lifecycle);
  });
});

app.on("before-quit", () => {
  handleBeforeQuit(lifecycle);
});

app.on("window-all-closed", () => {
  handleWindowAllClosed(lifecycle);
});
