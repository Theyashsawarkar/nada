/**
 * Insights: what your listening looks like, read from the play table. All
 * local time, all on the phone; nothing here is ever uploaded.
 */
import type { Sql } from "./db";
import { DAY } from "./taste";

/** Midnight (local) of the day `t` falls in, as unix seconds. */
export function dayStart(t: number): number {
  const d = new Date(t * 1000);
  d.setHours(0, 0, 0, 0);
  return Math.floor(d.getTime() / 1000);
}

export type Week = {
  minutes: number;
  lastWeekMinutes: number;
  change: number | null;      // +0.18 = 18% more than the week before; null with nothing to compare
  daily: number[];            // minutes for each of the last 7 days, today last
  hours: number[];            // minutes by hour of day (24), this week
  topHour: number | null;
  streak: number;             // days in a row with music, up to today (or yesterday)
  bestStreak: number;
  topArtist: { id: string; name: string; minutes: number; plays: number; songs: number; newNumberOne: boolean } | null;
  moods: { name: string; share: number }[];
};

const MIN = (sql: string) => `cast(round(coalesce(sum(${sql}), 0) / 60000.0) AS INTEGER)`;

export function week(db: Sql, now: number): Week {
  const today = dayStart(now);
  const from = today - 6 * DAY;
  const minutes = db.getFirstSync<{ m: number }>(`SELECT ${MIN("listened_ms")} AS m FROM play WHERE started_at >= ?`, from)?.m ?? 0;
  const last = db.getFirstSync<{ m: number }>(`SELECT ${MIN("listened_ms")} AS m FROM play WHERE started_at >= ? AND started_at < ?`,
    from - 7 * DAY, from)?.m ?? 0;

  const daily: number[] = [];
  for (let i = 6; i >= 0; i--) {
    const a = today - i * DAY;
    daily.push(db.getFirstSync<{ m: number }>(`SELECT ${MIN("listened_ms")} AS m FROM play WHERE started_at >= ? AND started_at < ?`,
      a, a + DAY)?.m ?? 0);
  }
  const hours = new Array<number>(24).fill(0);
  for (const r of db.getAllSync<{ h: number; m: number }>(
    `SELECT cast(strftime('%H', started_at, 'unixepoch', 'localtime') AS INTEGER) AS h, sum(listened_ms) / 60000.0 AS m
     FROM play WHERE started_at >= ? GROUP BY h`, from)) hours[r.h] = Math.round(r.m);
  const topHour = Math.max(...hours) > 0 ? hours.indexOf(Math.max(...hours)) : null;

  const [streak, bestStreak] = streaks(db, now);

  const artists = (a: number, b: number) => db.getAllSync<{ id: string; name: string; minutes: number; plays: number; songs: number }>(
    `SELECT s.artist_id AS id, coalesce(ar.name, s.artist_name) AS name, sum(p.listened_ms) / 60000 AS minutes,
            count(*) AS plays, count(DISTINCT s.id) AS songs
     FROM play p JOIN song s ON s.id = p.song_id LEFT JOIN artist ar ON ar.id = s.artist_id
     WHERE p.started_at >= ? AND p.started_at < ? AND s.artist_id IS NOT NULL
     GROUP BY s.artist_id ORDER BY minutes DESC LIMIT 1`, a, b);
  const top = artists(from, now + 1)[0];
  const before = artists(from - 7 * DAY, from)[0];

  const moodRows = db.getAllSync<{ g: string; m: number }>(
    `SELECT coalesce(nullif(s.genre, ''), 'Unsorted') AS g, sum(p.listened_ms) AS m FROM play p JOIN song s ON s.id = p.song_id
     WHERE p.started_at >= ? GROUP BY g ORDER BY m DESC LIMIT 4`, from);
  const totalMs = moodRows.reduce((a, r) => a + r.m, 0);

  return {
    minutes, lastWeekMinutes: last, change: last > 0 ? (minutes - last) / last : null,
    daily, hours, topHour, streak, bestStreak,
    topArtist: top ? { ...top, minutes: Math.round(top.minutes), newNumberOne: !!before && before.id !== top.id } : null,
    moods: moodRows.map((r) => ({ name: r.g, share: totalMs ? r.m / totalMs : 0 })),
  };
}

/** [current streak, best streak] in days. A streak still counts today if
 *  you listened yesterday and haven't yet today. */
export function streaks(db: Sql, now: number): [number, number] {
  const days = db.getAllSync<{ d: string }>(
    "SELECT DISTINCT date(started_at, 'unixepoch', 'localtime') AS d FROM play WHERE listened_ms >= 30000 ORDER BY d")
    .map((r) => Date.parse(r.d + "T00:00:00Z") / 86400000);
  if (!days.length) return [0, 0];
  let best = 1, run = 1;
  for (let i = 1; i < days.length; i++) {
    run = days[i]! - days[i - 1]! === 1 ? run + 1 : 1;
    best = Math.max(best, run);
  }
  const d = new Date(now * 1000);
  const todayN = Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86400000;
  const lastDay = days[days.length - 1]!;
  return [todayN - lastDay <= 1 ? run : 0, best];
}

/** "11 PM" for 23. */
export function hourName(h: number): string {
  return `${h % 12 === 0 ? 12 : h % 12} ${h < 12 ? "AM" : "PM"}`;
}
