import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Keyboard, Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { saveSong, searchLocal, type Song } from "../../core/db";
import { getDb, now } from "../../core/store";
import { current, playNext, playSongs, usePlayer } from "../../player/player";
import { Aurora, POOLS } from "../../ui/aurora";
import { Icon } from "../../ui/icons";
import { songMenu } from "../../ui/menu";
import { MOODS } from "../../ui/moods";
import { Bars, Cover, SongRow, s } from "../../ui/parts";
import { Text } from "../../ui/text";
import { BOTTOM, c, clock, f } from "../../ui/theme";
import { yt } from "../../youtube";
import { Offline } from "../../youtube/source";

function Label({ children, right }: { children: string; right?: ReactNode }) {
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 24, marginBottom: 10 }}>
      <Text style={{ color: c.muted, fontFamily: f.semibold, fontSize: 11, letterSpacing: 1.4 }}>{children}</Text>
      {right}
    </View>
  );
}

/** Grey shapes where results will be, while YouTube Music answers. */
function Skeleton() {
  return (
    <View style={{ gap: 14, marginTop: 4 }}>
      <View style={{ height: 116, borderRadius: 24, backgroundColor: "rgba(255,255,255,0.05)" }} />
      {[0, 1, 2, 3].map((i) => (
        <View key={i} style={{ flexDirection: "row", gap: 12, alignItems: "center", opacity: 1 - i * 0.2 }}>
          <View style={{ width: 50, height: 50, borderRadius: 12, backgroundColor: "rgba(255,255,255,0.06)" }} />
          <View style={{ flex: 1, gap: 7 }}>
            <View style={{ height: 12, width: "70%", borderRadius: 6, backgroundColor: "rgba(255,255,255,0.07)" }} />
            <View style={{ height: 10, width: "45%", borderRadius: 5, backgroundColor: "rgba(255,255,255,0.05)" }} />
          </View>
        </View>
      ))}
    </View>
  );
}

