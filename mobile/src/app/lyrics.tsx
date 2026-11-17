import { LinearGradient } from "expo-linear-gradient";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, View } from "react-native";
import { Text } from "../ui/text";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { getDb, now } from "../core/store";
import { current, toggle, usePlayer } from "../player/player";
import { Icon } from "../ui/icons";
import { Cover, Wave } from "../ui/parts";
import { artFor, c, f } from "../ui/theme";
import { yt } from "../youtube";
import { Offline } from "../youtube/source";

type Got = { text: string | null; source: string; state: "loading" | "ok" | "none" | "offline" };

/** Lyrics are kept once fetched, so they show offline next time. */
async function lyricsFor(id: string): Promise<Got> {
  const db = getDb();
  const kept = db.getFirstSync<{ plain: string | null; source: string }>("SELECT plain, source FROM lyrics WHERE song_id = ?", id);
  if (kept) return { text: kept.plain, source: kept.source, state: kept.plain ? "ok" : "none" };
  try {
    const l = await yt.lyrics(id);
    db.runSync("INSERT OR REPLACE INTO lyrics(song_id, synced, plain, source, fetched_at) VALUES (?, ?, ?, ?, ?)",
      id, l?.synced ?? null, l?.plain ?? null, l?.source ?? "YouTube Music", now());
    return { text: l?.plain ?? null, source: l?.source ?? "", state: l?.plain ? "ok" : "none" };
  } catch (e) {
    // never remembered as "no lyrics": asked again next time
    return { text: null, source: "", state: e instanceof Offline ? "offline" : "none" };
  }
}

export default function Lyrics() {
  const insets = useSafeAreaInsets();
  const p = usePlayer();
  const s = current();
  const [got, setGot] = useState<Got>({ text: null, source: "", state: "loading" });
  useEffect(() => {
    if (!s) return;
    let live = true;
    setGot({ text: null, source: "", state: "loading" });
    lyricsFor(s.id).then((g) => live && setGot(g));
    return () => { live = false; };
  }, [s?.id]);
  if (!s) return <View style={{ flex: 1, backgroundColor: c.bg }} />;
  const [a, b] = artFor(s.id);
  const prog = p.durationMs ? p.positionMs / p.durationMs : 0;

  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <LinearGradient colors={[b + "99", c.bg, a + "77"]} style={{ position: "absolute", inset: 0 }} />
      <View style={{ paddingTop: insets.top + 8, paddingHorizontal: 22, flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Pressable hitSlop={12} onPress={() => router.back()}><Icon name="chevron" size={24} /></Pressable>
        <View style={{ alignItems: "center", flex: 1 }}>
          <Text style={{ color: c.sub, fontFamily: f.medium, fontSize: 11, letterSpacing: 1.3 }}>LYRICS</Text>
          <Text numberOfLines={1} style={{ color: c.text, fontFamily: f.semibold, fontSize: 13 }}>{s.title}</Text>
        </View>
        <View style={{ width: 24 }} />
      </View>
      <ScrollView contentContainerStyle={{ paddingHorizontal: 24, paddingTop: 28, paddingBottom: 140 }}>
        {got.state === "loading" ? <ActivityIndicator color={c.accent} style={{ marginTop: 40 }} />
          : got.state === "ok" ? (
            <>
              {got.text!.split("\n").map((line, i) => (
                <Text key={i} style={{ color: line.trim() ? c.text : "transparent", fontFamily: f.display, fontSize: 21, lineHeight: 30, opacity: 0.92 }}>
                  {line || " "}
                </Text>
              ))}
              <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 11.5, marginTop: 24 }}>Source: {got.source} · kept on the phone</Text>
            </>
          ) : (
            <Text style={{ color: c.sub, fontFamily: f.body, fontSize: 15, marginTop: 30, textAlign: "center" }}>
              {got.state === "offline" ? "No signal: lyrics show once you're online, and stay after that." : "No lyrics for this song."}
            </Text>
          )}
      </ScrollView>
      <View style={{ position: "absolute", left: 14, right: 14, bottom: insets.bottom + 16, height: 62, borderRadius: 22, flexDirection: "row",
        alignItems: "center", gap: 10, paddingLeft: 8, paddingRight: 12, backgroundColor: "rgba(18,16,28,0.85)", borderWidth: 1, borderColor: c.line2 }}>
        <Cover song={s} size={44} radius={12} />
        <View style={{ flex: 1 }}><Wave id={s.id} bars={34} progress={prog} height={22} /></View>
        <Pressable onPress={toggle} style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: c.accent, alignItems: "center", justifyContent: "center" }}>
          <Icon name={p.playing ? "pause" : "play"} size={18} color={c.crust} />
        </Pressable>
      </View>
    </View>
  );
}
