import { join, normalize } from "node:path";
import { describe, expect, it } from "vitest";
import {
  createBuilderArgs,
  createPackageEnv,
  createUvExecutableCandidates,
  createUvResourcePath,
  formatTimestampVersion,
  getBundledUvName,
  resolvePackageBin,
} from "../../scripts/package.mjs";

describe("package script", () => {
  it("formats the default release version to the current UTC minute", () => {
    expect(formatTimestampVersion(new Date(Date.UTC(2026, 4, 13, 15, 7, 59)))).toBe("202605131507");
  });

  it("uses an explicit release version when provided", () => {
    const env = createPackageEnv(
      {
        NEKOSCOPE_RELEASE_VERSION: "custom-version",
        PATH: "/bin",
      },
      new Date(Date.UTC(2026, 4, 13, 15, 7))
    );

    expect(env).toEqual({
      NEKOSCOPE_RELEASE_VERSION: "custom-version",
      PATH: "/bin",
    });
  });

  it("generates a release version when none is provided", () => {
    const env = createPackageEnv({ PATH: "/bin" }, new Date(Date.UTC(2026, 4, 13, 15, 7)));

    expect(env).toEqual({
      NEKOSCOPE_RELEASE_VERSION: "202605131507",
      PATH: "/bin",
    });
  });

  it("passes npm script arguments through to electron-builder", () => {
    expect(createBuilderArgs(["node", "scripts/package.mjs", "--dir"], "/tmp/electron-builder")).toEqual([
      "/tmp/electron-builder",
      "--dir",
    ]);
  });

  it("resolves local package bins", () => {
    expect(normalize(resolvePackageBin("electron-vite"))).toContain("electron-vite");
    expect(normalize(resolvePackageBin("electron-builder"))).toContain("electron-builder");
  });

  it("uses a platform-specific uv resource path", () => {
    expect(createUvResourcePath("/repo/nekoscope", "darwin")).toBe(join("/repo/nekoscope", "resources", "bin", "uv"));
    expect(createUvResourcePath("/repo/nekoscope", "win32")).toBe(join("/repo/nekoscope", "resources", "bin", "uv.exe"));
  });

  it("builds uv executable candidates from PATH", () => {
    const pathValue = [join("/opt", "bin"), join("/usr", "local", "bin")].join(process.platform === "win32" ? ";" : ":");

    expect(createUvExecutableCandidates({ PATH: pathValue }, "linux")).toEqual([
      join("/opt", "bin", "uv"),
      join("/usr", "local", "bin", "uv"),
    ]);
  });

  it("names the bundled uv executable for each platform", () => {
    expect(getBundledUvName("linux")).toBe("uv");
    expect(getBundledUvName("darwin")).toBe("uv");
    expect(getBundledUvName("win32")).toBe("uv.exe");
  });
});
