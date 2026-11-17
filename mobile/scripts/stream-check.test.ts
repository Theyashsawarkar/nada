// `LIVE=stream-check pnpm vitest run`: can a whole song be fetched, in pieces?
import { it } from "vitest";
import { YouTubeMusic } from "../src/youtube/ytmusic";

it("whole song in 256 KB pieces", async () => {
  const st = await new YouTubeMusic().stream("9JDSGhhiOwI");
  console.log("best:", st.mime, st.bitrate, "bytes", st.bytes);
  const piece = 256 * 1024;
  let got = 0;
  for (let at = 0; at < st.bytes; at += piece) {
    const end = Math.min(st.bytes, at + piece) - 1;
    const r = await fetch(st.url, { headers: { range: `bytes=${at}-${end}` } });
    const b = (await r.arrayBuffer()).byteLength;
    if (r.status !== 206) {
      console.log("refused at", at, "status", r.status, `after ${got} of ${st.bytes} bytes`);
      return;
    }
    got += b;
  }
  console.log("whole song fetched:", got, "of", st.bytes);
}, 110000);
