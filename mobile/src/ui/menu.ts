import { Alert } from "react-native";
import type { Song } from "../core/db";
import { getDb, now } from "../core/store";
import { hide, like } from "../core/taste";
import { download, downloadState, removeDownload } from "../player/downloads";
import { playNext } from "../player/player";

/** Long-press on a song: what you can do with it. */
export function songMenu(song: Song): void {
  const db = getDb();
  const liked = !!db.getFirstSync("SELECT 1 FROM liked WHERE song_id = ?", song.id);
  const saved = downloadState(song.id) === "done";
  Alert.alert(song.title, song.artist_name, [
    { text: "Play next", onPress: () => playNext(song) },
    { text: liked ? "Unlike" : "Like", onPress: () => like(db, song.id, !liked, now()) },
    saved ? { text: "Remove from phone", style: "destructive", onPress: () => removeDownload(song.id) }
      : { text: "Download", onPress: () => download(song) },
    { text: "Not interested", style: "destructive", onPress: () => hide(db, "song", song.id, now()) },
    { text: "Cancel", style: "cancel" },
  ]);
}
