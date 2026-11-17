/**
 * The taste model. Every play that ends becomes a signal (finished, skipped,
 * replayed...), added to the song's and its artist's score. Scores fade: a
 * signal counts half after HALF_LIFE, a quarter after two. Each update is
 * O(1): a score is stored with the time it was true, and aged on read.
 */
import type { Sql } from "./db";

export const DAY = 86400;
export const HALF_LIFE = 21 * DAY;

/** What each thing you do says about a song. */
export const SIGNAL = {
  completed: 1.0,  // played past 80%
  replay: 2.0,     // played again within a day of finishing it
  liked: 3.0,
  unliked: -3.0,
  downloaded: 2.5,
  searched: 1.5,   // looked for by name and played
  skipped: -1.5,   // left within the first 30 s
  partial: 0.3,    // neither: some of it, then moved on
} as const;

/** Artist affinity moves slower than a song's score: a share of each signal. */
const ARTIST_SHARE = 0.35;

export function aged(score: number, since: number, now: number): number {
  return score * Math.pow(0.5, Math.max(0, now - since) / HALF_LIFE);
}

export type PlayEnd = {
  songId: string;
  startedAt: number;     // unix seconds
  listenedMs: number;
  durationMs: number;
  source?: string;
  offline?: boolean;
};

/** Records a play that ended and teaches the model. Returns the signal it gave. */
export function recordPlay(db: Sql, p: PlayEnd, now = p.startedAt + Math.round(p.listenedMs / 1000)): number {
  const completed = p.durationMs > 0 && p.listenedMs >= p.durationMs * 0.8;
  const skipped = !completed && p.listenedMs < 30_000;
  db.runSync(
    "INSERT INTO play(song_id, started_at, listened_ms, completed, skipped, source, offline) VALUES (?, ?, ?, ?, ?, ?, ?)",
    p.songId, p.startedAt, p.listenedMs, completed ? 1 : 0, skipped ? 1 : 0, p.source ?? "other", p.offline ? 1 : 0);
  let w: number = completed ? SIGNAL.completed : skipped ? SIGNAL.skipped : SIGNAL.partial;
  if (completed) {
    const again = db.getFirstSync<{ n: number }>(
      "SELECT count(*) AS n FROM play WHERE song_id = ? AND completed = 1 AND started_at < ? AND started_at > ?",
      p.songId, p.startedAt, p.startedAt - DAY);
    if ((again?.n ?? 0) > 0) w = SIGNAL.replay;
    if (p.source === "search") w += SIGNAL.searched;
  }
  const hour = new Date(p.startedAt * 1000).getHours();
  addSignal(db, p.songId, w, now, skipped ? null : hour, true);
  return w;
}

/** Adds a signal to a song (and a share to its artist). `hour` counts the play
 *  in the song's hour-of-day profile. */
export function addSignal(db: Sql, songId: string, w: number, now: number, hour: number | null = null, played = false): void {
  const row = db.getFirstSync<{ score: number; updated_at: number; hours: string; plays: number }>(
    "SELECT score, updated_at, hours, plays FROM taste_song WHERE song_id = ?", songId);
  const hours: number[] = row ? JSON.parse(row.hours) : new Array(24).fill(0);
  if (hour !== null) hours[hour] = (hours[hour] ?? 0) + 1;
  const score = (row ? aged(row.score, row.updated_at, now) : 0) + w;
  db.runSync(
    `INSERT INTO taste_song(song_id, score, updated_at, hours, plays, last_played) VALUES (?, ?, ?, ?, ?, ?)
     ON CONFLICT(song_id) DO UPDATE SET score = excluded.score, updated_at = excluded.updated_at, hours = excluded.hours,
       plays = excluded.plays, last_played = coalesce(excluded.last_played, last_played)`,
    songId, score, now, JSON.stringify(hours), (row?.plays ?? 0) + (played ? 1 : 0), played ? now : null);
  const artist = db.getFirstSync<{ artist_id: string | null }>("SELECT artist_id FROM song WHERE id = ?", songId)?.artist_id;
  if (!artist) return;
  const a = db.getFirstSync<{ score: number; updated_at: number }>("SELECT score, updated_at FROM taste_artist WHERE artist_id = ?", artist);
  db.runSync(
    `INSERT INTO taste_artist(artist_id, score, updated_at, last_played) VALUES (?, ?, ?, ?)
     ON CONFLICT(artist_id) DO UPDATE SET score = excluded.score, updated_at = excluded.updated_at,
       last_played = coalesce(excluded.last_played, last_played)`,
    artist, (a ? aged(a.score, a.updated_at, now) : 0) + w * ARTIST_SHARE, now, played ? now : null);
}

export function like(db: Sql, songId: string, on: boolean, now: number): void {
  if (on) db.runSync("INSERT OR IGNORE INTO liked(song_id, at) VALUES (?, ?)", songId, now);
  else db.runSync("DELETE FROM liked WHERE song_id = ?", songId);
  addSignal(db, songId, on ? SIGNAL.liked : SIGNAL.unliked, now);
}

/** "Not interested": never suggested again (still playable when you ask for it). */
export function hide(db: Sql, kind: "song" | "artist", id: string, now: number): void {
  db.runSync("INSERT OR REPLACE INTO hidden(kind, id, at) VALUES (?, ?, ?)", kind, id, now);
}

/** How well an hour suits a song, from when it has been played: 1 is neutral,
 *  up to 1.6 for its usual hours, down to 0.7 for hours it never gets. The
 *  neighbouring hours count half, so 10:55 pm still feels like 11. */
export function hourFit(hours: number[], hour: number): number {
  const total = hours.reduce((a, b) => a + b, 0);
  if (total < 3) return 1;   // too little to tell
  const near = (hours[hour] ?? 0) + 0.5 * ((hours[(hour + 23) % 24] ?? 0) + (hours[(hour + 1) % 24] ?? 0));
  const share = near / (total * 2 / 24);   // 1 = an even spread
  return Math.min(1.6, Math.max(0.7, 0.7 + 0.3 * share));
}

/** Forgets everything the model learned (history stays unless asked). */
export function resetTaste(db: Sql, history = false): void {
  db.execSync("DELETE FROM taste_song; DELETE FROM taste_artist;" + (history ? " DELETE FROM play; DELETE FROM search;" : ""));
}
