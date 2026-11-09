"""Every key of the window, as data (Vyom's keys.py, vendored as keys.py):
one table that the key engine (window.py), the which-key strip, the
palette, the key sheet, the `# keybind:` lines below and the README's key
tables are all made from. Pure Python: the tests read it without GTK.

Actions are strings the window runs:
  do:<key>     the old key engine's name for it (window.dispatch), e.g. do:dd
  tab:<±1|name> switch tabs        call:<method>[:arg] a Window method
  moved:<keys> a key that moved: say where (one release, then it goes)
A "|note:<text>" tail shows <text> once a session (a key with a new job).

Change a key here, then run `python3 scripts/keybinds.py` (it rewrites the
lines below and README.md; the tests fail until you do).

The Space grammar (the same in every Vayu tool): Space t tabs, u toggles,
y copy, f find, r refresh, a add, d delete, o open outside, g go to,
Space Space palette, Space ? keys, Space q close. nāda's own groups use
free letters: p playback, l lyrics, x downloads, i info.
"""
from .keys import Bind

SOURCE = "Nada"
TABS = ["home", "queue", "library", "playlists", "downloads"]   # YouTube's results: a page, from the search panel
TAB_TITLES = {"home": "Now", "queue": "Queue", "library": "Library", "playlists": "Playlists",
              "downloads": "Downloads", "youtube": "YouTube"}
LISTS = {"queue", "playlists", "downloads"}
GROUPS = {" p": "playback", " l": "lyrics", " x": "downloads"}


def B(seq, action, desc="", hidden=False, mode="normal"):
    return Bind(seq, action, desc, mode=mode, hidden=hidden)


