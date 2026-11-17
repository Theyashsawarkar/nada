/**
 * The database: one SQLite file on the phone (nada.db) holding everything
 * nāda knows. There is no account and no server, so this file *is* your
 * history, likes, playlists and taste. Export it to move to a new phone.
 *
 * `Sql` is the part of expo-sqlite's synchronous API we use, so the phone's
 * `openDatabaseSync("nada.db")` fits it as is; tests use node:sqlite.
 */

export type Param = string | number | null;

export interface Sql {
  execSync(sql: string): void;
  runSync(sql: string, ...params: Param[]): { changes: number; lastInsertRowId: number };
  getAllSync<T>(sql: string, ...params: Param[]): T[];
  getFirstSync<T>(sql: string, ...params: Param[]): T | null;
}

/** Numbered migrations: append, never edit one that has shipped. */
export const MIGRATIONS: string[] = [
  /* 1: the first schema */ `
  CREATE TABLE artist (
    id TEXT PRIMARY KEY,            -- YouTube Music channel id, or "name:<lowercased name>"
    name TEXT NOT NULL,
    image_url TEXT,
    fetched_at INTEGER
  );
  CREATE TABLE album (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    artist_id TEXT,
    year INTEGER,
    cover_url TEXT
  );
  CREATE TABLE song (
    id TEXT PRIMARY KEY,            -- the YouTube video id
    title TEXT NOT NULL,
    artist_id TEXT,
    artist_name TEXT NOT NULL,      -- every artist, as shown ("Mira Sen · Kabir Dhun")
    album_id TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    year INTEGER,
    genre TEXT,                     -- YouTube Music's own, when it gives one
    cover_url TEXT,
    explicit INTEGER NOT NULL DEFAULT 0,
    fetched_at INTEGER
  );
  CREATE INDEX song_artist ON song(artist_id);
  CREATE VIRTUAL TABLE song_fts USING fts5(title, artist_name, content='song', content_rowid='rowid',
                                           tokenize='unicode61 remove_diacritics 2');
  CREATE TRIGGER song_ai AFTER INSERT ON song BEGIN
    INSERT INTO song_fts(rowid, title, artist_name) VALUES (new.rowid, new.title, new.artist_name);
  END;
  CREATE TRIGGER song_ad AFTER DELETE ON song BEGIN
    INSERT INTO song_fts(song_fts, rowid, title, artist_name) VALUES ('delete', old.rowid, old.title, old.artist_name);
  END;
  CREATE TRIGGER song_au AFTER UPDATE ON song BEGIN
    INSERT INTO song_fts(song_fts, rowid, title, artist_name) VALUES ('delete', old.rowid, old.title, old.artist_name);
    INSERT INTO song_fts(rowid, title, artist_name) VALUES (new.rowid, new.title, new.artist_name);
  END;

  CREATE TABLE play (
    id INTEGER PRIMARY KEY,
    song_id TEXT NOT NULL,
    started_at INTEGER NOT NULL,    -- unix seconds
    listened_ms INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,   -- past 80% of the song
    skipped INTEGER NOT NULL DEFAULT 0,     -- left within its first 30 s
    source TEXT NOT NULL DEFAULT 'other',   -- search | mix | radio | playlist | album | widget | other
    offline INTEGER NOT NULL DEFAULT 0
  );
  CREATE INDEX play_song ON play(song_id, started_at);
  CREATE INDEX play_time ON play(started_at);

  CREATE TABLE liked (song_id TEXT PRIMARY KEY, at INTEGER NOT NULL);
  CREATE TABLE hidden (kind TEXT NOT NULL, id TEXT NOT NULL, at INTEGER NOT NULL, PRIMARY KEY (kind, id));
  CREATE TABLE playlist (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    smart TEXT,                     -- the name of a smart rule (see feed.ts), else a plain list
    created_at INTEGER NOT NULL
  );
  CREATE TABLE playlist_song (playlist_id INTEGER NOT NULL, song_id TEXT NOT NULL, pos REAL NOT NULL,
                              PRIMARY KEY (playlist_id, song_id));
  CREATE TABLE download (
    song_id TEXT PRIMARY KEY,
    path TEXT,
    bytes INTEGER NOT NULL DEFAULT 0,
    done_bytes INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'queued',   -- queued | running | done | failed
    at INTEGER NOT NULL
  );
  CREATE TABLE lyrics (song_id TEXT PRIMARY KEY, synced TEXT, plain TEXT, source TEXT, offset_ms INTEGER NOT NULL DEFAULT 0,
                       fetched_at INTEGER NOT NULL);
  CREATE TABLE search (id INTEGER PRIMARY KEY, q TEXT NOT NULL, at INTEGER NOT NULL, picked_song_id TEXT);
  CREATE TABLE related (song_id TEXT NOT NULL, related_id TEXT NOT NULL, rank INTEGER NOT NULL, fetched_at INTEGER NOT NULL,
                        PRIMARY KEY (song_id, related_id));

  -- the taste model: kept up to date as plays end, never recomputed (taste.ts)
  CREATE TABLE taste_song (
    song_id TEXT PRIMARY KEY,
    score REAL NOT NULL DEFAULT 0,  -- as of updated_at; it halves every HALF_LIFE
    updated_at INTEGER NOT NULL,
    hours TEXT NOT NULL DEFAULT '[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]',
    plays INTEGER NOT NULL DEFAULT 0,
    last_played INTEGER
  );
  CREATE TABLE taste_artist (
    artist_id TEXT PRIMARY KEY,
    score REAL NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL,
    last_played INTEGER
  );
  CREATE TABLE setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
  `,
];

