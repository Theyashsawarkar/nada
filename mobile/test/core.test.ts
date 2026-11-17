import { describe, expect, it } from "vitest";
import { MIGRATIONS, migrate, saveSong, searchLocal, type Song } from "../src/core/db";
import { blend, buildHome, partOfDay, smartPlaylist } from "../src/core/feed";
import { dayStart, hourName, streaks, week } from "../src/core/insights";
import { DAY, HALF_LIFE, SIGNAL, aged, hide, hourFit, like, recordPlay } from "../src/core/taste";
import { memoryDb } from "./sqlite";

// a Tuesday, 23:00 local time
const NIGHT = Math.floor(new Date(2026, 10, 10, 23, 0, 0).getTime() / 1000);

const song = (id: string, artist = "mira", extra: Partial<Song> = {}): Song => ({
  id, title: `Song ${id}`, artist_id: artist, artist_name: artist === "mira" ? "Mira Sen" : `Artist ${artist}`,
  duration_ms: 200_000, ...extra,
});

function play(db: ReturnType<typeof memoryDb>, id: string, at: number, ms = 200_000, source?: string) {
  return recordPlay(db, { songId: id, startedAt: at, listenedMs: ms, durationMs: 200_000, source });
}

describe("database", () => {
  it("migrates once, and again is a no-op", () => {
    const db = memoryDb();
    expect(migrate(db)).toBe(MIGRATIONS.length);
    expect(db.getFirstSync<{ user_version: number }>("PRAGMA user_version")?.user_version).toBe(MIGRATIONS.length);
  });

  it("finds songs on the phone by any word, liked ones first", () => {
    const db = memoryDb();
    saveSong(db, song("a", "mira", { title: "Glass Temple" }), NIGHT);
    saveSong(db, song("b", "ira", { title: "Glass Temples" }), NIGHT);
    saveSong(db, song("c", "ira", { title: "Blue Hour" }), NIGHT);
    for (let i = 0; i < 4; i++) play(db, "a", NIGHT - i * DAY);
    expect(searchLocal(db, "glass tem").map((s) => s.id)).toEqual(["a"]);   // b was only seen, never played
    like(db, "b", true, NIGHT);
    const hits = searchLocal(db, "glass tem");
    expect(hits.map((s) => s.id)).toEqual(["a", "b"]);
    expect(searchLocal(db, "mira").map((s) => s.id)).toEqual(["a"]);
    expect(searchLocal(db, "  ")).toEqual([]);
  });

  it("updates a song without losing what it knew", () => {
    const db = memoryDb();
    saveSong(db, song("a", "mira", { genre: "Indie", cover_url: "x" }), NIGHT);
    saveSong(db, song("a", "mira", { title: "Renamed" }), NIGHT + 1);
    like(db, "a", true, NIGHT + 1);
    const s = db.getFirstSync<Song>("SELECT * FROM song WHERE id = 'a'")!;
    expect([s.title, s.genre, s.cover_url]).toEqual(["Renamed", "Indie", "x"]);
    expect(searchLocal(db, "renamed").length).toBe(1);
  });
});

describe("taste", () => {
  it("halves a signal every half-life", () => {
    expect(aged(8, 0, HALF_LIFE)).toBeCloseTo(4);
    expect(aged(8, 0, 2 * HALF_LIFE)).toBeCloseTo(2);
    expect(aged(8, 100, 50)).toBe(8);   // never grows backwards in time
  });

  it("reads plays as finished, skipped, replayed or searched", () => {
    const db = memoryDb();
    saveSong(db, song("a"), NIGHT);
    expect(play(db, "a", NIGHT - 3600)).toBe(SIGNAL.completed);
    expect(play(db, "a", NIGHT - 1800)).toBe(SIGNAL.replay);
    expect(play(db, "a", NIGHT, 10_000)).toBe(SIGNAL.skipped);
    expect(play(db, "a", NIGHT + 2 * DAY, 200_000, "search")).toBe(SIGNAL.completed + SIGNAL.searched);
    expect(play(db, "a", NIGHT + 3 * DAY, 60_000)).toBe(SIGNAL.partial);
    const t = db.getFirstSync<{ plays: number; hours: string }>("SELECT plays, hours FROM taste_song")!;
    expect(t.plays).toBe(5);
    expect(JSON.parse(t.hours).reduce((a: number, b: number) => a + b, 0)).toBe(4);   // a skip doesn't count its hour
  });

  it("gives the artist a share, and likes count", () => {
    const db = memoryDb();
    saveSong(db, song("a"), NIGHT);
    like(db, "a", true, NIGHT);
    const a = db.getFirstSync<{ score: number }>("SELECT score FROM taste_artist WHERE artist_id = 'mira'")!;
    expect(a.score).toBeCloseTo(SIGNAL.liked * 0.35);
    expect(db.getFirstSync<{ n: number }>("SELECT count(*) AS n FROM liked")!.n).toBe(1);
  });

  it("knows which hours suit a song", () => {
    const night = new Array(24).fill(0);
    night[23] = 8; night[22] = 2;
    expect(hourFit(night, 23)).toBeGreaterThan(1.3);
    expect(hourFit(night, 9)).toBe(0.7);
    expect(hourFit(new Array(24).fill(0), 9)).toBe(1);   // nothing known yet
  });
});

