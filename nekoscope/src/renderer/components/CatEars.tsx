import { colors } from "../styles/theme";

/** SVG cat ears for decorating panel tops */
export function CatEars({ width = 28, height = 14 }: { width?: number; height?: number }) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 28 14"
      style={{ display: "block", flexShrink: 0 }}
    >
      <polygon points="2,14 10,2 18,14" fill={colors.mantle} />
      <polygon points="10,14 18,2 26,14" fill={colors.mantle} />
      <polygon points="3,14 10,4 17,14" fill={colors.surface0} />
      <polygon points="11,14 18,4 25,14" fill={colors.surface0} />
      {/* inner ear pink */}
      <polygon points="6,14 10,7 14,14" fill={colors.pink} opacity={0.6} />
      <polygon points="14,14 18,7 22,14" fill={colors.pink} opacity={0.6} />
    </svg>
  );
}

/** Small paw print indicator */
export function CatPaw({ size = 10 }: { size?: number }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: size,
        height: size,
        borderRadius: "50% 50% 0 50%",
        background: colors.pink,
        opacity: 0.7,
      }}
    />
  );
}
