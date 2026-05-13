import { app, BrowserWindow } from "electron";
import { spawn, ChildProcess } from "child_process";
import { join } from "path";

const API_PORT = 8000;
let apiProcess: ChildProcess | null = null;

function startFastAPI(): void {
  const projectRoot = join(__dirname, "../../..");
  apiProcess = spawn("uv", ["run", "uvicorn", "neko.viz_api:app", "--port", String(API_PORT)], {
    cwd: projectRoot,
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
    await win.loadURL("http://localhost:5173");
    win.webContents.openDevTools();
  } else {
    await win.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

app.whenReady().then(async () => {
  startFastAPI();
  await new Promise((resolve) => setTimeout(resolve, 1500));
  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

app.on("before-quit", () => {
  stopFastAPI();
});

app.on("window-all-closed", () => {
  stopFastAPI();
  if (process.platform !== "darwin") {
    app.quit();
  }
});
