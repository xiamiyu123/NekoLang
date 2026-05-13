import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);

export function createDevEnv(sourceEnv = process.env) {
  const env = { ...sourceEnv };
  delete env.ELECTRON_RUN_AS_NODE;
  return env;
}

export function resolveElectronViteBin() {
  const packageJsonPath = require.resolve("electron-vite/package.json");
  const packageJson = require(packageJsonPath);

  return path.resolve(path.dirname(packageJsonPath), packageJson.bin["electron-vite"]);
}

export function createElectronViteArgs(argv = process.argv, binPath = resolveElectronViteBin()) {
  return [binPath, "dev", ...argv.slice(2)];
}

export function runDev({ argv = process.argv, sourceEnv = process.env, platform = process.platform } = {}) {
  const child = spawn(process.execPath, createElectronViteArgs(argv), {
    env: createDevEnv(sourceEnv),
    windowsHide: platform === "win32",
    stdio: "inherit",
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }

    process.exit(code ?? 0);
  });

  child.on("error", (error) => {
    console.error(error.message);
    process.exit(1);
  });

  return child;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  runDev();
}
