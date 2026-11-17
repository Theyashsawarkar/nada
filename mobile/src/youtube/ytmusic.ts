/**
 * YouTube Music, asked the way its website asks (InnerTube, no login), and
 * audio links the way YouTube's iPhone app gets them (direct URLs, no
 * signature to decipher). This is not a public API and it is against
 * YouTube's terms; it changes now and then, so everything that knows its
 * shape is in this one file, and parsing is pure functions tested on saved
 * answers (test/fixtures).
 */
import type { Song } from "../core/db";
import { Offline, type Lyrics, type MusicSource, type SearchResults, type Stream } from "./source";

const MUSIC = "https://music.youtube.com/youtubei/v1";
const WWW = "https://www.youtube.com/youtubei/v1";
const WEB_REMIX = { clientName: "WEB_REMIX", clientVersion: "1.20251020.01.00", hl: "en", gl: "IN" };
const WEB_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";
const IOS = {
  clientName: "IOS", clientVersion: "20.10.4", deviceMake: "Apple", deviceModel: "iPhone16,2",
  osName: "iPhone", osVersion: "18.3.2.22D82", hl: "en", gl: "IN",
};
const IOS_UA = "com.google.ios.youtube/20.10.4 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)";
/** Search filter: songs only. */
const SONGS = "EgWKAQIIAWoKEAkQBRAKEAMQBA%3D%3D";

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any

// ===================================================================== parsing
const text = (t: J): string => (t?.runs ?? []).map((r: J) => r.text).join("") || t?.simpleText || "";

/** "7:51" or "1:02:03" to milliseconds. */
export function durationMs(s: string): number {
  const m = s.trim().match(/^(?:(\d+):)?(\d+):(\d{2})$/);
  if (!m) return 0;
  return ((+(m[1] ?? 0) * 60 + +m[2]!) * 60 + +m[3]!) * 1000;
}

/** The largest thumbnail, asked for at `size` px where Google's image server allows it. */
export function cover(thumbs: J[] | undefined, size = 544): string | null {
  const t = thumbs?.[thumbs.length - 1]?.url as string | undefined;
  if (!t) return null;
  if (/googleusercontent\.com|ggpht\.com/.test(t)) return t.replace(/=w\d+-h\d+[^&?]*$/, `=w${size}-h${size}-l90-rj`);
  return t;
}

const pageType = (r: J): string | undefined =>
  r?.navigationEndpoint?.browseEndpoint?.browseEndpointContextSupportedConfigs?.browseEndpointContextMusicConfig?.pageType;

/** Artists, album and duration from a byline's runs ("A, B & C • Album • 7:51"). */
function byline(runs: J[]): { artists: { id: string | null; name: string }[]; album: { id: string; title: string } | null; duration: number } {
  const parts: J[][] = [[]];
  for (const r of runs) {
    if (r.text === " • ") parts.push([]);
    else parts[parts.length - 1]!.push(r);
  }
  const artists: { id: string | null; name: string }[] = [];
  let album: { id: string; title: string } | null = null;
  let duration = 0;
  for (const [i, part] of parts.entries()) {
    const linked = part.filter((r) => pageType(r) === "MUSIC_PAGE_TYPE_ARTIST" || pageType(r) === "MUSIC_PAGE_TYPE_USER_CHANNEL");
    const al = part.find((r) => pageType(r) === "MUSIC_PAGE_TYPE_ALBUM");
    const joined = part.map((r) => r.text).join("");
    if (al) album = { id: al.navigationEndpoint.browseEndpoint.browseId, title: al.text };
    else if (linked.length) linked.forEach((r) => artists.push({ id: r.navigationEndpoint.browseEndpoint.browseId, name: r.text }));
    else if (durationMs(joined)) duration = durationMs(joined);
    else if (i === 0 && joined && !/^(Song|Video)$/.test(joined)) {
      // unlinked artist names ("A, B & C")
      joined.split(/, | & /).forEach((name) => artists.push({ id: null, name }));
    }
  }
  return { artists, album, duration };
}

function toSong(id: string, title: string, b: ReturnType<typeof byline>, thumbs: J[] | undefined): Song {
  const first = b.artists[0];
  return {
    id, title,
    artist_id: first?.id ?? (first ? `name:${first.name.toLowerCase()}` : null),
    artist_name: b.artists.map((a) => a.name).join(" · ") || "Unknown artist",
    album_id: b.album?.id ?? null,
    duration_ms: b.duration,
    cover_url: cover(thumbs),
  };
}

/** Songs from a search answer (the "Songs" shelf). */
export function parseSearch(j: J): SearchResults {
  const sections: J[] = j?.contents?.tabbedSearchResultsRenderer?.tabs?.[0]?.tabRenderer?.content?.sectionListRenderer?.contents ?? [];
  const songs: Song[] = [];
  for (const sec of sections) {
    for (const item of sec.musicShelfRenderer?.contents ?? []) {
      const r = item.musicResponsiveListItemRenderer;
      const id = r?.playlistItemData?.videoId;
      if (!id) continue;
      const cols = (r.flexColumns ?? []).map((c: J) => c.musicResponsiveListItemFlexColumnRenderer?.text);
      songs.push(toSong(id, text(cols[0]), byline(cols[1]?.runs ?? []), r.thumbnail?.musicThumbnailRenderer?.thumbnail?.thumbnails));
    }
  }
  return { songs, albums: [], artists: [], playlists: [] };
}