# (scope, the tabs it works on (None: everywhere), binds). Later sections
# win over earlier ones for the same keys, so a tab's own keys come last.
SECTIONS = [
    ("everywhere", None, [
        B("j", "do:j", "Move down a song (counts work: 5j)"),
        B("k", "do:k", "Move up a song"),
        B("<Down>", "do:j", hidden=True), B("<Up>", "do:k", hidden=True),
        B("gg", "do:gg", "Jump to the top (12gg: to the 12th)"),
        B("G", "do:G", "Jump to the bottom (12G: to the 12th)"),
        B("<C-d>", "do:C-d", "Scroll half a page down"),
        B("<C-u>", "do:C-u", "Scroll half a page up"),
        B("<PgDn>", "do:C-d", hidden=True), B("<PgUp>", "do:C-u", hidden=True),
        B("H", "tab:-1", "Switch to the previous tab (wraps around)"),
        B("L", "tab:+1|note:L is the next tab now: the lyrics are Space u l", "Switch to the next tab (wraps around)"),
        B("<C-Tab>", "tab:+1", "Switch to the next tab (also from the search box)"),
        B("<C-S-Tab>", "tab:-1", "Switch to the previous tab (also from the search box)"),
        B("<C-0>", "tab:home", "Switch to Now at once (Ctrl+1 Queue, 2 Library, 3 Playlists, 4 Downloads)"),
        B("<C-1>", "tab:queue", hidden=True), B("<C-2>", "tab:library", hidden=True),
        B("<C-3>", "tab:playlists", hidden=True), B("<C-4>", "tab:downloads", hidden=True),
        B("p", "call:toggle_play", "Toggle play / pause"),
        B("<CR>", "do:Return", "Play the selected song"),
        B(".", "do:.", "Seek forward 10 seconds (3. = 30 s)"),
        B(",", "do:,", "Seek back 10 seconds"),
        B(">", "do:>", "Play the next song"),
        B("<", "do:<", "Play the previous song"),
        B("=", "do:=", "Raise the volume"), B("+", "do:=", hidden=True),
        B("-", "do:-", "Lower the volume"),
        B("m", "do:m", "Toggle mute"),
        B("M", "do:M", "Toggle autoplay (more like this after your songs)"),
        B("V", "do:V", "Select several songs (visual mode)"),
        B("u", "do:u", "Restore the last change (undo)"),
        B("<C-r>", "do:C-r", "Restore an undone change (redo)"),
        B("D", "do:D", "Save the playing YouTube song to your music folder (download)"),
        B("r", "call:rescan", "Refresh: rescan the music folder and reload the lists"),
        B("/", "do:/", "Open the search panel (your library, YouTube, playlists, : commands, this list)"),
        B("o", "do:/", "Open the search panel to paste a YouTube link"),
        B(":", "do::", "Run a command (:w name, :sleep 30m, :yt query…)"),
        B("?", "call:keysheet", "Show every key of this tab"),
        B("z", "call:mini", "Switch to the mini player"),
        B("q", "do:q", "Close the window (the music keeps playing)"),
        B("<Esc>", "do:Escape", "Go back, or close the window"),
        B("s", "moved:Space p s", "Show where shuffle moved (Space p s; for one release)"),
        B("i", "moved:Space i", "Show where song info moved (Space i; for one release)"),
        B("0", "moved:H / L or Space t n", "Show where the tab numbers moved (H / L, Space t; for one release)"),
        # The leader
        B("  ", "call:palette", "Open the palette (every action of this tab, fuzzy)"),
        B(" ?", "call:keysheet", "Show every key of this tab"),
        B(" q", "do:q", "Close the window (the music keeps playing)"),
        B(" tn", "tab:home", "Switch to Now (the lyrics)"),
        B(" tq", "tab:queue", "Switch to the queue"),
        B(" tl", "tab:library", "Switch to the library"),
        B(" tp", "tab:playlists", "Switch to playlists"),
        B(" td", "tab:downloads", "Switch to downloads"),
        B(" ul", "call:lyrics_pane", "Toggle the lyrics on the right (Now: open the lyrics panel)"),
        B(" um", "call:mini", "Switch to the mini player"),
        B(" ps", "do:s", "Toggle shuffle"),
        B(" pr", "do:r", "Cycle repeat (off, all, this song)"),
        B(" pa", "do:M", "Toggle autoplay (more like this after your songs)"),
        B(" pz", "call:sleep", "Toggle the sleep timer (fades out in 30 min)"),
        B(" ll", "call:lyrics_panel", "Open the lyrics panel (pick a version, the script, the timing)"),
        B(" ls", "call:lyrics_script", "Switch the lyrics script: Hinglish (Latin letters) or Devanagari"),
        B(" l[", "call:lyrics_nudge:-0.25", "Show the lyrics earlier by 0.25 s (kept for the song)"),
        B(" l]", "call:lyrics_nudge:0.25", "Show the lyrics later by 0.25 s (kept for the song)"),
        B(" yy", "call:copy_song", "Copy the playing song's title and artist"),
        B(" yl", "call:copy_link", "Copy the playing song's link (YouTube) or file path"),
        B(" ff", "call:search:0", "Search everything"),
        B(" fy", "call:search:1", "Search YouTube"),
        B(" fl", "call:search:2", "Search your library"),
        B(" fp", "call:search:3", "Search your playlists"),
        B(" fc", "call:search:4", "Search the : commands"),
        B(" ft", "call:search:5", "Search this list"),
        B(" xd", "do:D", "Save the song to your music folder (download)"),
        B(" i", "do:i", "Show the song's title, artist and link"),
        B(" gp", "call:goto_playing", "Go to the song that's playing (in the queue)"),
        B(" ob", "call:open_browser", "Open the playing song on YouTube in the browser"),
        B(" r", "call:rescan", "Refresh: rescan the music folder and reload the lists"),
        B(" dc", "call:clear_queue", "Clear the queue (asks first; u brings it back)"),
    ]),
    ("queue", {"queue"}, [
        B("dd", "do:dd", "Remove the song from the queue (2dd: two; u undoes it)"),
        B("x", "do:x", "Remove the song from the queue (like dd; u undoes it)"),
        B("<Del>", "do:x", hidden=True),
        B("dG", "do:dG", "Remove every song from here to the end (u undoes it)"),
        B("yy", "do:yy", "Copy the song (yank; 3yy: three)"),
        B("gp", "do:p", "Paste removed or copied songs below"),
        B("gP", "do:P", "Paste removed or copied songs above"),
        B("P", "do:P", hidden=True),
        B("J", "do:J", "Move the song down"),
        B("K", "do:K", "Move the song up"),
        B("A", "do:A", "Move the song to play next"),
        B("D", "do:D", "Save the YouTube song to your music folder (download; V: the selection)"),
        B("n", "do:n", "Jump to the next match (after a \"This list\" search)"),
        B("N", "do:N", "Jump to the previous match"),
        B(" dd", "do:dd", "Remove the song from the queue (u undoes it)"),
    ]),
    ("library", {"library"}, [
        B("h", "do:h", "Move to the column on the left"),
        B("l", "do:l", "Move to the column on the right"),
        B("<Left>", "do:h", hidden=True), B("<Right>", "do:l", hidden=True),
        B("<Tab>", "do:Tab", "Switch between artists, albums, genres and folders"),
        B("<CR>", "do:Return", "Play the artist, album or song (replaces the queue)"),
        B("a", "do:a", "Add to the end of the queue"),
        B("A", "do:A", "Add to play next"),
        B(" aa", "do:a", "Add to the end of the queue"),
        B(" an", "do:A", "Add to play next"),
    ]),
    ("youtube", {"youtube"}, [
        B("<CR>", "do:Return", "Play the result"),
        B("a", "do:a", "Add the result to the end of the queue"),
        B("A", "do:A", "Add the result to play next"),
        B("D", "do:D", "Save the result to your music folder (download)"),
        B(" aa", "do:a", "Add the result to the end of the queue"),
        B(" an", "do:A", "Add the result to play next"),
    ]),
    ("playlists", {"playlists"}, [
        B("h", "do:h", "Move to the playlists"),
        B("l", "do:l", "Move to the playlist's songs"),
        B("<Left>", "do:h", hidden=True), B("<Right>", "do:l", hidden=True),
        B("<CR>", "do:Return", "Play the playlist (replaces the queue)"),
        B("a", "do:a", "Add the playlist to the end of the queue"),
        B("A", "do:A", "Add the playlist to play next"),
        B("dd", "do:dd", "Delete the playlist (asks first)"),
        B("D", "do:D", "Save the playlist's YouTube songs to your music folder (download)"),
        B(" aa", "do:a", "Add the playlist to the end of the queue"),
        B(" an", "do:A", "Add the playlist to play next"),
        B(" dd", "do:dd", "Delete the playlist (asks first)"),
    ]),
    ("downloads", {"downloads"}, [
        B("<CR>", "do:Return", "Play the saved song"),
        B("R", "do:R", "Retry a failed download"),
        B("dd", "do:dd", "Delete the saved file (asks first)"),
        B(" xr", "do:R", "Retry a failed download"),
        B(" dd", "do:dd", "Delete the saved file (asks first)"),
    ]),
    ("now", {"home"}, [
        B("<CR>", "call:toggle_play", "Toggle play / pause"),
    ]),
]