/** Brings the database up to date. Safe to call on every start. */
export function migrate(db: Sql): number {
  db.execSync("PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;");
  const v = db.getFirstSync<{ user_version: number }>("PRAGMA user_version")?.user_version ?? 0;
  for (let i = v; i < MIGRATIONS.length; i++) {
    db.execSync("BEGIN");
    try {
      db.execSync(MIGRATIONS[i]!);
      db.execSync(`PRAGMA user_version = ${i + 1}`);
      db.execSync("COMMIT");
    } catch (e) {
      db.execSync("ROLLBACK");
      throw e;
    }
  }
  return MIGRATIONS.length;
}

export type Song = {
  id: string;
  title: string;
  artist_id: string | null;
  artist_name: string;
  album_id?: string | null;
  duration_ms: number;
  year?: number | null;
  genre?: string | null;
  cover_url?: string | null;
  explicit?: number;
};

/** Keeps what YouTube Music said about a song (first sight, or fresher details). */
export function saveSong(db: Sql, s: Song, now: number): void {
  if (s.artist_id) {
    db.runSync("INSERT INTO artist(id, name, fetched_at) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET name = excluded.name",
      s.artist_id, s.artist_name.split(" · ")[0] ?? s.artist_name, now);
  }
  db.runSync(
    `INSERT INTO song(id, title, artist_id, artist_name, album_id, duration_ms, year, genre, cover_url, explicit, fetched_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET title = excluded.title, artist_id = excluded.artist_id, artist_name = excluded.artist_name,
       album_id = coalesce(excluded.album_id, album_id), duration_ms = excluded.duration_ms, year = coalesce(excluded.year, year),
       genre = coalesce(excluded.genre, genre), cover_url = coalesce(excluded.cover_url, cover_url), fetched_at = excluded.fetched_at`,
    s.id, s.title, s.artist_id, s.artist_name, s.album_id ?? null, s.duration_ms, s.year ?? null, s.genre ?? null,
    s.cover_url ?? null, s.explicit ?? 0, now);
}

/** Your songs that match what's typed, best first: ones you've played, liked or
 *  downloaded (not every search result the phone has seen), full-text matched
 *  and ranked up by how much you like them. Works with no network. */
export function searchLocal(db: Sql, q: string, limit = 20): (Song & { score: number })[] {
  const terms = q.toLowerCase().match(/[\p{L}\p{N}]+/gu);
  if (!terms) return [];
  const match = terms.map((t) => `"${t}"*`).join(" ");
  return db.getAllSync<Song & { score: number }>(
    `SELECT s.*, coalesce(t.score, 0) AS score FROM song_fts f JOIN song s ON s.rowid = f.rowid
     LEFT JOIN taste_song t ON t.song_id = s.id
     WHERE song_fts MATCH ? AND s.id NOT IN (SELECT id FROM hidden WHERE kind = 'song')
       AND (s.id IN (SELECT song_id FROM play) OR s.id IN (SELECT song_id FROM liked)
            OR s.id IN (SELECT song_id FROM download WHERE state = 'done'))
     ORDER BY bm25(song_fts) - min(coalesce(t.score, 0), 20) * 0.25 LIMIT ?`, match, limit);
}
