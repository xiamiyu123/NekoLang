/** Catppuccin Mocha — cat-themed NekoScope color palette */
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

/** Token-type → color mapping for TokenPanel */
export const tokenColors: Record<string, string> = {
  keyword: colors.mauve,
  identifier: colors.blue,
  literal: colors.green,
  operator: colors.peach,
  delimiter: colors.overlay0,
  program: colors.pink,
  type: colors.sky,
};

export function tokenColor(tokenType: string): string {
  const t = tokenType.toLowerCase();
  if (t === "int" || t === "float" || t === "string" || t === "bool") return colors.sky;
  if (t === "true" || t === "false") return colors.green;
  return tokenColors[t] ?? colors.overlay1;
}

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
