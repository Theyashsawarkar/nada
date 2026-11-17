/** nāda's colours: Catppuccin Mocha with pink as the accent, as on the desktop.
 *  Colour means something: pink is where you are and what's playing, green is
 *  on the phone, yellow is waiting or downloading, peach is why something is
 *  suggested, red is destructive, sky is online. */
export const c = {
  bg: "#07070d",
  bg2: "#0d0d17",
  surface: "rgba(255,255,255,0.055)",
  surface2: "rgba(255,255,255,0.09)",
  line: "rgba(255,255,255,0.10)",
  line2: "rgba(255,255,255,0.18)",
  text: "#ecebf7",
  sub: "#b4b2cc",
  muted: "#7c7a96",
  faint: "#4d4b63",
  accent: "#f5c2e7",
  mauve: "#cba6f7",
  sky: "#89dceb",
  blue: "#89b4fa",
  teal: "#94e2d5",
  green: "#a6e3a1",
  yellow: "#f9e2af",
  peach: "#fab387",
  red: "#f38ba8",
  crust: "#1e1e2e",
} as const;

export const f = {
  display: "SpaceGrotesk_600SemiBold",
  displayBold: "SpaceGrotesk_700Bold",
  body: "Inter_400Regular",
  medium: "Inter_500Medium",
  semibold: "Inter_600SemiBold",
  bold: "Inter_700Bold",
} as const;

/** Space to leave under a tab screen's content for the tab bar and mini player. */
export const BOTTOM = 170;

/** Every corner is rounded, everywhere. */
export const r = { sm: 10, md: 14, lg: 18, xl: 24, pill: 999 } as const;

/** Gradients for songs with no cover yet, picked by id so a song keeps its colour. */
const ART: [string, string][] = [
  ["#3b1d6e", "#ff5f8f"], ["#0e2a47", "#1f6fb2"], ["#f9e2af", "#cba6f7"], ["#1b1035", "#7a2d6b"],
  ["#0b1d2e", "#2c6c9c"], ["#14231f", "#89b4fa"], ["#f5c2e7", "#3d2a6b"], ["#2a0f1d", "#fab387"],
];
export function artFor(id: string): [string, string] {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return ART[h % ART.length]!;
}

export function clock(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