# Visual mode (V in a list): the motions above, and these act on the selection.
VISUAL = [
    ("queue", {"queue"}, [
        B("d", "do:dd", "Remove the selected songs (u undoes it)", mode="visual"),
        B("x", "do:dd", "Remove the selected songs (like d; u undoes it)", mode="visual"),
        B("y", "do:yy", "Copy the selected songs (yank)", mode="visual"),
        B("D", "do:D", "Save the selected YouTube songs (download)", mode="visual"),
        B("V", "do:V", "Leave visual mode", mode="visual"),
        B("<Esc>", "do:Escape", "Leave visual mode", mode="visual"),
    ]),
    ("youtube", {"youtube"}, [
        B("a", "do:a", "Add the selected results to the end of the queue", mode="visual"),
        B("A", "do:A", "Add the selected results to play next", mode="visual"),
        B("D", "do:D", "Save the selected results (download)", mode="visual"),
        B("V", "do:V", "Leave visual mode", mode="visual"),
        B("<Esc>", "do:Escape", "Leave visual mode", mode="visual"),
    ]),
]

# Panels with keys of their own (they take every key while open): listed
# for the key sheet, the README and the keybinding search only.
PANELS = [
    ("lyrics panel", "normal", [
        B("j", None, "Move down through the versions the sources have"),
        B("k", None, "Move up through the versions"),
        B("<CR>", None, "Use these lyrics (kept for the song)"),
        B("s", None, "Switch the script: Hinglish (Latin letters) or Devanagari"),
        B("[", None, "Show the lyrics earlier by 0.25 s (kept for the song)"),
        B("]", None, "Show the lyrics later by 0.25 s (kept for the song)"),
        B("<Esc>", None, "Close the lyrics panel (q too)"),
    ]),
    ("search", "insert", [
        B("<Tab>", None, "Switch where to look (all, YouTube, library, playlists, commands, this list)"),
        B("<S-Tab>", None, "Switch back where to look"),
        B("<C-j>", None, "Move down through the results while typing"),
        B("<C-k>", None, "Move up through the results while typing"),
        B("<CR>", None, "Play the result (a playlist: replace the queue; a command: run it)"),
        B("<C-CR>", None, "Play the result next"),
        B("<S-CR>", None, "Add the result to the end of the queue"),
        B("<C-d>", None, "Download the result (YouTube)"),
        B("<C-u>", None, "Clear the search box"),
        B("<C-x>", None, "Clear recent searches"),
        B("<Esc>", None, "Close the search panel"),
    ]),
    ("palette", "insert", [
        B("<C-j>", None, "Move down through the actions (Down too)"),
        B("<C-k>", None, "Move up through the actions (Up too)"),
        B("<CR>", None, "Run the action"),
        B("<Esc>", None, "Close the palette"),
    ]),
    ("leader", "normal", [
        B("<Esc>", None, "Cancel a pending key or count (Space, g, d…)"),
    ]),
]

