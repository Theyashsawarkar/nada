// The soft glow behind every screen: two or three blurred colour pools, drawn
// as SVG radial gradients (no blur pass, so it costs nothing to draw).
import { StyleSheet, useWindowDimensions } from "react-native";
import Svg, { Defs, RadialGradient, Rect, Stop } from "react-native-svg";

export type Pool = { x: number; y: number; r: number; color: string; opacity?: number };

export const POOLS: Record<string, Pool[]> = {
  home: [
    { x: 0.15, y: 0.02, r: 0.75, color: "#b0447e", opacity: 0.55 },
    { x: 0.95, y: 0.12, r: 0.6, color: "#5b2a86", opacity: 0.5 },
    { x: 0.5, y: 0.95, r: 0.7, color: "#1c5f8a", opacity: 0.18 },
  ],
  search: [
    { x: 0.9, y: 0.0, r: 0.7, color: "#89dceb", opacity: 0.22 },
    { x: 0.05, y: 0.25, r: 0.6, color: "#cba6f7", opacity: 0.25 },
  ],
  library: [{ x: 0.85, y: 0.0, r: 0.65, color: "#a6e3a1", opacity: 0.18 }, { x: 0.1, y: 0.5, r: 0.6, color: "#cba6f7", opacity: 0.12 }],
  insights: [{ x: 0.1, y: 0.05, r: 0.7, color: "#cba6f7", opacity: 0.35 }, { x: 0.95, y: 0.4, r: 0.6, color: "#89dceb", opacity: 0.2 }],
};

export function Aurora({ pools }: { pools: Pool[] }) {
  const { width, height } = useWindowDimensions();
  return (
    <Svg width={width} height={height} style={StyleSheet.absoluteFill} pointerEvents="none">
      <Defs>
        {pools.map((p, i) => (
          <RadialGradient key={i} id={`g${i}`} cx={p.x * width} cy={p.y * height} r={p.r * width} gradientUnits="userSpaceOnUse">
            <Stop offset="0" stopColor={p.color} stopOpacity={p.opacity ?? 0.4} />
            <Stop offset="1" stopColor={p.color} stopOpacity={0} />
          </RadialGradient>
        ))}
      </Defs>
      {pools.map((_, i) => <Rect key={i} x={0} y={0} width={width} height={height} fill={`url(#g${i})`} />)}
    </Svg>
  );
}
