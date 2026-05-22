export type ThemePreference = "system" | "light" | "dark" | "neko";
export type ResolvedTheme = Exclude<ThemePreference, "system">;

export const themePreferenceOrder: ThemePreference[] = ["system", "light", "dark", "neko"];

export const themePreferenceLabels: Record<ThemePreference, string> = {
  system: "跟随系统",
  light: "日间模式",
  dark: "夜间模式",
  neko: "猫猫模式",
};

export const themePreferenceDescriptions: Record<ThemePreference, string> = {
  system: "跟随系统主题",
  light: "切换到日间模式",
  dark: "切换到夜间模式",
  neko: "切换到粉嫩猫猫模式",
};

export const THEME_STORAGE_KEY = "nekoscope.themePreference";

export function isThemePreference(value: string | null): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark" || value === "neko";
}

function getStorage(): Storage | null {
  if (typeof window === "undefined" || !window.localStorage) return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadThemePreference(): ThemePreference {
  const storedPreference = getStorage()?.getItem(THEME_STORAGE_KEY) ?? null;
  return isThemePreference(storedPreference) ? storedPreference : "system";
}

export function saveThemePreference(preference: ThemePreference): void {
  try {
    getStorage()?.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Some test and browser privacy contexts expose localStorage but reject writes.
  }
}

export function resolveTheme(preference: ThemePreference, systemPrefersDark: boolean): ResolvedTheme {
  if (preference === "system") return systemPrefersDark ? "dark" : "light";
  return preference;
}

export function nextThemePreference(preference: ThemePreference): ThemePreference {
  const index = themePreferenceOrder.indexOf(preference);
  return themePreferenceOrder[(index + 1) % themePreferenceOrder.length];
}

/** Catppuccin Mocha — cat-themed fallback palette for older inline helpers */
export const colors = {
  base: "#1e1e2e",
  mantle: "#181825",
  surface0: "#313244",
  surface1: "#45475a",
  surface2: "#585b70",
  overlay0: "#6c7086",
  overlay1: "#7f849c",
  overlay2: "#9399b2",
  subtext0: "#a6adc8",
  subtext1: "#bac2de",
  text: "#cdd6f4",
  lavender: "#b4befe",
  blue: "#89b4fa",
  sky: "#89dceb",
  teal: "#94e2d5",
  green: "#a6e3a1",
  yellow: "#f9e2af",
  peach: "#fab387",
  red: "#f38ba8",
  maroon: "#eba0ac",
  mauve: "#cba6f7",
  pink: "#f5c2e7",
  rosewater: "#f5e0dc",
  flamingo: "#f2cdcd",
} as const;

export type ColorKey = keyof typeof colors;

/** Token-type -> color mapping for TokenPanel */
export const tokenColors: Record<ResolvedTheme, Record<string, string>> = {
  dark: {
    keyword: colors.mauve,
    identifier: colors.blue,
    literal: colors.green,
    operator: colors.peach,
    delimiter: colors.overlay0,
    program: colors.pink,
    type: colors.sky,
    fallback: colors.overlay1,
  },
  light: {
    keyword: "#8763d6",
    identifier: "#2f73d9",
    literal: "#4d9c3f",
    operator: "#b97712",
    delimiter: "#8a99a8",
    program: "#d24f82",
    type: "#2f8fbb",
    fallback: "#61707f",
  },
  neko: {
    keyword: "#c65fcf",
    identifier: "#6b88e8",
    literal: "#62b45b",
    operator: "#f0a23a",
    delimiter: "#b77f96",
    program: "#ff79aa",
    type: "#39b7a8",
    fallback: "#8b5d70",
  },
};

export function tokenColor(tokenType: string, theme: ResolvedTheme = "dark"): string {
  const t = tokenType.toLowerCase();
  const palette = tokenColors[theme];
  if (t === "int" || t === "float" || t === "string" || t === "bool") return palette.type;
  if (t === "true" || t === "false") return palette.literal;
  return palette[t] ?? palette.fallback;
}

export const astThemeColors: Record<
  ResolvedTheme,
  {
    background: string;
    controlBackground: string;
    edge: string;
    handle: string;
    minimap: string;
    minimapNode: string;
    minimapMask: string;
  }
> = {
  dark: {
    background: "#313244",
    controlBackground: "#313244",
    edge: "#6c7086",
    handle: "#45475a",
    minimap: "#181825",
    minimapNode: "#45475a",
    minimapMask: "#1e1e2edd",
  },
  light: {
    background: "#d6dde7",
    controlBackground: "#ffffff",
    edge: "#9aa8b8",
    handle: "#9aa8b8",
    minimap: "#f7f8fc",
    minimapNode: "#d6dde7",
    minimapMask: "#f7f7fbdd",
  },
  neko: {
    background: "#f3b9cd",
    controlBackground: "#fffafd",
    edge: "#d89ab3",
    handle: "#f19abd",
    minimap: "#ffe8f2",
    minimapNode: "#f3b9cd",
    minimapMask: "#fff1f7dd",
  },
};

/** Cat-ear panel corner decoration size */
export const catEarSize = 8;

/** Shared panel header style */
export const panelHeader: React.CSSProperties = {
  color: colors.pink,
  fontWeight: 600,
  fontSize: 13,
  marginBottom: 8,
  display: "flex",
  alignItems: "center",
  gap: 6,
};

/** Shared flex column style for panels */
export const panelContainer: React.CSSProperties = {
  height: "100%",
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
};

/** Shared scrollable content area */
export const panelScroll: React.CSSProperties = {
  flex: 1,
  overflow: "auto",
  padding: 8,
};
