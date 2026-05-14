import { describe, expect, it, vi } from "vitest";
import {
  handleActivate,
  handleBeforeQuit,
  handleReady,
  handleWindowAllClosed,
  type NekoScopeLifecycle,
} from "../lifecycle";

function createLifecycle(overrides: Partial<NekoScopeLifecycle> = {}): NekoScopeLifecycle {
  return {
    platform: "darwin",
    getWindowCount: vi.fn(() => 0),
    ensureFastAPIReady: vi.fn(async () => {}),
    stopFastAPI: vi.fn(),
    createWindow: vi.fn(async () => {}),
    quitApp: vi.fn(),
    ...overrides,
  };
}

describe("NekoScope main lifecycle", () => {
  it("starts FastAPI before opening the first window", async () => {
    const lifecycle = createLifecycle();

    await handleReady(lifecycle);

    expect(lifecycle.ensureFastAPIReady).toHaveBeenCalledOnce();
    expect(lifecycle.createWindow).toHaveBeenCalledOnce();
  });

  it("keeps FastAPI running when the last macOS window closes", () => {
    const lifecycle = createLifecycle({ platform: "darwin" });

    handleWindowAllClosed(lifecycle);

    expect(lifecycle.stopFastAPI).not.toHaveBeenCalled();
    expect(lifecycle.quitApp).not.toHaveBeenCalled();
  });

  it("restarts FastAPI before reopening a macOS window from the Dock", async () => {
    const lifecycle = createLifecycle({ platform: "darwin", getWindowCount: vi.fn(() => 0) });

    await handleActivate(lifecycle);

    expect(lifecycle.ensureFastAPIReady).toHaveBeenCalledOnce();
    expect(lifecycle.createWindow).toHaveBeenCalledOnce();
  });

  it("does not reopen a window when one already exists", async () => {
    const lifecycle = createLifecycle({ getWindowCount: vi.fn(() => 1) });

    await handleActivate(lifecycle);

    expect(lifecycle.ensureFastAPIReady).not.toHaveBeenCalled();
    expect(lifecycle.createWindow).not.toHaveBeenCalled();
  });

  it("stops FastAPI when non-macOS windows close and the app quits", () => {
    const lifecycle = createLifecycle({ platform: "linux" });

    handleWindowAllClosed(lifecycle);

    expect(lifecycle.stopFastAPI).toHaveBeenCalledOnce();
    expect(lifecycle.quitApp).toHaveBeenCalledOnce();
  });

  it("stops FastAPI when the app is quitting", () => {
    const lifecycle = createLifecycle();

    handleBeforeQuit(lifecycle);

    expect(lifecycle.stopFastAPI).toHaveBeenCalledOnce();
  });
});