describe("home feed", () => {
  function library() {
    const db = memoryDb();
    for (const id of ["a", "b", "c", "d", "e"]) saveSong(db, song(id), NIGHT - 40 * DAY);
    for (const id of ["n1", "n2", "n3", "n4"]) saveSong(db, song(id, "kabir"), NIGHT);
    for (const [i, r] of ["n1", "n2", "n3", "n4"].entries()) {
      db.runSync("INSERT INTO related(song_id, related_id, rank, fetched_at) VALUES ('a', ?, ?, ?)", r, i, NIGHT);
    }
    return db;
  }

  it("mixes favourites with new related songs, and says why", () => {
    const db = library();
    for (let d = 1; d <= 5; d++) for (const id of ["a", "b", "c", "d"]) play(db, id, NIGHT - d * DAY);
    const home = buildHome(db, NIGHT);
    const mix = home.find((s) => s.id === "for-you")!;
    expect(mix.title).toBe("Midnight Mix");
    expect(mix.songs.map((s) => s.id)).toEqual(expect.arrayContaining(["a", "n1"]));
    expect(mix.why).toMatch(/for your nights · 4 you love, 4 new to you/);
  });

  it("offers more like this week's favourite", () => {
    const db = library();
    for (let i = 0; i < 3; i++) play(db, "a", NIGHT - i * DAY - 5 * 3600);
    const more = buildHome(db, NIGHT).find((s) => s.id === "more-like")!;
    expect(more.title).toBe("More like Song a");
    expect(more.why).toBe("you played it 3 times this week");
    expect(more.songs.map((s) => s.id)).toEqual(["n1", "n2", "n3", "n4"]);
  });

  it("brings back what you loved and stopped playing", () => {
    const db = library();
    for (let i = 0; i < 4; i++) play(db, "e", NIGHT - 60 * DAY + i * DAY);
    for (let i = 0; i < 4; i++) play(db, "b", NIGHT - 60 * DAY + i * DAY);
    for (let i = 0; i < 4; i++) play(db, "c", NIGHT - 60 * DAY + i * DAY);
    const re = buildHome(db, NIGHT).find((s) => s.id === "rediscover")!;
    expect(re.songs.map((s) => s.id).sort()).toEqual(["b", "c", "e"]);
  });

  it("never suggests what you hid", () => {
    const db = library();
    for (let d = 1; d <= 5; d++) for (const id of ["a", "b", "c", "d"]) play(db, id, NIGHT - d * DAY);
    hide(db, "song", "n1", NIGHT);
    hide(db, "artist", "kabir", NIGHT);
    const ids = buildHome(db, NIGHT).flatMap((s) => s.songs.map((x) => x.id));
    expect(ids).not.toContain("n1");
    expect(ids.some((i) => i.startsWith("n"))).toBe(false);
  });

  it("works with nothing played yet", () => {
    expect(buildHome(memoryDb(), NIGHT)).toEqual([]);
  });

  it("offers downloads for no signal", () => {
    const db = library();
    db.runSync("INSERT INTO download(song_id, state, at) VALUES ('b', 'done', ?), ('c', 'running', ?)", NIGHT, NIGHT);
    expect(buildHome(db, NIGHT).find((s) => s.id === "offline")!.songs.map((s) => s.id)).toEqual(["b"]);
  });

  it("blends 3 to 2 without repeats", () => {
    const s = (id: string) => song(id);
    expect(blend(["a", "b", "c", "d"].map(s), ["x", "a", "y"].map(s), 7).map((x) => x.id)).toEqual(["a", "b", "c", "x", "d", "y"]);
  });

  it("names the part of the day", () => {
    const at = (h: number, day = 10) => Math.floor(new Date(2026, 10, day, h).getTime() / 1000);
    expect(partOfDay(at(8)).mix).toBe("Morning Lift");
    expect(partOfDay(at(8, 15)).mix).toBe("Slow Sunday");
    expect(partOfDay(at(2)).mix).toBe("After Hours");
  });

  it("keeps smart playlists live", () => {
    const db = library();
    for (let i = 0; i < 2; i++) play(db, "a", NIGHT - i * DAY);
    expect(smartPlaylist(db, "lateNight", NIGHT).map((s) => s.id)).toEqual(["a"]);
    expect(smartPlaylist(db, "mostPlayed", NIGHT).map((s) => s.id)).toEqual(["a"]);
  });
});

describe("insights", () => {
  it("adds up the week and compares it with the last", () => {
    const db = memoryDb();
    saveSong(db, song("a", "mira", { genre: "Indie" }), NIGHT);
    saveSong(db, song("b", "kabir", { genre: "Ghazal" }), NIGHT);
    play(db, "a", NIGHT - 3600, 30 * 60_000);          // 30 min tonight at 10 PM
    play(db, "a", NIGHT - DAY, 30 * 60_000);
    play(db, "b", NIGHT - 10 * DAY, 50 * 60_000);      // last week
    const w = week(db, NIGHT);
    expect(w.minutes).toBe(60);
    expect(w.lastWeekMinutes).toBe(50);
    expect(w.change).toBeCloseTo(0.2);
    expect(w.daily.slice(-2)).toEqual([30, 30]);
    expect(w.topHour).toBe(22);
    expect(w.topArtist).toMatchObject({ id: "mira", plays: 2, songs: 1, newNumberOne: true });
    expect(w.moods).toEqual([{ name: "Indie", share: 1 }]);
  });

  it("counts streaks, forgiving a day you haven't listened yet", () => {
    const db = memoryDb();
    saveSong(db, song("a"), NIGHT);
    expect(streaks(db, NIGHT)).toEqual([0, 0]);
    for (const d of [1, 2, 3, 6, 7]) play(db, "a", dayStart(NIGHT) - d * DAY + 3600);
    expect(streaks(db, NIGHT)).toEqual([3, 3]);
    expect(streaks(db, NIGHT + 2 * DAY)).toEqual([0, 3]);
  });

  it("names hours", () => {
    expect([hourName(0), hourName(12), hourName(23)]).toEqual(["12 AM", "12 PM", "11 PM"]);
  });
});
