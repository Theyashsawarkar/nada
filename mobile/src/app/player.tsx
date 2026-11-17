import { LinearGradient } from "expo-linear-gradient";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, Share, View } from "react-native";
import { Text } from "../ui/text";
import Animated, { Easing, cancelAnimation, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Line } from "react-native-svg";
import { getDb, now } from "../core/store";
import { like } from "../core/taste";
import { download, downloadState, useDownloads } from "../player/downloads";
import { current, next, prev, seek, setRepeat, shuffleRest, toggle, usePlayer } from "../player/player";
import { Icon } from "../ui/icons";
import { Cover, Wave } from "../ui/parts";
import { artFor, c, clock, f } from "../ui/theme";

/** The ring around the record: bars from the song's id, lit as far as the song has played. */
function Ring({ id, progress, size }: { id: string; progress: number; size: number }) {
  const n = 90, cx = size / 2, r = size / 2 - 22;
  let seed = 0;
  for (const ch of id) seed = (seed * 31 + ch.charCodeAt(0)) % 997;
  return (
    <Svg width={size} height={size} style={{ position: "absolute" }}>
      {Array.from({ length: n }, (_, i) => {
        const a = (i / n) * Math.PI * 2 - Math.PI / 2;
        const h = 4 + Math.abs(Math.sin(i * 0.9 + seed) * 8) + Math.abs(Math.sin(i * 0.23 + seed) * 10);
        return <Line key={i} x1={cx + Math.cos(a) * r} y1={cx + Math.sin(a) * r} x2={cx + Math.cos(a) * (r + h)} y2={cx + Math.sin(a) * (r + h)}
          stroke={i / n < progress ? c.accent : "rgba(203,166,247,0.4)"} strokeWidth={2} strokeLinecap="round" />;
      })}
    </Svg>
  );
}