function TopResult({ song, onPlay }: { song: Song; onPlay: () => void }) {
  const p = usePlayer();
  const on = current()?.id === song.id;
  return (
    <Pressable onPress={onPlay} onLongPress={() => songMenu(song)} style={({ pressed }) => [pressed && { opacity: 0.8 }]}>
      <LinearGradient colors={["rgba(245,194,231,0.16)", "rgba(203,166,247,0.05)"]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
        style={{ flexDirection: "row", gap: 14, padding: 14, borderRadius: 24, borderWidth: 1, borderColor: "rgba(245,194,231,0.28)" }}>
        <Cover song={song} size={88} radius={18} />
        <View style={{ flex: 1, minWidth: 0, justifyContent: "space-between" }}>
          <View>
            <Text numberOfLines={2} style={{ color: on ? c.accent : c.text, fontFamily: f.displayBold, fontSize: 18, lineHeight: 22 }}>{song.title}</Text>
            <Text numberOfLines={1} style={{ color: c.sub, fontFamily: f.body, fontSize: 13, marginTop: 3 }}>{song.artist_name}</Text>
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Pressable onPress={onPlay} style={st.playPill}>
              {on && p.playing ? <Bars on color={c.crust} /> : <Icon name="play" size={14} color={c.crust} />}
              <Text style={{ color: c.crust, fontFamily: f.semibold, fontSize: 13 }}>{on ? "Playing" : "Play"}</Text>
            </Pressable>
            <Pressable onPress={() => playNext(song)} style={st.ghostPill}>
              <Text style={{ color: c.text, fontFamily: f.medium, fontSize: 13 }}>Play next</Text>
            </Pressable>
            {song.duration_ms ? <Text style={{ color: c.muted, fontFamily: f.medium, fontSize: 12, marginLeft: "auto" }}>{clock(song.duration_ms)}</Text> : null}
          </View>
        </View>
      </LinearGradient>
    </Pressable>
  );
}

export default function Search() {
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ q?: string }>();
  const [q, setQ] = useState("");
  const [focused, setFocused] = useState(false);
  const [local, setLocal] = useState<Song[]>([]);
  const [online, setOnline] = useState<Song[]>([]);
  const [suggest, setSuggest] = useState<string[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "done" | "offline" | "error">("idle");
  const [recent, setRecent] = useState<string[]>([]);
  const ask = useRef(0);
  const searched = useRef("");

  const loadRecent = () =>
    setRecent(getDb().getAllSync<{ q: string }>("SELECT q FROM search GROUP BY lower(q) ORDER BY max(at) DESC LIMIT 8").map((r) => r.q));
  useEffect(loadRecent, []);
  useEffect(() => {
    if (params.q) void run(params.q);   // a mood from Home
  }, [params.q]);

  // the phone answers at once, as you type; YouTube Music suggests
  useEffect(() => {
    setLocal(q.trim() ? searchLocal(getDb(), q, 4) : []);
    if (q.trim() === searched.current) return;
    if (!q.trim()) { setOnline([]); setSuggest([]); setState("idle"); return; }
    const id = ++ask.current;
    const t = setTimeout(() => {
      yt.suggest(q).then((x) => id === ask.current && setSuggest(x.slice(0, 5))).catch(() => {});
    }, 160);
    return () => clearTimeout(t);
  }, [q]);

  async function run(query: string) {
    const text = query.trim();
    if (!text) return;
    Keyboard.dismiss();
    searched.current = text;
    setQ(text);
    setSuggest([]);
    const id = ++ask.current;
    setState("loading");
    getDb().runSync("INSERT INTO search(q, at) VALUES (?, ?)", text, now());
    loadRecent();
    try {
      const r = await yt.search(text);
      if (id !== ask.current) return;
      const t = now();
      r.songs.forEach((x) => saveSong(getDb(), x, t));
      setOnline(r.songs);
      setState("done");
    } catch (e) {
      if (id === ask.current) setState(e instanceof Offline ? "offline" : "error");
    }
  }

  function play(list: Song[], i: number) {
    const song = list[i]!;
    getDb().runSync("UPDATE search SET picked_song_id = ? WHERE id = (SELECT max(id) FROM search)", song.id);
    playSongs([song], 0, "Search");   // what follows comes from autoplay, like YouTube Music
  }

  const showSuggest = focused && suggest.length > 0 && q.trim() !== searched.current;
  const top = online[0];

  return (
    <View style={s.screen}>
      <Aurora pools={POOLS.search!} />
      <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingTop: insets.top + 14, paddingHorizontal: 18, paddingBottom: BOTTOM }}>
        <Text style={{ color: c.text, fontFamily: f.displayBold, fontSize: 28 }}>Search</Text>

        <View style={[st.field, focused && st.fieldOn]}>
          <Icon name="search" size={19} color={focused ? c.accent : c.sub} />
          <TextInput value={q} onChangeText={setQ} onSubmitEditing={() => run(q)} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
            placeholder="Songs, artists, a line you remember" placeholderTextColor={c.muted} returnKeyType="search" autoCorrect={false}
            maxFontSizeMultiplier={1.15} style={{ flex: 1, color: c.text, fontFamily: f.medium, fontSize: 15.5, paddingVertical: 0 }} selectionColor={c.accent} />
          {q ? (
            <Pressable hitSlop={12} onPress={() => { setQ(""); searched.current = ""; }} style={st.clear}>
              <Icon name="close" size={13} color={c.text} stroke={2.4} />
            </Pressable>
          ) : null}
        </View>

        {showSuggest ? (
          <View style={st.suggest}>
            {suggest.map((x, i) => (
              <Pressable key={x} onPress={() => run(x)} style={({ pressed }) => [st.suggestRow, i > 0 && st.suggestLine, pressed && { backgroundColor: c.surface2 }]}>
                <Icon name="search" size={15} color={c.muted} />
                <Text numberOfLines={1} style={{ flex: 1, color: c.text, fontFamily: f.body, fontSize: 14.5 }}>{x}</Text>
              </Pressable>
            ))}
          </View>
        ) : null}

        {/* while typing, your own songs answer first */}
        {state !== "done" ? (local.length && q.trim() ? (
          <>
            <Label>FROM YOUR MUSIC</Label>
            {local.map((song, i) => <SongRow key={song.id} song={song} onPress={() => play(local, i)} onMore={() => songMenu(song)} />)}
          </>
        ) : null) : null}

        {state === "loading" ? (<><Label>YOUTUBE MUSIC</Label><Skeleton /></>) : null}
        {state === "offline" ? (
          <View style={st.note}>
            <Icon name="offline" size={20} color={c.yellow} />
            <Text style={{ flex: 1, color: c.sub, fontFamily: f.body, fontSize: 13.5 }}>No signal. What's on your phone is above; YouTube Music answers once you're back online.</Text>
          </View>
        ) : null}
        {state === "error" ? (
          <Pressable onPress={() => run(q)} style={st.note}>
            <Icon name="repeat" size={20} color={c.red} />
            <Text style={{ flex: 1, color: c.sub, fontFamily: f.body, fontSize: 13.5 }}>YouTube Music didn't answer. Tap to try again.</Text>
          </Pressable>
        ) : null}

        {state === "done" && top ? (
          <>
            <Label>TOP RESULT</Label>
            <TopResult song={top} onPlay={() => play(online, 0)} />
            {/* then below the top result, so it stays where your eye lands */}
            {local.length && q.trim() ? (
          <>
            <Label>FROM YOUR MUSIC</Label>
            {local.map((song, i) => <SongRow key={song.id} song={song} onPress={() => play(local, i)} onMore={() => songMenu(song)} />)}
          </>
        ) : null}
            <Label right={<Text style={{ color: c.muted, fontFamily: f.body, fontSize: 12 }}>{online.length - 1} more</Text>}>SONGS</Label>
            {online.slice(1).map((song, i) => (
              <SongRow key={song.id} song={song} onPress={() => play(online, i + 1)} onMore={() => songMenu(song)} />
            ))}
          </>
        ) : null}
        {state === "done" && !top ? (
          <View style={st.note}><Text style={{ color: c.sub, fontFamily: f.body, fontSize: 13.5 }}>Nothing found for "{q}". Try fewer words, or the artist's name.</Text></View>
        ) : null}

        {!q.trim() ? (
          <>
            {recent.length ? (
              <>
                <Label right={
                  <Pressable hitSlop={10} onPress={() => { getDb().runSync("DELETE FROM search"); loadRecent(); }}>
                    <Text style={{ color: c.muted, fontFamily: f.medium, fontSize: 12 }}>Clear</Text>
                  </Pressable>}>RECENT</Label>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                  {recent.map((x) => (
                    <Pressable key={x} onPress={() => run(x)} style={({ pressed }) => [st.chip, pressed && { backgroundColor: c.surface2 }]}>
                      <Icon name="clock" size={13} color={c.muted} />
                      <Text style={{ color: c.sub, fontFamily: f.body, fontSize: 13 }}>{x}</Text>
                    </Pressable>
                  ))}
                </View>
              </>
            ) : null}
            <Label>BROWSE</Label>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
              {MOODS.map((m) => (
                <Pressable key={m.name} onPress={() => run(m.query)} style={({ pressed }) => [{ width: "48%", flexGrow: 1 }, pressed && { opacity: 0.75 }]}>
                  <LinearGradient colors={m.colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.mood}>
                    <View style={{ position: "absolute", right: -18, bottom: -18, width: 70, height: 70, borderRadius: 35, backgroundColor: "rgba(255,255,255,0.16)" }} />
                    <Text style={{ color: "#fff", fontFamily: f.display, fontSize: 15 }}>{m.name}</Text>
                  </LinearGradient>
                </Pressable>
              ))}
            </View>
          </>
        ) : null}
      </ScrollView>
    </View>
  );
}

