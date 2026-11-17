/**
 * Home, built on the phone from the taste model (taste.ts) and YouTube
 * Music's "related" lists kept in the database. Every section says why it is
 * there. Pure reads: nothing here touches the network, so Home works offline.
 */
import type { Song, Sql } from "./db";
import { DAY, HALF_LIFE, hourFit } from "./taste";

export type Section = {
  id: string;
  title: string;
  why: string;          // the peach "because…" line
  songs: Song[];
};

type Scored = Song & { score: number; updated_at: number; hours: string; last_played: number | null; plays: number };

const NOT_HIDDEN = `s.id NOT IN (SELECT id FROM hidden WHERE kind = 'song')
  AND coalesce(s.artist_id, '') NOT IN (SELECT id FROM hidden WHERE kind = 'artist')`;

/** Songs by how much you'd want them right now: the aged score, times how
 *  well this hour suits them, plus a share of the artist's affinity. */
function ranked(db: Sql, now: number): (Scored & { now: number })[] {
  const hour = new Date(now * 1000).getHours();
  const rows = db.getAllSync<Scored & { artist_score: number; artist_at: number | null }>(
    `SELECT s.*, t.score, t.updated_at, t.hours, t.last_played, t.plays,
            coalesce(a.score, 0) AS artist_score, a.updated_at AS artist_at
     FROM taste_song t JOIN song s ON s.id = t.song_id LEFT JOIN taste_artist a ON a.artist_id = s.artist_id
     WHERE ${NOT_HIDDEN}`);
  return rows.map((r) => {
    const age = (at: number | null, v: number) => (at === null ? v : v * Math.pow(0.5, Math.max(0, now - at) / HALF_LIFE));
    const fit = hourFit(JSON.parse(r.hours), hour);
    return { ...r, now: age(r.updated_at, r.score) * fit + 0.6 * age(r.artist_at, r.artist_score) };
  }).sort((a, b) => b.now - a.now);
}

/** The related songs YouTube Music gave for these, best first, minus what
 *  you've already played and anything hidden. */
function discover(db: Sql, seeds: string[], limit: number): Song[] {
  if (!seeds.length) return [];
  const marks = seeds.map(() => "?").join(",");
  return db.getAllSync<Song>(
    `SELECT s.* FROM related r JOIN song s ON s.id = r.related_id
     WHERE r.song_id IN (${marks}) AND s.id NOT IN (SELECT song_id FROM play) AND ${NOT_HIDDEN}
     GROUP BY s.id ORDER BY min(r.rank), count(*) DESC LIMIT ?`, ...seeds, limit);
}

/** Interleaves two lists about 60/40 (3 of a, 2 of b), without repeats. */
export function blend(a: Song[], b: Song[], size: number): Song[] {
  const out: Song[] = [];
  const seen = new Set<string>();
  let i = 0, j = 0;
  while (out.length < size && (i < a.length || j < b.length)) {
    for (let k = 0; k < 3 && i < a.length; k++, i++) if (!seen.has(a[i]!.id)) { seen.add(a[i]!.id); out.push(a[i]!); }
    for (let k = 0; k < 2 && j < b.length; k++, j++) if (!seen.has(b[j]!.id)) { seen.add(b[j]!.id); out.push(b[j]!); }
  }
  return out.slice(0, size);
}

export function partOfDay(now: number): { name: string; mix: string } {
  const d = new Date(now * 1000);
  const h = d.getHours();
  const weekend = d.getDay() === 0 || d.getDay() === 6;
  if (h < 5) return { name: "late night", mix: "After Hours" };
  if (h < 12) return { name: weekend ? "weekend morning" : "morning", mix: weekend ? "Slow Sunday" : "Morning Lift" };
  if (h < 17) return { name: "afternoon", mix: "Afternoon Flow" };
  if (h < 21) return { name: "evening", mix: "Evening Glow" };
  return { name: "night", mix: "Midnight Mix" };
}

