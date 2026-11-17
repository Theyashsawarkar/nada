// The icons from the design, as SVG. One component, picked by name.
import Svg, { Circle, G, Path, Rect } from "react-native-svg";

export type IconName =
  | "play" | "pause" | "next" | "prev" | "home" | "search" | "library" | "insights" | "heart" | "heartOutline"
  | "down" | "check" | "lyrics" | "queue" | "moon" | "share" | "chevron" | "more" | "spark" | "lock" | "shuffle"
  | "repeat" | "offline" | "clock" | "list" | "sliders" | "close" | "trash";

export function Icon({ name, size = 22, color = "#ecebf7", stroke = 1.8 }: { name: IconName; size?: number; color?: string; stroke?: number }) {
  const s = { fill: "none", stroke: color, strokeWidth: stroke, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const body = (() => {
    switch (name) {
      case "play": return <Path fill={color} d="M7 4.8v14.4c0 .8.9 1.3 1.6.9l11.3-7.2c.6-.4.6-1.4 0-1.8L8.6 3.9C7.9 3.5 7 4 7 4.8z" />;
      case "pause": return <G fill={color}><Rect x={6} y={4.5} width={4.2} height={15} rx={1.6} /><Rect x={13.8} y={4.5} width={4.2} height={15} rx={1.6} /></G>;
      case "next": return <G fill={color}><Path d="M5 6.2v11.6c0 .8.9 1.3 1.6.8l8.4-5.8c.6-.4.6-1.3 0-1.7L6.6 5.4C5.9 4.9 5 5.4 5 6.2z" /><Rect x={16.5} y={5} width={2.6} height={14} rx={1.3} /></G>;
      case "prev": return <G fill={color} transform="translate(24 0) scale(-1 1)"><Path d="M5 6.2v11.6c0 .8.9 1.3 1.6.8l8.4-5.8c.6-.4.6-1.3 0-1.7L6.6 5.4C5.9 4.9 5 5.4 5 6.2z" /><Rect x={16.5} y={5} width={2.6} height={14} rx={1.3} /></G>;
      case "home": return <Path {...s} d="M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5h-3.5v-6h-6v6H5.5A1.5 1.5 0 0 1 4 19z" />;
      case "search": return <G {...s} strokeWidth={1.9}><Circle cx={11} cy={11} r={6.5} /><Path d="m20 20-4.2-4.2" /></G>;
      case "library": return <G {...s}><Path d="M5 4.5v15M9.5 4.5v15" /><Rect x={13} y={4.5} width={6} height={15} rx={2} transform="rotate(-12 16 12)" /></G>;
      case "insights": return <G {...s}><Path d="M4 19.5h16" /><Path d="M7 16v-5M12 16V6M17 16v-8" /></G>;
      case "heart": return <Path fill={color} d="M12 20.3s-7.8-4.6-7.8-10.4A4.4 4.4 0 0 1 12 7.3a4.4 4.4 0 0 1 7.8 2.6c0 5.8-7.8 10.4-7.8 10.4z" />;
      case "heartOutline": return <Path {...s} d="M12 20.3s-7.8-4.6-7.8-10.4A4.4 4.4 0 0 1 12 7.3a4.4 4.4 0 0 1 7.8 2.6c0 5.8-7.8 10.4-7.8 10.4z" />;
      case "down": return <G {...s} strokeWidth={1.9}><Path d="M12 4v11M7.5 10.5 12 15l4.5-4.5" /><Path d="M5 19.5h14" /></G>;
      case "check": return <G {...s} strokeWidth={2}><Circle cx={12} cy={12} r={8.5} /><Path d="m8.3 12.2 2.5 2.5 4.9-5" /></G>;
      case "lyrics": return <G {...s}><Path d="M4 6.5h16M4 11.5h11M4 16.5h7" /><Circle cx={17.5} cy={17} r={2.5} /><Path d="M20 17V9.5" /></G>;
      case "queue": return <G {...s}><Path d="M4 6.5h12M4 11.5h12M4 16.5h7" /><Path d="M15 15v4.5l4-2.25z" fill={color} /></G>;
      case "moon": return <Path {...s} d="M19.5 14.5A7.5 7.5 0 0 1 9.5 4.5a7.5 7.5 0 1 0 10 10z" />;
      case "share": return <G {...s}><Path d="M12 4v11M8 8l4-4 4 4" /><Path d="M6 12v6.5A1.5 1.5 0 0 0 7.5 20h9a1.5 1.5 0 0 0 1.5-1.5V12" /></G>;
      case "chevron": return <Path {...s} strokeWidth={2} d="m6.5 9.5 5.5 5.5 5.5-5.5" />;
      case "more": return <G fill={color}><Circle cx={5.5} cy={12} r={1.7} /><Circle cx={12} cy={12} r={1.7} /><Circle cx={18.5} cy={12} r={1.7} /></G>;
      case "spark": return <Path fill={color} d="M12 2.5l1.9 5.6 5.6 1.9-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9z" />;
      case "lock": return <G {...s} strokeWidth={1.9}><Rect x={5} y={10.5} width={14} height={10} rx={3} /><Path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" /></G>;
      case "shuffle": return <G {...s}><Path d="M4 7h3.5c2.5 0 3.5 1.5 5 5s2.5 5 5 5H20M4 17h3.5c1.4 0 2.3-.5 3-1.4M14.5 8.4c.7-.9 1.6-1.4 3-1.4H20" /><Path d="m17.5 4.5 2.5 2.5-2.5 2.5M17.5 14.5l2.5 2.5-2.5 2.5" /></G>;
      case "repeat": return <G {...s}><Path d="M5 11V9.5A2.5 2.5 0 0 1 7.5 7H19M16.5 4.5 19 7l-2.5 2.5M19 13v1.5a2.5 2.5 0 0 1-2.5 2.5H5M7.5 19.5 5 17l2.5-2.5" /></G>;
      case "offline": return <G {...s}><Path d="M7 18.5h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.2 9.6 4.5 4.5 0 0 0 7 18.5z" /><Path d="m9.5 13.7 1.8 1.8 3.4-3.4" /></G>;
      case "clock": return <G {...s}><Circle cx={12} cy={12} r={8.5} /><Path d="M12 7.5V12l3 2" /></G>;
      case "list": return <G {...s}><Rect x={4} y={4} width={16} height={16} rx={4} /><Path d="M8 9.5h8M8 14.5h5" /></G>;
      case "sliders": return <G {...s}><Path d="M5 5v14M12 5v14M19 5v14" /><Circle cx={5} cy={14} r={2} fill="#08080f" /><Circle cx={12} cy={9} r={2} fill="#08080f" /><Circle cx={19} cy={15.5} r={2} fill="#08080f" /></G>;
      case "close": return <Path {...s} strokeWidth={2} d="M6.5 6.5l11 11M17.5 6.5l-11 11" />;
      case "trash": return <G {...s}><Path d="M5 7h14M10 7V5h4v2M7 7l1 12.5h8L17 7" /></G>;
    }
  })();
  return <Svg width={size} height={size} viewBox="0 0 24 24">{body}</Svg>;
}
