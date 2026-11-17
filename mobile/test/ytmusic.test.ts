import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { cover, durationMs, lyricsBrowseId, parseLyrics, parseNext, parseSearch, parseStream, parseSuggest } from "../src/youtube/ytmusic";

const fx = (n: string) => JSON.parse(readFileSync(new URL(`./fixtures/${n}.json`, import.meta.url), "utf8"));

describe("YouTube Music answers", () => {
  it("reads songs from a search, with every artist, the album and the length", () => {
    const { songs } = parseSearch(fx("search-songs"));
    expect(songs.length).toBeGreaterThanOrEqual(3);
    expect(songs[0]).toMatchObject({
      id: "_fmA1RoHbzA", title: "Kun Faya Kun", artist_id: "UCtJe0RYzgPddQXKtWduxz_w",
      artist_name: "A.R. Rahman · Javed Ali · Mohit Chauhan", album_id: "MPREb_E9Diy6kXmlV", duration_ms: 471_000,
    });
    expect(songs[0]!.cover_url).toMatch(/=w544-h544-l90-rj$/);
  });

  it("reads the up-next radio, the song itself first", () => {
    const q = parseNext(fx("next"));
    expect(q.length).toBeGreaterThanOrEqual(5);
    expect(q[1]).toMatchObject({ id: "9JDSGhhiOwI", title: "Tere Bina", duration_ms: 289_000 });
    expect(q[1]!.artist_name.split(" · ")[0]).toBe("A. R. Rahman");
    expect(new Set(q.map((s) => s.id)).size).toBe(q.length);
  });

  it("finds and reads the lyrics", () => {
    expect(lyricsBrowseId(fx("next"))).toMatch(/^MPLY/);
    expect(parseLyrics(fx("lyrics"))).toEqual({ synced: null, plain: "first line of the song\nsecond line of the song", source: "LyricFind" });
    expect(parseLyrics({})).toBeNull();
  });

  it("reads suggestions", () => {
    expect(parseSuggest(fx("suggest"))).toContain("kun faya kun");
  });

  it("picks the best audio link and knows when it expires", () => {
    const s = parseStream({
      playabilityStatus: { status: "OK" },
      streamingData: { adaptiveFormats: [
        { url: "https://x/v?expire=1900000000", mimeType: 'video/mp4; codecs="avc1"', bitrate: 9e6 },
        { url: "https://x/a?expire=1900000000", mimeType: 'audio/mp4; codecs="mp4a.40.2"', bitrate: 130000 },
        { url: "https://x/o?expire=1900000000", mimeType: 'audio/webm; codecs="opus"', bitrate: 120000 },
      ] },
    });
    expect(s).toMatchObject({ url: "https://x/o?expire=1900000000", expiresAt: 1900000000 });
    expect(() => parseStream({ playabilityStatus: { status: "LOGIN_REQUIRED", reason: "Sign in" } })).toThrow("Sign in");
    // the loudness-squashed copy and a dubbed track never win, even at a higher bitrate
    const best = parseStream({
      playabilityStatus: { status: "OK" },
      streamingData: { adaptiveFormats: [
        { url: "https://x/drc?expire=1", mimeType: 'audio/webm; codecs="opus"', bitrate: 160000, isDrc: true },
        { url: "https://x/dub?expire=1", mimeType: 'audio/webm; codecs="opus"', bitrate: 170000, audioTrack: { audioIsDefault: false } },
        { url: "https://x/aac?expire=1", mimeType: 'audio/mp4; codecs="mp4a.40.2"', bitrate: 130000 },
        { url: "https://x/best?expire=1", mimeType: 'audio/webm; codecs="opus"', bitrate: 150000, contentLength: "8476554" },
      ] },
    });
    expect(best).toMatchObject({ url: "https://x/best?expire=1", bytes: 8476554 });
  });

  it("parses lengths and covers", () => {
    expect([durationMs("7:51"), durationMs("1:02:03"), durationMs("711M plays")]).toEqual([471_000, 3_723_000, 0]);
    expect(cover([{ url: "https://lh3.googleusercontent.com/abc=w60-h60-l90-rj" }])).toBe("https://lh3.googleusercontent.com/abc=w544-h544-l90-rj");
    expect(cover(undefined)).toBeNull();
  });
});
