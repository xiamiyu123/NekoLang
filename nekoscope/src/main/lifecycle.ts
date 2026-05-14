export interface NekoScopeLifecycle {
  platform: NodeJS.Platform;
  getWindowCount: () => number;
  ensureFastAPIReady: () => Promise<void>;
  stopFastAPI: () => void;
  createWindow: () => Promise<void>;
  quitApp: () => void;
}

export async function handleReady(lifecycle: NekoScopeLifecycle): Promise<void> {
  await lifecycle.ensureFastAPIReady();
  await lifecycle.createWindow();
}

export async function handleActivate(lifecycle: NekoScopeLifecycle): Promise<void> {
  if (lifecycle.getWindowCount() === 0) {
    await lifecycle.ensureFastAPIReady();
    await lifecycle.createWindow();
  }
}

export function handleBeforeQuit(lifecycle: NekoScopeLifecycle): void {
  lifecycle.stopFastAPI();
}

export function handleWindowAllClosed(lifecycle: NekoScopeLifecycle): void {
  if (lifecycle.platform !== "darwin") {
    lifecycle.stopFastAPI();
    lifecycle.quitApp();
  }
}