export default function Player() {
  const insets = useSafeAreaInsets();
  const p = usePlayer();
  useDownloads();
  const s = current();
  const spin = useSharedValue(0);
  const [liked, setLiked] = useState(false);
  useEffect(() => {
    if (s) setLiked(!!getDb().getFirstSync("SELECT 1 FROM liked WHERE song_id = ?", s.id));
  }, [s?.id]);
  useEffect(() => {
    if (p.playing) spin.value = withRepeat(withTiming(spin.value + 360, { duration: 24000, easing: Easing.linear }), -1, false);
    else cancelAnimation(spin);
  }, [p.playing]);
  const rot = useAnimatedStyle(() => ({ transform: [{ rotate: `${spin.value}deg` }] }));
  useEffect(() => {
    if (!s && router.canGoBack()) router.back();   // nothing playing
  }, [s]);
  if (!s) return <View style={{ flex: 1, backgroundColor: c.bg }} />;
  const prog = p.durationMs ? p.positionMs / p.durationMs : 0;
  const [a, b] = artFor(s.id);
  const dl = downloadState(s.id);
  const size = 290;

  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <LinearGradient colors={[a + "aa", c.bg, b + "55"]} locations={[0, 0.55, 1]} style={{ position: "absolute", inset: 0 }} />
      <View style={{ flex: 1, paddingTop: insets.top + 8, paddingHorizontal: 22, paddingBottom: insets.bottom + 16 }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <Pressable hitSlop={12} onPress={() => router.back()}><Icon name="chevron" size={24} /></Pressable>
          <View style={{ alignItems: "center" }}>
            <Text style={{ color: c.sub, fontFamily: f.medium, fontSize: 11, letterSpacing: 1.3 }}>PLAYING FROM</Text>
            <Text style={{ color: c.text, fontFamily: f.semibold, fontSize: 13 }}>{p.source || "Up next"}</Text>
          </View>
          <Pressable hitSlop={12} onPress={() => router.push("/queue")}><Icon name="queue" size={22} /></Pressable>
        </View>

        <View style={{ width: size, height: size, alignSelf: "center", marginTop: 26, alignItems: "center", justifyContent: "center" }}>
          <View style={{ position: "absolute", width: size, height: size, borderRadius: size / 2, borderWidth: 1, borderColor: "rgba(137,220,235,0.12)" }} />
          <Ring id={s.id} progress={prog} size={size} />
          <Animated.View style={[{ shadowColor: c.accent, shadowOpacity: 0.6, shadowRadius: 40, elevation: 20, borderRadius: 999 }, rot]}>
            <Cover song={s} size={size - 64} radius={(size - 64) / 2} />
            <View style={{ position: "absolute", left: (size - 64) / 2 - 16, top: (size - 64) / 2 - 16, width: 32, height: 32, borderRadius: 16,
              backgroundColor: c.bg, borderWidth: 6, borderColor: "rgba(255,255,255,0.12)" }} />
          </Animated.View>
        </View>

        <View style={{ flexDirection: "row", alignItems: "flex-end", marginTop: 30 }}>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text numberOfLines={2} style={{ color: c.text, fontFamily: f.displayBold, fontSize: 23 }}>{s.title}</Text>
            <Text numberOfLines={1} style={{ color: c.sub, fontFamily: f.body, fontSize: 14, marginTop: 2 }}>{s.artist_name}</Text>
          </View>
          <Pressable hitSlop={12} onPress={() => { like(getDb(), s.id, !liked, now()); setLiked(!liked); }}>
            <Icon name={liked ? "heart" : "heartOutline"} size={26} color={c.accent} />
          </Pressable>
        </View>

        <View style={{ marginTop: 16 }}>
          <View style={{ height: 38, flexDirection: "row" }}>
            <View style={{ flex: 1 }}>
              {/* the waveform is the seek bar: tap anywhere on it */}
              <Wave id={s.id} bars={54} progress={prog} onSeek={(x) => seek(x * (p.durationMs || s.duration_ms))} />
            </View>
          </View>
          <View style={{ flexDirection: "row", justifyContent: "space-between", marginTop: 4 }}>
            <Text style={{ color: c.muted, fontSize: 11.5, fontFamily: f.medium }}>{clock(p.positionMs)}</Text>
            <Text style={{ color: p.error ? c.red : c.muted, fontSize: 11.5, fontFamily: f.medium }}>
              {p.error ? "couldn't play" : p.buffering ? "loading…" : `−${clock((p.durationMs || s.duration_ms) - p.positionMs)}`}
            </Text>
          </View>
        </View>

        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 10, paddingHorizontal: 4 }}>
          <Pressable hitSlop={10} onPress={shuffleRest}><Icon name="shuffle" size={23} color={c.muted} /></Pressable>
          <Pressable hitSlop={10} onPress={() => void prev()}><Icon name="prev" size={26} /></Pressable>
          <Pressable onPress={toggle} style={{ width: 72, height: 72, borderRadius: 24, backgroundColor: c.accent, alignItems: "center", justifyContent: "center",
            shadowColor: c.accent, shadowOpacity: 0.5, shadowRadius: 20, elevation: 12 }}>
            <Icon name={p.playing ? "pause" : "play"} size={30} color={c.crust} />
          </Pressable>
          <Pressable hitSlop={10} onPress={() => void next()}><Icon name="next" size={26} /></Pressable>
          <Pressable hitSlop={10} onPress={() => setRepeat(!p.repeat)}><Icon name="repeat" size={23} color={p.repeat ? c.accent : c.muted} /></Pressable>
        </View>

        <View style={{ flex: 1 }} />
        <View style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 10, paddingHorizontal: 14, borderRadius: 20,
          backgroundColor: c.surface, borderWidth: 1, borderColor: c.line }}>
          <Dock icon="lyrics" label="Lyrics" color={c.accent} onPress={() => router.push("/lyrics")} />
          <Dock icon="queue" label="Up next" onPress={() => router.push("/queue")} />
          {dl === "done" ? <Dock icon="check" label="Offline" color={c.green} />
            : dl === "queued" || dl === "running" ? <Dock icon="down" label="Saving" color={c.yellow} />
            : <Dock icon="down" label="Download" onPress={() => download(s)} />}
          <Dock icon="share" label="Share" onPress={() => Share.share({ message: `${s.title} · ${s.artist_name}\nhttps://music.youtube.com/watch?v=${s.id}` })} />
        </View>
      </View>
    </View>
  );
}

function Dock({ icon, label, color = c.sub, onPress }: { icon: "lyrics" | "queue" | "check" | "down" | "share"; label: string; color?: string; onPress?: () => void }) {
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={{ alignItems: "center", gap: 3, minWidth: 56 }}>
      <Icon name={icon} size={19} color={color} />
      <Text style={{ color, fontFamily: f.body, fontSize: 10.5 }}>{label}</Text>
    </Pressable>
  );
}