const st = StyleSheet.create({
  field: { flexDirection: "row", alignItems: "center", gap: 10, height: 52, borderRadius: 18, paddingHorizontal: 16, marginTop: 14,
    backgroundColor: "rgba(255,255,255,0.08)", borderWidth: 1, borderColor: c.line },
  fieldOn: { borderColor: c.accent, backgroundColor: "rgba(245,194,231,0.07)" },
  clear: { width: 22, height: 22, borderRadius: 11, backgroundColor: "rgba(255,255,255,0.16)", alignItems: "center", justifyContent: "center" },
  suggest: { marginTop: 8, borderRadius: 18, backgroundColor: "#15131f", borderWidth: 1, borderColor: c.line, overflow: "hidden" },
  suggestRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 13 },
  suggestLine: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: c.line },
  playPill: { flexDirection: "row", alignItems: "center", gap: 6, height: 34, paddingHorizontal: 14, borderRadius: 999, backgroundColor: c.accent },
  ghostPill: { height: 34, paddingHorizontal: 14, borderRadius: 999, justifyContent: "center", borderWidth: 1, borderColor: c.line2 },
  chip: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, borderWidth: 1,
    borderColor: c.line, backgroundColor: "rgba(255,255,255,0.05)" },
  mood: { height: 76, borderRadius: 20, padding: 14, justifyContent: "flex-end", overflow: "hidden" },
  note: { flexDirection: "row", alignItems: "center", gap: 12, marginTop: 18, padding: 14, borderRadius: 18, backgroundColor: c.surface,
    borderWidth: 1, borderColor: c.line },
});
