// The building blocks every screen shares.
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useState, type ReactNode } from "react";
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { Text } from "./text";
import type { Song } from "../core/db";
import { downloadState, useDownloads } from "../player/downloads";
import { current, usePlayer } from "../player/player";
import { Icon } from "./icons";
import { artFor, c, clock, f, r } from "./theme";

/** A song's cover, or its own gradient until there is one. */
export function Cover({ song, size, radius = r.md, style }: { song: Pick<Song, "id" | "cover_url">; size: number; radius?: number; style?: StyleProp<ViewStyle> }) {
  const [a, b] = artFor(song.id);
  return (
    <View style={[{ width: size, height: size, borderRadius: radius, overflow: "hidden" }, style]}>
      <LinearGradient colors={[a, b]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={StyleSheet.absoluteFill} />
      {song.cover_url ? <Image source={song.cover_url} style={StyleSheet.absoluteFill} contentFit="cover" transition={200} /> : null}
    </View>
  );
}

export function Tag({ children, color }: { children: ReactNode; color: string }) {
  return (
    <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: color + "22" }}>
      <Text style={{ color, fontFamily: f.semibold, fontSize: 10.5, letterSpacing: 0.6, textTransform: "uppercase" }}>{children}</Text>
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[{ backgroundColor: c.surface, borderColor: c.line, borderWidth: 1, borderRadius: r.lg }, style]}>{children}</View>;
}

export function Title({ children, small }: { children: ReactNode; small?: string }) {
  return (
    <Text style={s.title}>
      {children}
      {small ? <Text style={s.titleSmall}>{"  " + small}</Text> : null}
    </Text>
  );
}

/** A song in a list: cover, title (pink, with equaliser bars, while it plays),
 *  artists, then its length or its state, and a ⋯ menu. */
export function SongRow({ song, onPress, onLong, onMore, right, sub, index }: {
  song: Song; onPress: () => void; onLong?: () => void; onMore?: () => void; right?: ReactNode; sub?: string; index?: number;
}) {
  const p = usePlayer();
  useDownloads();
  const playing = current()?.id === song.id;
  const dl = downloadState(song.id);
  const state = dl === "done" ? <Icon name="check" size={17} color={c.green} />
    : dl === "queued" || dl === "running" ? <Tag color={c.yellow}>{dl === "running" ? "saving" : "next"}</Tag>
    : song.duration_ms ? <Text style={s.rowTime}>{clock(song.duration_ms)}</Text> : null;
  return (
    <Pressable onPress={onPress} onLongPress={onLong ?? onMore} style={({ pressed }) => [s.row, pressed && { opacity: 0.55 }]}>
      {index !== undefined ? <Text style={s.rowIndex}>{index}</Text> : null}
      <View>
        <Cover song={song} size={50} radius={12} />
        {playing ? (
          <View style={s.rowPlaying}><Bars on={p.playing} /></View>
        ) : null}
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text numberOfLines={1} style={[s.rowTitle, playing && { color: c.accent }]}>{song.title}</Text>
        <Text numberOfLines={1} style={s.rowSub}>{sub ?? song.artist_name}</Text>
      </View>
      {right ?? state}
      {onMore ? (
        <Pressable hitSlop={12} onPress={onMore} style={{ paddingLeft: 4 }}><Icon name="more" size={20} color={c.muted} /></Pressable>
      ) : null}
    </Pressable>
  );
}

/** Three little bars for "this one is playing" (still when paused). */
export function Bars({ on, color = c.accent }: { on: boolean; color?: string }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 2, height: 14 }}>
      {[0.55, 1, 0.75].map((h, i) => (
        <View key={i} style={{ width: 3, borderRadius: 2, height: `${(on ? h : 0.35) * 100}%`, backgroundColor: color }} />
      ))}
    </View>
  );
}

/** The song's "waveform": bars made from its id (no audio analysis), lit up to `progress`. */
export function Wave({ id, bars = 48, progress, height = 38, onSeek }: { id: string; bars?: number; progress: number; height?: number; onSeek?: (p: number) => void }) {
  let seed = 0;
  for (const ch of id) seed = (seed * 33 + ch.charCodeAt(0)) % 9973;
  const hs = Array.from({ length: bars }, (_, i) => {
    const v = 20 + Math.abs(Math.sin(i * 0.55 + seed) * 55) + Math.abs(Math.sin(i * 1.7 + seed * 2) * 25);
    return Math.min(100, v);
  });
  const [w, setW] = useState(1);
  return (
    <Pressable
      disabled={!onSeek}
      onPress={(e) => onSeek?.(Math.max(0, Math.min(1, e.nativeEvent.locationX / w)))}
      onLayout={(e) => setW(Math.max(1, e.nativeEvent.layout.width))}
      style={{ flexDirection: "row", alignItems: "center", gap: 2, height }}>
      {hs.map((h, i) => (
        <View key={i} style={{ flex: 1, height: `${h}%`, borderRadius: 3, backgroundColor: i / bars < progress ? c.accent : "rgba(255,255,255,0.18)" }} />
      ))}
    </Pressable>
  );
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <View style={{ alignItems: "center", paddingVertical: 48, paddingHorizontal: 24, gap: 8 }}>
      <Text style={{ color: c.text, fontFamily: f.display, fontSize: 19, textAlign: "center" }}>{title}</Text>
      <Text style={{ color: c.sub, fontFamily: f.body, fontSize: 14, textAlign: "center", lineHeight: 21 }}>{body}</Text>
    </View>
  );
}

export const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: c.bg },
  title: { color: c.text, fontFamily: f.display, fontSize: 17, marginTop: 22, marginBottom: 10 },
  titleSmall: { color: c.muted, fontFamily: f.medium, fontSize: 12 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 7 },
  rowTitle: { color: c.text, fontFamily: f.semibold, fontSize: 14.5 },
  rowSub: { color: c.muted, fontFamily: f.body, fontSize: 12.5, marginTop: 2 },
  rowTime: { color: c.muted, fontFamily: f.medium, fontSize: 12, fontVariant: ["tabular-nums"] },
  rowIndex: { color: c.faint, fontFamily: f.semibold, fontSize: 13, width: 18, textAlign: "center" },
  rowPlaying: { position: "absolute", inset: 0, borderRadius: 12, backgroundColor: "rgba(7,7,13,0.55)", alignItems: "center", justifyContent: "center" },
  h1: { color: c.text, fontFamily: f.display, fontSize: 26 },
});
