/**
 * Everything nāda needs from the network, in one place. The rest of the app
 * talks only to this interface, so the way songs are fetched can change (or
 * be fixed when YouTube changes) without touching anything else.
 *
 * No implementation yet: how the phone gets playable audio is still to be
 * decided (see mobile/README.md, "Open question").
 */
import type { Song } from "../core/db";

export type SearchResults = {
  songs: Song[];
  albums: { id: string; title: string; artist: string; year?: number; cover_url?: string }[];
  artists: { id: string; name: string; image_url?: string }[];
  playlists: { id: string; title: string; author: string; count?: number; cover_url?: string }[];
};

export type Lyrics = { synced: string | null; plain: string | null; source: string };

export type Stream = {
  url: string;
  mime: string;           // audio/webm; codecs="opus", audio/mp4...
  bitrate: number;
  bytes: number;          // the file's size, for fetching it in ranges
  expiresAt: number;      // unix seconds: links expire, so never store them
};

export interface MusicSource {
  search(q: string): Promise<SearchResults>;
  /** Live suggestions while typing. */
  suggest(q: string): Promise<string[]>;
  song(id: string): Promise<Song>;
  /** YouTube Music's "up next" for a song: kept a week in `related`. */
  related(id: string): Promise<Song[]>;
  album(id: string): Promise<{ title: string; songs: Song[] }>;
  playlist(id: string): Promise<{ title: string; songs: Song[] }>;
  lyrics(id: string): Promise<Lyrics | null>;
  /** A playable audio link, asked for just before playing or downloading. */
  stream(id: string): Promise<Stream>;
}

/** Raised when the network can't be reached: callers fall back to what's on
 *  the phone, and never remember it as "nothing found". */
export class Offline extends Error {}
