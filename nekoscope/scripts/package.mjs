import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);

export function formatTimestampVersion(date = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");

  return [
    date.getUTCFullYear(),
    pad(date.getUTCMonth() + 1),
    pad(date.getUTCDate()),
    pad(date.getUTCHours()),
    pad(date.getUTCMinutes()),
  ].join("");
}

export function createPackageEnv(sourceEnv = process.env, date = new Date()) {
  return {
    ...sourceEnv,
    NEKOSCOPE_RELEASE_VERSION: sourceEnv.NEKOSCOPE_RELEASE_VERSION || formatTimestampVersion(date),
  };
}

export function resolvePackageBin(packageName, binName = packageName) {
  const packageJsonPath = require.resolve(`${packageName}/package.json`);
  const packageJson = require(packageJsonPath);
  const bin = typeof packageJson.bin === "string" ? packageJson.bin : packageJson.bin?.[binName];

  if (!bin) {
    throw new Error(`Cannot find ${binName} bin in ${packageName}`);
  }

  return path.resolve(path.dirname(packageJsonPath), bin);
}

export function createBuilderArgs(argv = process.argv, binPath = resolvePackageBin("electron-builder")) {
  return [binPath, ...argv.slice(2)];
}

function runNodeScript(args, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, args, {
      env,
      stdio: "inherit",
    });

    child.on("exit", (code, signal) => {
      if (signal) {
        reject(new Error(`Command was interrupted by ${signal}`));
        return;
      }

      if (code === 0) {
        resolve();
        return;
      }

      reject(new Error(`Command exited with code ${code}`));
    });

    child.on("error", reject);
  });
}

export async function runPackage({ argv = process.argv, sourceEnv = process.env } = {}) {
  const env = createPackageEnv(sourceEnv);
  console.log(`NekoScope release version: ${env.NEKOSCOPE_RELEASE_VERSION}`);

  await runNodeScript([resolvePackageBin("electron-vite"), "build"], env);
  await runNodeScript(createBuilderArgs(argv), env);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  runPackage().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
