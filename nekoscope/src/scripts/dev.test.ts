import { readFile } from "node:fs/promises";
import { join, normalize } from "node:path";
import { describe, expect, it } from "vitest";
import { createDevEnv, createElectronViteArgs, resolveElectronViteBin } from "../../scripts/dev.mjs";

const packageJsonPath = join(process.cwd(), "package.json");

describe("dev script", () => {
  it("does not rely on POSIX-only shell commands", async () => {
    const packageJson = JSON.parse(await readFile(packageJsonPath, "utf8"));

    expect(packageJson.scripts.dev).not.toContain("unset ");
    expect(packageJson.scripts.dev).toBe("node ./scripts/dev.mjs");
  });

  it("clears ELECTRON_RUN_AS_NODE before starting electron-vite", () => {
    const env = createDevEnv({
      ELECTRON_RUN_AS_NODE: "1",
      PATH: "/bin",
    });

    expect(env).toEqual({ PATH: "/bin" });
  });

  it("passes npm script arguments through to electron-vite dev", () => {
    expect(
      createElectronViteArgs(["node", "scripts/dev.mjs", "--host", "127.0.0.1"], "/tmp/electron-vite")
    ).toEqual([
      "/tmp/electron-vite",
      "dev",
      "--host",
      "127.0.0.1",
    ]);
  });

  it("resolves the local electron-vite bin script", () => {
    expect(normalize(resolveElectronViteBin())).toContain(
      join("node_modules", "electron-vite", "bin", "electron-vite.js")
    );
  });
});
