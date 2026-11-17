/**
 * The player: one audio player (expo-audio, background and lock screen), a
 * queue, and autoplay like YouTube Music's "up next". Every play that ends is
 * written to the database and teaches the taste model (core/taste.ts).
 *
 * State lives in a small store any screen can subscribe to (usePlayer).
 */
import { createAudioPlayer, setAudioModeAsync, type AudioPlayer, type AudioStatus } from "expo-audio";
import { useSyncExternalStore } from "react";
import { saveSong, type Song } from "../core/db";
import { getDb, now } from "../core/store";
import { recordPlay } from "../core/taste";
import { localFile } from "./downloads";
import { yt } from "../youtube";
import { STREAM_UA } from "../youtube/ytmusic";
import { log } from "../core/log";

export type PlayerState = {
  queue: Song[];
  index: number;
  playing: boolean;
  buffering: boolean;
  positionMs: number;
  durationMs: number;
  source: string;          // where the queue came from: "Midnight Mix", "Search"...
  error: string | null;
  repeat: boolean;
};

let state: PlayerState = {
  queue: [], index: -1, playing: false, buffering: false, positionMs: 0, durationMs: 0, source: "", error: null, repeat: false,
};
const subs = new Set<() => void>();
function set(p: Partial<PlayerState>) {
  state = { ...state, ...p };
  subs.forEach((f) => f());
}
export function usePlayer(): PlayerState {
  return useSyncExternalStore((f) => (subs.add(f), () => subs.delete(f)), () => state);
}
export const current = (): Song | null => state.queue[state.index] ?? null;

// ===================================================================== audio
let player: AudioPlayer | null = null;
let started = 0;          // when the current song started (unix s)
let listened = 0;         // ms actually played, so seeking doesn't count
let lastPos = 0;
let loadToken = 0;

function audio(): AudioPlayer {
  if (player) return player;
  setAudioModeAsync({ playsInSilentMode: true, shouldPlayInBackground: true, interruptionMode: "doNotMix" }).catch(() => {});
  player = createAudioPlayer(null, { updateInterval: 250 });
  player.addListener("playbackStatusUpdate", onStatus);
  return player;
}

function onStatus(s: AudioStatus) {
  const pos = Math.round((s.currentTime ?? 0) * 1000);
  if (s.playing && pos > lastPos && pos - lastPos < 2000) listened += pos - lastPos;
  lastPos = pos;
  set({
    playing: s.playing, buffering: !!s.isBuffering && s.playing,
    positionMs: pos, durationMs: s.duration ? Math.round(s.duration * 1000) : current()?.duration_ms ?? 0,
  });
  if (s.didJustFinish) {
    if (state.repeat) { audio().seekTo(0); audio().play(); }
    else void next();
  }
}

/** Writes the play that's ending into history (and the taste model). */
function finishPlay() {
  const s = current();
  if (!s || !started || listened < 1000) return;
  try {
    recordPlay(getDb(), { songId: s.id, startedAt: started, listenedMs: listened, durationMs: s.duration_ms || state.durationMs,
      source: sourceKind(state.source), offline: !!localFile(s.id) });
  } catch (e) {
    log("record play failed", e);
  }
  started = 0;
  listened = 0;
}

function sourceKind(label: string): string {
  const l = label.toLowerCase();
  if (l === "search") return "search";
  if (l.includes("mix") || l === "for you") return "mix";
  if (l.startsWith("radio") || l === "up next") return "radio";
  if (l === "widget") return "widget";
  return "other";
}

async function load(i: number) {
  const s = state.queue[i];
  if (!s) return;
  finishPlay();
  const token = ++loadToken;
  set({ index: i, positionMs: 0, durationMs: s.duration_ms, buffering: true, error: null });
  try {
    saveSong(getDb(), s, now());
    const file = localFile(s.id);
    const src = file ? { uri: file } : { uri: (await yt.stream(s.id)).url, headers: { "user-agent": STREAM_UA } };
    if (token !== loadToken) return;   // another song was picked meanwhile
    const p = audio();
    p.replace(src);
    p.play();
    started = now();
    listened = 0;
    lastPos = 0;
    p.setActiveForLockScreen(true, { title: s.title, artist: s.artist_name, artworkUrl: s.cover_url ?? undefined });
    void keepRelated(s.id);
  } catch (e) {
    log("load failed", s.id, e);
    if (token === loadToken) set({ buffering: false, playing: false, error: e instanceof Error ? e.message : String(e) });
  }
}

/** YouTube Music's "up next" for a song, kept a week: the feed is built from it. */
export async function keepRelated(id: string): Promise<Song[]> {
  const db = getDb();
  const fresh = db.getFirstSync<{ n: number }>("SELECT count(*) AS n FROM related WHERE song_id = ? AND fetched_at > ?", id, now() - 7 * 86400);
  if ((fresh?.n ?? 0) > 0) {
    return db.getAllSync<Song>("SELECT s.* FROM related r JOIN song s ON s.id = r.related_id WHERE r.song_id = ? ORDER BY r.rank", id);
  }
  const rel = await yt.related(id);
  const t = now();
  db.runSync("DELETE FROM related WHERE song_id = ?", id);
  rel.forEach((s, rank) => {
    saveSong(db, s, t);
    db.runSync("INSERT OR REPLACE INTO related(song_id, related_id, rank, fetched_at) VALUES (?, ?, ?, ?)", id, s.id, rank, t);
  });
  return rel;
}

// ===================================================================== actions
export function playSongs(songs: Song[], start = 0, source = "") {
  set({ queue: songs, source });
  void load(start);
}

export function toggle() {
  if (!player || state.index < 0) return;
  if (state.playing) player.pause();
  else player.play();
}

/** The next song; at the end of the queue, more like the last one (autoplay). */
export async function next() {
  if (state.index + 1 < state.queue.length) return load(state.index + 1);
  const last = current();
  if (!last) return;
  try {
    const hidden = new Set(getDb().getAllSync<{ id: string }>("SELECT id FROM hidden").map((h) => h.id));
    const have = new Set(state.queue.map((s) => s.id));
    const more = (await keepRelated(last.id)).filter((s) => !have.has(s.id) && !hidden.has(s.id) && !hidden.has(s.artist_id ?? ""));
    if (more.length) {
      set({ queue: [...state.queue, ...more.slice(0, 25)] });
      return load(state.index + 1);
    }
  } catch (e) {
    log("autoplay failed", e);
  }
  finishPlay();
  set({ playing: false });
}

export function prev() {
  if (state.positionMs > 3000 || state.index === 0) return player?.seekTo(0);
  return load(state.index - 1);
}

export function seek(ms: number) {
  player?.seekTo(ms / 1000);
  lastPos = ms;
}

export function jump(i: number) {
  void load(i);
}

export function playNext(s: Song) {
  const q = [...state.queue];
  q.splice(state.index + 1, 0, s);
  set({ queue: q });
  if (state.index < 0) void load(0);
}

export function setRepeat(on: boolean) {
  set({ repeat: on });
}

export function shuffleRest() {
  const head = state.queue.slice(0, state.index + 1);
  const rest = state.queue.slice(state.index + 1);
  for (let i = rest.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [rest[i], rest[j]] = [rest[j]!, rest[i]!];
  }
  set({ queue: [...head, ...rest] });
}
