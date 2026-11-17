import { it } from "vitest";
import { YouTubeMusic, STREAM_UA } from "../src/youtube/ytmusic";
it("live", async () => {
  const yt = new YouTubeMusic();
  const r = await yt.search("tum hi ho");
  console.log("search:", r.songs.slice(0, 3).map(s => `${s.title} — ${s.artist_name} (${s.duration_ms / 1000}s)`));
  const id = r.songs[0]!.id;
  const rel = await yt.related(id);
  console.log("related:", rel.length, rel.slice(0, 3).map(s => s.title));
  console.log("suggest:", (await yt.suggest("arij")).slice(0, 3));
  const ly = await yt.lyrics(id);
  console.log("lyrics:", ly ? `${ly.plain!.split("\n").length} lines from ${ly.source}` : "none");
  const st = await yt.stream(id);
  const h = await fetch(st.url, { headers: { range: "bytes=0-99999", "user-agent": STREAM_UA } });
  console.log("stream:", st.mime, st.bitrate, "fetch", h.status, (await h.arrayBuffer()).byteLength, "bytes; expires in", Math.round((st.expiresAt - Date.now() / 1000) / 3600), "h");
}, 60000);
