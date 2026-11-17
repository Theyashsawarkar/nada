import { LinearGradient } from "expo-linear-gradient";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { Song } from "../../core/db";
import { buildHome, partOfDay, type Section } from "../../core/feed";
import { getDb, now } from "../../core/store";
import { current, playSongs, usePlayer } from "../../player/player";
import { Aurora, POOLS } from "../../ui/aurora";
import { Icon } from "../../ui/icons";
import { MOODS } from "../../ui/moods";
import { Bars, Cover, s } from "../../ui/parts";
import { Text } from "../../ui/text";
import { BOTTOM, c, f } from "../../ui/theme";

function greeting(t: number): string {
  const h = new Date(t * 1000).getHours();
  return h < 5 ? "Still up?" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

/** Six songs to tap straight into: what you play most and lately, else what you looked at last. */
function quickPicks(): Song[] {
  const db = getDb();
  const picks = db.getAllSync<Song>(
    `SELECT s.* FROM song s LEFT JOIN taste_song t ON t.song_id = s.id
     WHERE s.id IN (SELECT song_id FROM play UNION SELECT song_id FROM liked UNION SELECT song_id FROM download WHERE state = 'done')
       AND s.id NOT IN (SELECT id FROM hidden WHERE kind = 'song')
     ORDER BY coalesce(t.score, 0) DESC, t.last_played DESC LIMIT 6`);
  if (picks.length >= 4) return picks;
  const seen = db.getAllSync<Song>(
    `SELECT s.* FROM search q JOIN song s ON s.id = q.picked_song_id GROUP BY s.id ORDER BY max(q.at) DESC LIMIT 6`);
  const ids = new Set(picks.map((x) => x.id));
  return [...picks, ...seen.filter((x) => !ids.has(x.id))].slice(0, 6);
}

function MixCard({ sec }: { sec: Section }) {
  const covers = sec.songs.slice(0, 3);
  const [loved, fresh] = (sec.why.split(" · ")[1] ?? "").split(", ");
  return (
    <Pressable onPress={() => playSongs(sec.songs, 0, sec.title)} style={({ pressed }) => [{ marginTop: 18 }, pressed && { transform: [{ scale: 0.985 }] }]}>
      <LinearGradient colors={["#5b2a86", "#b0447e", "#f08a7e"]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
        style={{ height: 196, borderRadius: 28, padding: 18, overflow: "hidden" }}>
        <View style={{ position: "absolute", right: -40, top: -50, width: 210, height: 210, borderRadius: 105, borderWidth: 1, borderColor: "rgba(255,255,255,0.22)" }} />
        <View style={{ position: "absolute", right: 10, top: -20, width: 150, height: 150, borderRadius: 75, borderWidth: 1, borderStyle: "dashed", borderColor: "rgba(255,255,255,0.25)" }} />
        {/* the mix's own covers, fanned */}
        <View style={{ position: "absolute", right: 22, top: 26, width: 120, height: 110 }}>
          {covers.map((song, i) => (
            <View key={song.id} style={{ position: "absolute", right: i * 26, top: i * 8, transform: [{ rotate: `${(i - 1) * 7}deg` }],
              shadowColor: "#000", shadowOpacity: 0.4, shadowRadius: 12, elevation: 8 - i, zIndex: 3 - i }}>
              <Cover song={song} size={78} radius={16} />
            </View>
          ))}
        </View>
        <View style={{ flex: 1, justifyContent: "flex-end" }}>
          <Text style={{ color: "#fff", opacity: 0.85, fontFamily: f.semibold, fontSize: 10.5, letterSpacing: 1.6 }}>FOR YOU · MADE JUST NOW</Text>
          <Text style={{ color: "#fff", fontFamily: f.displayBold, fontSize: 26, marginTop: 4 }}>{sec.title}</Text>
          <Text style={{ color: "#fff", opacity: 0.85, fontFamily: f.body, fontSize: 12.5, marginTop: 2 }}>
            {sec.songs.length} songs{loved ? ` · ${loved}` : ""}{fresh ? ` · ${fresh}` : ""}
          </Text>
        </View>
        <View style={{ position: "absolute", right: 18, bottom: 18, width: 52, height: 52, borderRadius: 26, backgroundColor: "#fff",
          alignItems: "center", justifyContent: "center", shadowColor: "#000", shadowOpacity: 0.35, shadowRadius: 14, elevation: 10 }}>
          <Icon name="play" size={24} color={c.crust} />
        </View>
      </LinearGradient>
    </Pressable>
  );
}

function QuickPicks({ songs }: { songs: Song[] }) {
  const p = usePlayer();
  const now_ = current();
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", rowGap: 8, marginTop: 18 }}>
      {songs.map((song, i) => {
        const on = now_?.id === song.id;
        return (
          <Pressable key={song.id} onPress={() => playSongs(songs, i, "Quick picks")}
            style={({ pressed }) => [st.pick, on && { borderColor: "rgba(245,194,231,0.45)", backgroundColor: "rgba(245,194,231,0.10)" }, pressed && { opacity: 0.6 }]}>
            <Cover song={song} size={50} radius={0} />
            <Text numberOfLines={2} style={{ flex: 1, color: on ? c.accent : c.text, fontFamily: f.semibold, fontSize: 12.5, lineHeight: 16 }}>{song.title}</Text>
            {on ? <View style={{ paddingRight: 10 }}><Bars on={p.playing} /></View> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

function Row({ sec }: { sec: Section }) {
  return (
    <View>
      <View style={{ flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", marginTop: 26 }}>
        <Text style={{ color: c.text, fontFamily: f.display, fontSize: 19 }}>{sec.title}</Text>
        <Pressable hitSlop={10} onPress={() => playSongs(sec.songs, 0, sec.title)}>
          <Text style={{ color: c.accent, fontFamily: f.semibold, fontSize: 12.5 }}>Play all</Text>
        </Pressable>
      </View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 3, marginBottom: 12 }}>
        <Icon name="spark" size={12} color={c.peach} />
        <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 12 }}>{sec.why}</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 14, paddingRight: 18 }} style={{ marginRight: -18 }}>
        {sec.songs.map((song, i) => (
          <Pressable key={song.id} onPress={() => playSongs(sec.songs, i, sec.title)} style={({ pressed }) => [{ width: 136 }, pressed && { opacity: 0.7 }]}>
            <Cover song={song} size={136} radius={20} />
            <Text numberOfLines={1} style={{ color: c.text, fontFamily: f.semibold, fontSize: 13, marginTop: 8 }}>{song.title}</Text>
            <Text numberOfLines={1} style={{ color: c.muted, fontFamily: f.body, fontSize: 12, marginTop: 1 }}>{song.artist_name}</Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

function Moods({ title }: { title: string }) {
  return (
    <>
      <Text style={{ color: c.text, fontFamily: f.display, fontSize: 19, marginTop: 28, marginBottom: 12 }}>{title}</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
        {MOODS.map((m) => (
          <Pressable key={m.name} onPress={() => router.push({ pathname: "/search", params: { q: m.query } })}
            style={({ pressed }) => [{ width: "48%", flexGrow: 1 }, pressed && { opacity: 0.75 }]}>
            <LinearGradient colors={m.colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={{ height: 64, borderRadius: 18, padding: 14, justifyContent: "flex-end", overflow: "hidden" }}>
              <View style={{ position: "absolute", right: -14, top: -14, width: 56, height: 56, borderRadius: 28, backgroundColor: "rgba(255,255,255,0.18)" }} />
              <Text style={{ color: "#fff", fontFamily: f.semibold, fontSize: 14 }}>{m.name}</Text>
            </LinearGradient>
          </Pressable>
        ))}
      </View>
    </>
  );
}

export default function Home() {
  const insets = useSafeAreaInsets();
  const [sections, setSections] = useState<Section[]>([]);
  const [picks, setPicks] = useState<Song[]>([]);
  const p = usePlayer();
  useFocusEffect(useCallback(() => {
    setSections(buildHome(getDb(), now()));
    setPicks(quickPicks());
  }, [p.index]));
  const t = now();
  const mix = sections.find((x) => x.id === "for-you");
  const rest = sections.filter((x) => x.id !== "for-you");
  const day = new Date(t * 1000).toLocaleDateString("en", { weekday: "long" });
  const fresh = !mix && !picks.length && !rest.length;

  return (
    <View style={s.screen}>
      <Aurora pools={POOLS.home!} />
      <ScrollView contentContainerStyle={{ paddingTop: insets.top + 14, paddingHorizontal: 18, paddingBottom: BOTTOM }} showsVerticalScrollIndicator={false}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <View style={{ flex: 1 }}>
            <Text style={{ color: c.sub, fontFamily: f.medium, fontSize: 12.5, letterSpacing: 0.4 }}>{day} {partOfDay(t).name}</Text>
            <Text style={{ color: c.text, fontFamily: f.displayBold, fontSize: 28, marginTop: 2 }}>{greeting(t)}</Text>
          </View>
          <Pressable onPress={() => router.push("/search")} style={st.round}>
            <Icon name="search" size={19} color={c.accent} />
          </Pressable>
        </View>

        {fresh ? (
          <Pressable onPress={() => router.push("/search")} style={{ marginTop: 20 }}>
            <LinearGradient colors={["#3d2a6b", "#b0447e"]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={{ borderRadius: 28, padding: 22, overflow: "hidden" }}>
              <View style={{ position: "absolute", right: -40, top: -40, width: 180, height: 180, borderRadius: 90, borderWidth: 1, borderColor: "rgba(255,255,255,0.2)" }} />
              <Text style={{ color: "#fff", fontFamily: f.displayBold, fontSize: 24 }}>Start your sound</Text>
              <Text style={{ color: "#fff", opacity: 0.85, fontFamily: f.body, fontSize: 13.5, lineHeight: 20, marginTop: 6, maxWidth: 260 }}>
                Play a song you love. nāda learns from what you finish, replay and skip, and makes Home from that, on this phone.
              </Text>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 10, marginTop: 18, height: 46, borderRadius: 16, paddingHorizontal: 14, backgroundColor: "rgba(255,255,255,0.16)" }}>
                <Icon name="search" size={17} color="#fff" />
                <Text style={{ color: "#fff", opacity: 0.85, fontFamily: f.body, fontSize: 14 }}>Search songs, artists…</Text>
              </View>
            </LinearGradient>
          </Pressable>
        ) : null}

        {mix ? <MixCard sec={mix} /> : null}
        {picks.length >= 2 ? <QuickPicks songs={picks.slice(0, picks.length - (picks.length % 2))} /> : null}
        {rest.map((sec) => <Row key={sec.id} sec={sec} />)}
        <Moods title={fresh ? "Start somewhere" : "In the mood for"} />
      </ScrollView>
    </View>
  );
}

const st = StyleSheet.create({
  round: { width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,255,255,0.08)",
    borderWidth: 1, borderColor: c.line },
  pick: { width: "48.5%", height: 50, flexDirection: "row", alignItems: "center", gap: 10, borderRadius: 12, overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.07)", borderWidth: 1, borderColor: c.line },
});
