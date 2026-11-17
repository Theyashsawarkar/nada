# nāda for Android

The phone side of nāda: YouTube Music with no account. History, likes,
playlists and taste live in one SQLite file on the phone, and the home feed
is learned from them on the phone. Expo + React Native, the same toolchain
as Vāgdevī.

## What's here

- `src/app/`: the screens (expo-router). Home, Search, Library and Insights
  are tabs under a glass tab bar with the mini player; Now playing, Lyrics
  and Up next open over them.
- `src/core/db.ts`: the schema (numbered migrations), saving songs, search
  on the phone (FTS5, ranked by taste). Its `Sql` type is expo-sqlite's
  synchronous API, so tests run the same SQL on node:sqlite.
- `src/core/taste.ts`: the taste model. Each finished, replayed, liked,
  downloaded, searched or skipped song is a signal; scores halve every 21
  days, are kept per song and per artist, and each song has a 24-hour
  profile of when it's played.
- `src/core/feed.ts`: Home (For you, More like, Jump back in, Rediscover,
  Offline ready), every row with its "because…", and smart playlists.
- `src/core/insights.ts`: minutes, week-on-week change, streaks, the
  listening clock, top artist, moods.
- `src/player/`: the player (expo-audio, background and lock screen; a
  queue that keeps going with YouTube Music's "up next"; every play that
  ends teaches the taste model) and downloads (saved in the app's folder,
  played with no signal).
- `src/youtube/`: the only code that talks to the network, behind the
  `MusicSource` interface. `ytmusic.ts` asks YouTube Music the way its
  website does (search, up next, lyrics, suggestions) and gets audio links
  the way YouTube's iPhone app does. **That is against YouTube's terms** and
  YouTube changes it now and then; parsing is pure and tested on saved
  answers (`test/fixtures`), and `pnpm live` checks it against YouTube.

```sh
pnpm install
pnpm test          # no network
pnpm typecheck
pnpm live          # asks YouTube for real: search, up next, lyrics, audio
```

## Build and install

```sh
npx expo prebuild --platform android
cd android && ./gradlew assembleRelease
adb install -r app/build/outputs/apk/release/app-release.apk
```

## Not yet

- Home-screen widgets and the lock-screen line from the design (the lock
  screen already shows the player's own controls).
- Synced lyrics: YouTube Music gives plain lyrics to this kind of request.
- Albums, artists and playlists from YouTube; search finds songs.
- The "Week / Year" switch and the yearly summary in Insights.
- A permanent signing key for releases (this build is signed with the debug key).