/** The "up next" queue: the song itself first, then YouTube Music's radio for it. */
export function parseNext(j: J): Song[] {
  const tabs: J[] = j?.contents?.singleColumnMusicWatchNextResultsRenderer?.tabbedRenderer?.watchNextTabbedResultsRenderer?.tabs ?? [];
  const items: J[] = tabs[0]?.tabRenderer?.content?.musicQueueRenderer?.content?.playlistPanelRenderer?.contents ?? [];
  const out: Song[] = [];
  for (const it of items) {
    const v = it.playlistPanelVideoRenderer ?? it.playlistPanelVideoWrapperRenderer?.primaryRenderer?.playlistPanelVideoRenderer;
    if (!v?.videoId) continue;
    const b = byline(v.longBylineText?.runs ?? []);
    b.duration = durationMs(text(v.lengthText));
    out.push(toSong(v.videoId, text(v.title), b, v.thumbnail?.thumbnails));
  }
  return out;
}

/** The lyrics page's id, from an "up next" answer. */
export function lyricsBrowseId(j: J): string | null {
  const tabs: J[] = j?.contents?.singleColumnMusicWatchNextResultsRenderer?.tabbedRenderer?.watchNextTabbedResultsRenderer?.tabs ?? [];
  for (const t of tabs) {
    const id = t.tabRenderer?.endpoint?.browseEndpoint?.browseId as string | undefined;
    if (id?.startsWith("MPLY")) return id;
  }
  return null;
}

export function parseLyrics(j: J): Lyrics | null {
  const shelf = j?.contents?.sectionListRenderer?.contents?.find((c: J) => c.musicDescriptionShelfRenderer)?.musicDescriptionShelfRenderer;
  const plain = text(shelf?.description);
  if (!plain) return null;
  return { synced: null, plain, source: text(shelf.footer).replace(/^Source:\s*/, "") || "YouTube Music" };
}

export function parseSuggest(j: J): string[] {
  const out: string[] = [];
  for (const sec of j?.contents ?? []) {
    for (const c of sec.searchSuggestionsSectionRenderer?.contents ?? []) {
      const q = c.searchSuggestionRenderer?.navigationEndpoint?.searchEndpoint?.query;
      if (q) out.push(q);
    }
  }
  return out;
}

/** The best audio YouTube gives: never a lower-quality fallback. Of the audio
 *  formats, it skips the loudness-squashed ("DRC") copies and dubbed tracks,
 *  then takes Opus (better than AAC at the same bitrate), then the highest
 *  bitrate. */
export function parseStream(j: J, now = Date.now() / 1000): Stream {
  const status = j?.playabilityStatus?.status;
  if (status !== "OK") throw new Error(j?.playabilityStatus?.reason || `not playable (${status ?? "no answer"})`);
  let audio = (j.streamingData?.adaptiveFormats ?? []).filter((f: J) => f.url && String(f.mimeType).startsWith("audio/"));
  if (!audio.length) throw new Error("no audio link in the answer");
  const drc = (f: J) => f.isDrc === true || /drc/.test(String(f.xtags ?? "")) || /drc/i.test(String(f.audioTrack?.id ?? ""));
  const dubbed = (f: J) => f.audioTrack && f.audioTrack.audioIsDefault === false;
  const clean = audio.filter((f: J) => !drc(f) && !dubbed(f));
  if (clean.length) audio = clean;
  const opus = (f: J) => +String(f.mimeType).includes("opus");
  audio.sort((a: J, b: J) => opus(b) - opus(a) || b.bitrate - a.bitrate);
  const f = audio[0];
  const exp = Number(new URL(f.url).searchParams.get("expire")) || now + 5 * 3600;
  return { url: f.url, mime: f.mimeType, bitrate: f.bitrate, bytes: Number(f.contentLength) || 0, expiresAt: exp };
}

// ===================================================================== network
async function post(url: string, body: object, ua: string, extra: Record<string, string> = {}): Promise<J> {
  let r: Response;
  try {
    r = await fetch(`${url}?prettyPrint=false`, {
      method: "POST",
      headers: { "content-type": "application/json", "user-agent": ua, ...extra },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new Offline(String(e));
  }
  if (!r.ok) throw new Error(`YouTube answered ${r.status}`);
  return r.json();
}

const music = (ep: string, body: object) =>
  post(`${MUSIC}/${ep}`, { context: { client: WEB_REMIX }, ...body }, WEB_UA, { origin: "https://music.youtube.com" });

export class YouTubeMusic implements MusicSource {
  async search(q: string): Promise<SearchResults> {
    return parseSearch(await music("search", { query: q, params: SONGS }));
  }
  async suggest(q: string): Promise<string[]> {
    return parseSuggest(await music("music/get_search_suggestions", { input: q }));
  }
  private next(id: string) {
    return music("next", { videoId: id, playlistId: `RDAMVM${id}`, isAudioOnly: true });
  }
  async song(id: string): Promise<Song> {
    const s = parseNext(await this.next(id)).find((x) => x.id === id);
    if (!s) throw new Error("song not found");
    return s;
  }
  async related(id: string): Promise<Song[]> {
    return parseNext(await this.next(id)).filter((s) => s.id !== id);
  }
  async album(): Promise<{ title: string; songs: Song[] }> {
    throw new Error("albums aren't in this version yet");
  }
  async playlist(): Promise<{ title: string; songs: Song[] }> {
    throw new Error("playlists from YouTube aren't in this version yet");
  }
  async lyrics(id: string): Promise<Lyrics | null> {
    const browse = lyricsBrowseId(await this.next(id));
    return browse ? parseLyrics(await music("browse", { browseId: browse })) : null;
  }
  async stream(id: string): Promise<Stream> {
    const j = await post(`${WWW}/player`, { context: { client: IOS }, videoId: id, contentCheckOk: true, racyCheckOk: true }, IOS_UA);
    return parseStream(j);
  }
}

/** The user agent audio links must be fetched with. */
export const STREAM_UA = IOS_UA;