COMMANDS = ":w <name> save the queue · :e <name> load a playlist · :yt <search> · :play <search> · :sleep 30m · " \
           ":vol 40 · :seek 1:30 · :lyrics <search> · :autoplay on/off · :clear · :dl · :q · :qa"


def _with_when(sections):
    out = []
    for _scope, tabs, bs in sections:
        for b in bs:
            b.when = tabs
            out.append(b)
    return out


ALL = _with_when(SECTIONS)
ALL_VISUAL = _with_when(VISUAL)


def binds_for(tab, visual=False):
    """The binds that work on this tab right now (later ones win)."""
    out = [b for b in ALL if b.applies("normal", tab)]
    if visual:
        # d and y act at once on a selection: no dd / yy / dG waiting
        out = [b for b in out if not (len(b.seq) > 1 and b.seq[0] in "dy")]
        out += [b for b in ALL_VISUAL if b.applies("visual", tab)]
    return out


def where(tab):
    return TAB_TITLES.get(tab, tab)


# ------------------------------------------------------------- generated docs
def _spell_sections():
    from .keys import spell
    for scope, _tabs, bs in SECTIONS:
        yield scope, "normal", [(spell(b.seq), b.desc) for b in bs if not b.hidden and b.desc]
    for scope, _tabs, bs in VISUAL:
        yield f"{scope} visual", "visual", [(spell(b.seq), b.desc) for b in bs if not b.hidden and b.desc]
    for scope, mode, bs in PANELS:
        yield scope, mode, [(spell(b.seq), b.desc) for b in bs if not b.hidden and b.desc]


def annotation_lines():
    lines = []
    for scope, mode, rows in _spell_sections():
        base = scope.replace(" visual", "")
        for k, d in rows:
            lines.append(f"# keybind: {SOURCE}/{base}:{mode} | {k} | {d}")
    for prefix, name in sorted(GROUPS.items()):
        from .keys import spell
        lines.append(f"# keybind-group: {SOURCE}/everywhere | {spell(prefix)} | {name.capitalize()}")
    return lines


def readme_tables():
    titles = {"everywhere": "Everywhere", "queue": "Queue", "library": "Library", "youtube": "YouTube results",
              "playlists": "Playlists", "downloads": "Downloads", "now": "Now", "queue visual": "Queue, visual mode (V)",
              "youtube visual": "YouTube results, visual mode (V)", "lyrics panel": "Lyrics panel (Space l l)",
              "search": "Search panel (/)", "palette": "Palette (Space Space)", "leader": "While a key waits"}
    out = []
    for scope, _mode, rows in _spell_sections():
        out += [f"**{titles.get(scope, scope)}**", "", "| Key | Action |", "|---|---|"]
        out += [f"| `{k}` | {d} |" for k, d in rows]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# --- keybind lines: generated by scripts/keybinds.py from the tables above; don't edit ---