export function buildHome(db: Sql, now: number): Section[] {
  const out: Section[] = [];
  const all = ranked(db, now);
  const fresh = all.filter((s) => !s.last_played || now - s.last_played > 2 * 3600);   // not what just played
  const pod = partOfDay(now);

  // For you: favourites for this hour, mixed with new songs related to them
  const favs = fresh.filter((s) => s.now > 0).slice(0, 30);
  const mix = blend(favs, discover(db, favs.slice(0, 8).map((s) => s.id), 20), 32);
  if (mix.length >= 4) {
    const known = mix.filter((s) => favs.some((f) => f.id === s.id)).length;
    out.push({ id: "for-you", title: pod.mix, why: `for your ${pod.name}s · ${known} you love, ${mix.length - known} new to you`, songs: mix });
  }

  // More like X: the song you've finished most this week, and its relatives
  const top = db.getFirstSync<{ song_id: string; n: number }>(
    `SELECT p.song_id, count(*) AS n FROM play p JOIN song s ON s.id = p.song_id
     WHERE p.completed = 1 AND p.started_at > ? AND ${NOT_HIDDEN} GROUP BY p.song_id ORDER BY n DESC, max(p.started_at) DESC LIMIT 1`,
    now - 7 * DAY);
  if (top && top.n >= 2) {
    const like = discover(db, [top.song_id], 15);
    const title = db.getFirstSync<{ title: string }>("SELECT title FROM song WHERE id = ?", top.song_id)?.title ?? "";
    if (like.length >= 3) out.push({ id: "more-like", title: `More like ${title}`, why: `you played it ${top.n} times this week`, songs: like });
  }

  // Jump back in: what you played lately, newest first
  const recent = db.getAllSync<Song>(
    `SELECT s.* FROM song s JOIN (SELECT song_id, max(started_at) AS at FROM play GROUP BY song_id) p ON p.song_id = s.id
     WHERE ${NOT_HIDDEN} ORDER BY p.at DESC LIMIT 12`);
  if (recent.length) out.push({ id: "recent", title: "Jump back in", why: "what you played lately", songs: recent });

  // Rediscover: loved once, not heard in a month
  const old = all.filter((s) => s.last_played && now - s.last_played > 30 * DAY && s.plays >= 3).slice(0, 15);
  if (old.length >= 3) out.push({ id: "rediscover", title: "Rediscover", why: "songs you loved, not played in a month", songs: old });

  // Offline ready: downloads only, for no signal
  const offline = db.getAllSync<Song>(
    `SELECT s.* FROM download d JOIN song s ON s.id = d.song_id LEFT JOIN taste_song t ON t.song_id = s.id
     WHERE d.state = 'done' ORDER BY coalesce(t.score, 0) DESC LIMIT 30`);
  if (offline.length) out.push({ id: "offline", title: "Offline ready", why: "on this phone, plays with no signal", songs: offline });
  return out;
}

/** Smart playlists: saved rules, read live from the database. */
export const SMART: Record<string, { name: string; sql: string }> = {
  forgotten: { name: "Loved, not heard in a month", sql: `SELECT s.* FROM taste_song t JOIN song s ON s.id = t.song_id
      WHERE t.plays >= 3 AND t.last_played < :now - 30 * 86400 ORDER BY t.score DESC LIMIT 100` },
  lateNight: { name: "Late-night repeats", sql: `SELECT s.* FROM play p JOIN song s ON s.id = p.song_id
      WHERE p.completed = 1 AND cast(strftime('%H', p.started_at, 'unixepoch', 'localtime') AS INTEGER) IN (22, 23, 0, 1, 2, 3)
      GROUP BY s.id HAVING count(*) >= 2 ORDER BY count(*) DESC LIMIT 100` },
  mostPlayed: { name: "Most played", sql: `SELECT s.* FROM play p JOIN song s ON s.id = p.song_id WHERE p.completed = 1
      GROUP BY s.id ORDER BY count(*) DESC LIMIT 100` },
};

export function smartPlaylist(db: Sql, rule: keyof typeof SMART, now: number): Song[] {
  return db.getAllSync<Song>(SMART[rule]!.sql.replaceAll(":now", String(now)));
}
