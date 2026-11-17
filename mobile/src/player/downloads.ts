/**
 * Downloads: a song's audio saved in the app's own folder, so it plays with no
 * signal. The song's details, cover link and lyrics are already in the
 * database, so the file is all that's missing. One at a time, in order.
 */
import { Directory, File, Paths } from "expo-file-system";
import { useSyncExternalStore } from "react";
import { saveSong, type Song } from "../core/db";
import { getDb, now } from "../core/store";
import { addSignal, SIGNAL } from "../core/taste";
import { log } from "../core/log";
import { yt } from "../youtube";
import { STREAM_UA } from "../youtube/ytmusic";

const subs = new Set<() => void>();
let version = 0;
const changed = () => { version++; subs.forEach((f) => f()); };
/** Re-renders when any download changes state. */
export function useDownloads(): number {
  return useSyncExternalStore((f) => (subs.add(f), () => subs.delete(f)), () => version);
}

function dir(): Directory {
  const d = new Directory(Paths.document, "music");
  if (!d.exists) d.create({ intermediates: true, idempotent: true });
  return d;
}

/** The file to play for a song, if it's on the phone. */
export function localFile(id: string): string | null {
  const row = getDb().getFirstSync<{ path: string | null }>("SELECT path FROM download WHERE song_id = ? AND state = 'done'", id);
  if (!row?.path) return null;
  return new File(row.path).exists ? row.path : null;
}

export function downloadState(id: string): "queued" | "running" | "done" | "failed" | null {
  return getDb().getFirstSync<{ state: "queued" | "running" | "done" | "failed" }>("SELECT state FROM download WHERE song_id = ?", id)?.state ?? null;
}

let busy = false;

export function download(s: Song): void {
  const db = getDb();
  saveSong(db, s, now());
  db.runSync("INSERT INTO download(song_id, state, at) VALUES (?, 'queued', ?) ON CONFLICT(song_id) DO UPDATE SET state = 'queued'",
    s.id, now());
  addSignal(db, s.id, SIGNAL.downloaded, now());
  changed();
  void work();
}

async function work() {
  if (busy) return;
  busy = true;
  const db = getDb();
  try {
    for (;;) {
      const job = db.getFirstSync<{ song_id: string }>("SELECT song_id FROM download WHERE state = 'queued' ORDER BY at LIMIT 1");
      if (!job) break;
      db.runSync("UPDATE download SET state = 'running' WHERE song_id = ?", job.song_id);
      changed();
      try {
        const st = await yt.stream(job.song_id);
        const ext = st.mime.includes("webm") ? "webm" : "m4a";
        const target = new File(dir(), `${job.song_id}.${ext}`);
        if (target.exists) target.delete();
        const f = await File.downloadFileAsync(st.url, target, { headers: { "user-agent": STREAM_UA } });
        db.runSync("UPDATE download SET state = 'done', path = ?, bytes = ?, done_bytes = ? WHERE song_id = ?",
          f.uri, f.size ?? 0, f.size ?? 0, job.song_id);
      } catch (e) {
        log("download failed", job.song_id, e);
        db.runSync("UPDATE download SET state = 'failed' WHERE song_id = ?", job.song_id);
      }
      changed();
    }
  } finally {
    busy = false;
  }
}

/** Resumes downloads left queued or half-done when the app was closed. */
export function resumeDownloads(): void {
  getDb().runSync("UPDATE download SET state = 'queued' WHERE state = 'running'");
  void work();
}

export function removeDownload(id: string): void {
  const db = getDb();
  const row = db.getFirstSync<{ path: string | null }>("SELECT path FROM download WHERE song_id = ?", id);
  if (row?.path) {
    const f = new File(row.path);
    if (f.exists) f.delete();
  }
  db.runSync("DELETE FROM download WHERE song_id = ?", id);
  changed();
}

export function storageUsed(): { bytes: number; songs: number } {
  const r = getDb().getFirstSync<{ b: number; n: number }>("SELECT coalesce(sum(bytes), 0) AS b, count(*) AS n FROM download WHERE state = 'done'");
  return { bytes: r?.b ?? 0, songs: r?.n ?? 0 };
}