# keybind: Nada/everywhere:normal | j | Move down a song (counts work: 5j)
# keybind: Nada/everywhere:normal | k | Move up a song
# keybind: Nada/everywhere:normal | g g | Jump to the top (12gg: to the 12th)
# keybind: Nada/everywhere:normal | G | Jump to the bottom (12G: to the 12th)
# keybind: Nada/everywhere:normal | Ctrl+d | Scroll half a page down
# keybind: Nada/everywhere:normal | Ctrl+u | Scroll half a page up
# keybind: Nada/everywhere:normal | H | Switch to the previous tab (wraps around)
# keybind: Nada/everywhere:normal | L | Switch to the next tab (wraps around)
# keybind: Nada/everywhere:normal | Ctrl+Tab | Switch to the next tab (also from the search box)
# keybind: Nada/everywhere:normal | Ctrl+Shift+Tab | Switch to the previous tab (also from the search box)
# keybind: Nada/everywhere:normal | Ctrl+0 | Switch to Now at once (Ctrl+1 Queue, 2 Library, 3 Playlists, 4 Downloads)
# keybind: Nada/everywhere:normal | p | Toggle play / pause
# keybind: Nada/everywhere:normal | Enter | Play the selected song
# keybind: Nada/everywhere:normal | . | Seek forward 10 seconds (3. = 30 s)
# keybind: Nada/everywhere:normal | , | Seek back 10 seconds
# keybind: Nada/everywhere:normal | > | Play the next song
# keybind: Nada/everywhere:normal | < | Play the previous song
# keybind: Nada/everywhere:normal | = | Raise the volume
# keybind: Nada/everywhere:normal | - | Lower the volume
# keybind: Nada/everywhere:normal | m | Toggle mute
# keybind: Nada/everywhere:normal | M | Toggle autoplay (more like this after your songs)
# keybind: Nada/everywhere:normal | V | Select several songs (visual mode)
# keybind: Nada/everywhere:normal | u | Restore the last change (undo)
# keybind: Nada/everywhere:normal | Ctrl+r | Restore an undone change (redo)
# keybind: Nada/everywhere:normal | D | Save the playing YouTube song to your music folder (download)
# keybind: Nada/everywhere:normal | r | Refresh: rescan the music folder and reload the lists
# keybind: Nada/everywhere:normal | / | Open the search panel (your library, YouTube, playlists, : commands, this list)
# keybind: Nada/everywhere:normal | o | Open the search panel to paste a YouTube link
# keybind: Nada/everywhere:normal | : | Run a command (:w name, :sleep 30m, :yt query…)
# keybind: Nada/everywhere:normal | ? | Show every key of this tab
# keybind: Nada/everywhere:normal | z | Switch to the mini player
# keybind: Nada/everywhere:normal | q | Close the window (the music keeps playing)
# keybind: Nada/everywhere:normal | Esc | Go back, or close the window
# keybind: Nada/everywhere:normal | s | Show where shuffle moved (Space p s; for one release)
# keybind: Nada/everywhere:normal | i | Show where song info moved (Space i; for one release)
# keybind: Nada/everywhere:normal | 0 | Show where the tab numbers moved (H / L, Space t; for one release)
# keybind: Nada/everywhere:normal | Space Space | Open the palette (every action of this tab, fuzzy)
# keybind: Nada/everywhere:normal | Space ? | Show every key of this tab
# keybind: Nada/everywhere:normal | Space q | Close the window (the music keeps playing)
# keybind: Nada/everywhere:normal | Space t n | Switch to Now (the lyrics)
# keybind: Nada/everywhere:normal | Space t q | Switch to the queue
# keybind: Nada/everywhere:normal | Space t l | Switch to the library
# keybind: Nada/everywhere:normal | Space t p | Switch to playlists
# keybind: Nada/everywhere:normal | Space t d | Switch to downloads
# keybind: Nada/everywhere:normal | Space u l | Toggle the lyrics on the right (Now: open the lyrics panel)
# keybind: Nada/everywhere:normal | Space u m | Switch to the mini player
# keybind: Nada/everywhere:normal | Space p s | Toggle shuffle
# keybind: Nada/everywhere:normal | Space p r | Cycle repeat (off, all, this song)
# keybind: Nada/everywhere:normal | Space p a | Toggle autoplay (more like this after your songs)
# keybind: Nada/everywhere:normal | Space p z | Toggle the sleep timer (fades out in 30 min)
# keybind: Nada/everywhere:normal | Space l l | Open the lyrics panel (pick a version, the script, the timing)
# keybind: Nada/everywhere:normal | Space l s | Switch the lyrics script: Hinglish (Latin letters) or Devanagari
# keybind: Nada/everywhere:normal | Space l [ | Show the lyrics earlier by 0.25 s (kept for the song)
# keybind: Nada/everywhere:normal | Space l ] | Show the lyrics later by 0.25 s (kept for the song)
# keybind: Nada/everywhere:normal | Space y y | Copy the playing song's title and artist
# keybind: Nada/everywhere:normal | Space y l | Copy the playing song's link (YouTube) or file path
# keybind: Nada/everywhere:normal | Space f f | Search everything
# keybind: Nada/everywhere:normal | Space f y | Search YouTube
# keybind: Nada/everywhere:normal | Space f l | Search your library
# keybind: Nada/everywhere:normal | Space f p | Search your playlists
# keybind: Nada/everywhere:normal | Space f c | Search the : commands
# keybind: Nada/everywhere:normal | Space f t | Search this list
# keybind: Nada/everywhere:normal | Space x d | Save the song to your music folder (download)
# keybind: Nada/everywhere:normal | Space i | Show the song's title, artist and link
# keybind: Nada/everywhere:normal | Space g p | Go to the song that's playing (in the queue)
# keybind: Nada/everywhere:normal | Space o b | Open the playing song on YouTube in the browser
# keybind: Nada/everywhere:normal | Space r | Refresh: rescan the music folder and reload the lists
# keybind: Nada/everywhere:normal | Space d c | Clear the queue (asks first; u brings it back)
# keybind: Nada/queue:normal | d d | Remove the song from the queue (2dd: two; u undoes it)
# keybind: Nada/queue:normal | x | Remove the song from the queue (like dd; u undoes it)
# keybind: Nada/queue:normal | d G | Remove every song from here to the end (u undoes it)
# keybind: Nada/queue:normal | y y | Copy the song (yank; 3yy: three)
# keybind: Nada/queue:normal | g p | Paste removed or copied songs below
# keybind: Nada/queue:normal | g P | Paste removed or copied songs above
# keybind: Nada/queue:normal | J | Move the song down
# keybind: Nada/queue:normal | K | Move the song up
# keybind: Nada/queue:normal | A | Move the song to play next
# keybind: Nada/queue:normal | D | Save the YouTube song to your music folder (download; V: the selection)
# keybind: Nada/queue:normal | n | Jump to the next match (after a "This list" search)
# keybind: Nada/queue:normal | N | Jump to the previous match
# keybind: Nada/queue:normal | Space d d | Remove the song from the queue (u undoes it)
# keybind: Nada/library:normal | h | Move to the column on the left
# keybind: Nada/library:normal | l | Move to the column on the right
# keybind: Nada/library:normal | Tab | Switch between artists, albums, genres and folders
# keybind: Nada/library:normal | Enter | Play the artist, album or song (replaces the queue)
# keybind: Nada/library:normal | a | Add to the end of the queue
# keybind: Nada/library:normal | A | Add to play next
# keybind: Nada/library:normal | Space a a | Add to the end of the queue
# keybind: Nada/library:normal | Space a n | Add to play next
# keybind: Nada/youtube:normal | Enter | Play the result
# keybind: Nada/youtube:normal | a | Add the result to the end of the queue
# keybind: Nada/youtube:normal | A | Add the result to play next
# keybind: Nada/youtube:normal | D | Save the result to your music folder (download)
# keybind: Nada/youtube:normal | Space a a | Add the result to the end of the queue
# keybind: Nada/youtube:normal | Space a n | Add the result to play next
# keybind: Nada/playlists:normal | h | Move to the playlists
# keybind: Nada/playlists:normal | l | Move to the playlist's songs
# keybind: Nada/playlists:normal | Enter | Play the playlist (replaces the queue)
# keybind: Nada/playlists:normal | a | Add the playlist to the end of the queue
# keybind: Nada/playlists:normal | A | Add the playlist to play next
# keybind: Nada/playlists:normal | d d | Delete the playlist (asks first)
# keybind: Nada/playlists:normal | D | Save the playlist's YouTube songs to your music folder (download)
# keybind: Nada/playlists:normal | Space a a | Add the playlist to the end of the queue
# keybind: Nada/playlists:normal | Space a n | Add the playlist to play next
# keybind: Nada/playlists:normal | Space d d | Delete the playlist (asks first)
# keybind: Nada/downloads:normal | Enter | Play the saved song
# keybind: Nada/downloads:normal | R | Retry a failed download
# keybind: Nada/downloads:normal | d d | Delete the saved file (asks first)
# keybind: Nada/downloads:normal | Space x r | Retry a failed download
# keybind: Nada/downloads:normal | Space d d | Delete the saved file (asks first)
# keybind: Nada/now:normal | Enter | Toggle play / pause
# keybind: Nada/queue:visual | d | Remove the selected songs (u undoes it)
# keybind: Nada/queue:visual | x | Remove the selected songs (like d; u undoes it)
# keybind: Nada/queue:visual | y | Copy the selected songs (yank)
# keybind: Nada/queue:visual | D | Save the selected YouTube songs (download)
# keybind: Nada/queue:visual | V | Leave visual mode
# keybind: Nada/queue:visual | Esc | Leave visual mode
# keybind: Nada/youtube:visual | a | Add the selected results to the end of the queue
# keybind: Nada/youtube:visual | A | Add the selected results to play next
# keybind: Nada/youtube:visual | D | Save the selected results (download)
# keybind: Nada/youtube:visual | V | Leave visual mode
# keybind: Nada/youtube:visual | Esc | Leave visual mode
# keybind: Nada/lyrics panel:normal | j | Move down through the versions the sources have
# keybind: Nada/lyrics panel:normal | k | Move up through the versions
# keybind: Nada/lyrics panel:normal | Enter | Use these lyrics (kept for the song)
# keybind: Nada/lyrics panel:normal | s | Switch the script: Hinglish (Latin letters) or Devanagari
# keybind: Nada/lyrics panel:normal | [ | Show the lyrics earlier by 0.25 s (kept for the song)
# keybind: Nada/lyrics panel:normal | ] | Show the lyrics later by 0.25 s (kept for the song)
# keybind: Nada/lyrics panel:normal | Esc | Close the lyrics panel (q too)
# keybind: Nada/search:insert | Tab | Switch where to look (all, YouTube, library, playlists, commands, this list)
# keybind: Nada/search:insert | Shift+Tab | Switch back where to look
# keybind: Nada/search:insert | Ctrl+j | Move down through the results while typing
# keybind: Nada/search:insert | Ctrl+k | Move up through the results while typing
# keybind: Nada/search:insert | Enter | Play the result (a playlist: replace the queue; a command: run it)
# keybind: Nada/search:insert | Ctrl+Enter | Play the result next
# keybind: Nada/search:insert | Shift+Enter | Add the result to the end of the queue
# keybind: Nada/search:insert | Ctrl+d | Download the result (YouTube)
# keybind: Nada/search:insert | Ctrl+u | Clear the search box
# keybind: Nada/search:insert | Ctrl+x | Clear recent searches
# keybind: Nada/search:insert | Esc | Close the search panel
# keybind: Nada/palette:insert | Ctrl+j | Move down through the actions (Down too)
# keybind: Nada/palette:insert | Ctrl+k | Move up through the actions (Up too)
# keybind: Nada/palette:insert | Enter | Run the action
# keybind: Nada/palette:insert | Esc | Close the palette
# keybind: Nada/leader:normal | Esc | Cancel a pending key or count (Space, g, d…)
# keybind-group: Nada/everywhere | Space l | Lyrics
# keybind-group: Nada/everywhere | Space p | Playback
# keybind-group: Nada/everywhere | Space x | Downloads
# --- end of keybind lines ---
