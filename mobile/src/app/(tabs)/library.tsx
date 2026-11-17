import { useFocusEffect } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { Text } from "../../ui/text";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { Song } from "../../core/db";
import { SMART, smartPlaylist } from "../../core/feed";
import { getDb, now } from "../../core/store";
import { storageUsed, useDownloads } from "../../player/downloads";
import { playSongs } from "../../player/player";
import { Aurora, POOLS } from "../../ui/aurora";
import { Icon, type IconName } from "../../ui/icons";
import { songMenu } from "../../ui/menu";
import { Card, Empty, SongRow, Tag, Title, s } from "../../ui/parts";
import { BOTTOM, c, f } from "../../ui/theme";

type View_ = "liked" | "downloads" | "history" | keyof typeof SMART;

function songs(v: View_): Song[] {
  const db = getDb();
  switch (v) {
    case "liked": return db.getAllSync<Song>("SELECT s.* FROM liked l JOIN song s ON s.id = l.song_id ORDER BY l.at DESC");
    case "downloads": return db.getAllSync<Song>("SELECT s.* FROM download d JOIN song s ON s.id = d.song_id WHERE d.state = 'done' ORDER BY d.at DESC");
    case "history": return db.getAllSync<Song>(
      "SELECT s.* FROM song s JOIN (SELECT song_id, max(started_at) AS at FROM play GROUP BY song_id) p ON p.song_id = s.id ORDER BY p.at DESC LIMIT 200");
    default: return smartPlaylist(db, v, now());
  }
}

const NAMES: Record<string, string> = { liked: "Liked", downloads: "Downloads", history: "History",
  ...Object.fromEntries(Object.entries(SMART).map(([k, v]) => [k, v.name])) };

export default function Library() {
  const insets = useSafeAreaInsets();
  const dl = useDownloads();
  const [open, setOpen] = useState<View_>("liked");
  const [list, setList] = useState<Song[]>([]);
  const [counts, setCounts] = useState({ liked: 0, downloads: 0, plays: 0, queued: 0 });
  const [queue, setQueue] = useState<(Song & { state: string })[]>([]);

  const refresh = useCallback(() => {
    const db = getDb();
    const n = (sql: string) => db.getFirstSync<{ n: number }>(sql)?.n ?? 0;
    setCounts({
      liked: n("SELECT count(*) AS n FROM liked"),
      downloads: n("SELECT count(*) AS n FROM download WHERE state = 'done'"),
      plays: n("SELECT count(*) AS n FROM play"),
      queued: n("SELECT count(*) AS n FROM download WHERE state IN ('queued', 'running')"),
    });
    setQueue(db.getAllSync<Song & { state: string }>(
      "SELECT s.*, d.state FROM download d JOIN song s ON s.id = d.song_id WHERE d.state IN ('queued', 'running', 'failed') ORDER BY d.at"));
    setList(songs(open));
  }, [open]);
  useFocusEffect(refresh);
  useEffect(refresh, [dl, refresh]);   // a download finished or failed

  const used = storageUsed();
  const mb = used.bytes / 1e6;
  const cards: { id: View_; icon: IconName; color: string; name: string; sub: string }[] = [
    { id: "liked", icon: "heart", color: c.accent, name: "Liked", sub: `${counts.liked} songs` },
    { id: "downloads", icon: "offline", color: c.green, name: "Downloads", sub: `${counts.downloads} songs` },
    { id: "mostPlayed", icon: "list", color: c.sky, name: "Smart lists", sub: `${Object.keys(SMART).length} that keep up` },
    { id: "history", icon: "clock", color: c.mauve, name: "History", sub: `${counts.plays.toLocaleString()} plays` },
  ];

  return (
    <View style={s.screen}>
      <Aurora pools={POOLS.library!} />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingTop: insets.top + 12, paddingHorizontal: 18, paddingBottom: BOTTOM }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Text style={s.h1}>Library</Text>
        <Tag color={c.green}>{`${counts.downloads} offline`}</Tag>
      </View>

      <Card style={{ padding: 14, marginTop: 12 }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
          <Text style={{ color: c.text, fontFamily: f.semibold, fontSize: 12.5 }}>Music on this phone</Text>
          <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 12.5 }}>{mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : `${Math.round(mb)} MB`}</Text>
        </View>
        <View style={{ height: 10, borderRadius: 6, backgroundColor: "rgba(255,255,255,0.08)", marginTop: 10, flexDirection: "row", overflow: "hidden" }}>
          <View style={{ width: `${Math.min(100, mb / 80)}%`, backgroundColor: c.green }} />
          {counts.queued ? <View style={{ width: "3%", backgroundColor: c.yellow }} /> : null}
        </View>
      </Card>

      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 12 }}>
        {cards.map((k) => {
          const on = open === k.id || (k.id === "mostPlayed" && k.id in SMART && open in SMART);
          return (
            <Pressable key={k.id} onPress={() => { setOpen(k.id); setList(songs(k.id)); }}
              style={{ width: "48%", flexGrow: 1, height: 88, padding: 13, borderRadius: 18, justifyContent: "space-between",
                backgroundColor: on ? "rgba(245,194,231,0.08)" : c.surface, borderWidth: 1, borderColor: on ? "rgba(245,194,231,0.35)" : c.line }}>
              <Icon name={k.icon} size={22} color={k.color} />
              <View>
                <Text style={{ color: c.text, fontFamily: f.semibold, fontSize: 13.5 }}>{k.name}</Text>
                <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 11.5 }}>{k.sub}</Text>
              </View>
            </Pressable>
          );
        })}
      </View>

      {queue.length ? (
        <>
          <Title small={`${queue.filter((q) => q.state !== "failed").length} left`}>Downloading</Title>
          {queue.map((song) => (
            <SongRow key={song.id} song={song} onPress={() => songMenu(song)}
              right={<Tag color={song.state === "failed" ? c.red : c.yellow}>{song.state === "running" ? "saving" : song.state === "failed" ? "failed" : "next"}</Tag>} />
          ))}
        </>
      ) : null}

      {open in SMART ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, marginTop: 18 }}>
          {Object.entries(SMART).map(([k, v]) => (
            <Pressable key={k} onPress={() => { setOpen(k as View_); setList(songs(k as View_)); }}
              style={{ paddingHorizontal: 13, paddingVertical: 7, borderRadius: 999, backgroundColor: open === k ? c.accent : c.surface, borderWidth: 1, borderColor: open === k ? c.accent : c.line }}>
              <Text style={{ color: open === k ? c.crust : c.sub, fontFamily: open === k ? f.semibold : f.body, fontSize: 12.5 }}>{v.name}</Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : null}

      <Title small={list.length ? `${list.length}` : undefined}>{NAMES[open]}</Title>
      {list.length ? (
        <>
          <Pressable onPress={() => playSongs(list, 0, NAMES[open]!)} style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <Icon name="play" size={16} color={c.accent} />
            <Text style={{ color: c.accent, fontFamily: f.semibold, fontSize: 13 }}>Play all</Text>
          </Pressable>
          {list.map((song, i) => <SongRow key={song.id} song={song} onPress={() => playSongs(list, i, NAMES[open]!)} onMore={() => songMenu(song)} />)}
        </>
      ) : (
        <Empty title="Nothing here yet" body={open === "downloads" ? "Download a song from Search or from the player, and it plays with no signal."
          : open === "liked" ? "Tap the heart while a song plays." : "Play some music and this fills up by itself."} />
      )}
      </ScrollView>
    </View>
  );
}
