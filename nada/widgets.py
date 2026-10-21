"""Shared widgets: a vim-driven list, synced lyrics, cover art."""
import hashlib

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

# Nerd Font glyphs
G = {
    "note": "\U000f075a", "prev": "\U000f04ae", "next": "\U000f04ad", "play": "\U000f040a", "pause": "\U000f03e4",
    "back": "\U000f0d2a", "fwd": "\U000f0d71", "shuffle": "\U000f049d", "repeat": "\U000f0456",
    "repeat_off": "\U000f0457", "repeat_one": "\U000f0458", "vol": "\U000f057e", "mute": "\U000f075f",
    "mic": "\U000f036c", "dl": "\U000f01da", "yt": "\U000f05c3", "radio": "\U000f0439", "disk": "\U000f01bc",
    "home": "\U000f02dc", "queue": "\U000f0cb8", "lib": "\U000f0331", "list": "\U000f0279", "search": "\U000f0349",
    "folder": "\U000f024b", "artist": "\U000f0803", "album": "\U000f0025", "warn": "\U000f0026", "check": "\U000f012c",
}
PALETTE = ["#f9e2af", "#fab387", "#f38ba8", "#cba6f7", "#89b4fa", "#94e2d5", "#a6e3a1", "#89dceb", "#f5c2e7", "#b4befe"]


def label(text="", cls=None, xalign=0.0, ellipsize=True, wrap=False, markup=False, **kw):
    w = Gtk.Label(xalign=xalign, **kw)
    if markup:
        w.set_markup(text)
    else:
        w.set_text(text or "")
    if ellipsize and not wrap:
        w.set_ellipsize(Pango.EllipsizeMode.END)
    if wrap:
        w.set_wrap(True)
        w.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        if "width_chars" not in kw:
            w.set_width_chars(18)   # else GTK measures it one character wide (and very tall)
        if "max_width_chars" not in kw:
            w.set_max_width_chars(46)   # and its natural width would stretch the window
    for c in (cls.split() if isinstance(cls, str) else cls or []):
        w.add_css_class(c)
    return w


def box(*children, vertical=False, spacing=0, cls=None, **kw):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=spacing, **kw)
    for c in (cls.split() if isinstance(cls, str) else cls or []):
        b.add_css_class(c)
    for ch in children:
        if ch is not None:
            b.append(ch)
    return b


def keycap(text):
    return label(text, "keycap", ellipsize=False)


def hint(keys, what):
    b = box(spacing=5)
    for k in keys.split():
        b.append(keycap(k))
    b.append(label(what, "dim", ellipsize=False))
    return b


def esc(s):
    return GLib.markup_escape_text(s or "")


def initials(title):
    words = [w for w in (title or "").replace("(", " ").split() if w[:1].isalnum()]
    return "".join(w[0] for w in words[:2]).upper() or "♪"


def tile_color(key):
    return PALETTE[int(hashlib.md5((key or "").encode()).hexdigest(), 16) % len(PALETTE)]


_tile_css = {}


def tile(song_key, title, size=38):
    """A coloured square with the song's initials (until its cover loads)."""
    color = tile_color(song_key)
    cls = "tile-" + color[1:]
    if cls not in _tile_css:
        p = Gtk.CssProvider()
        p.load_from_string(f".{cls} {{ background-image: linear-gradient(135deg, {color}, alpha({color}, 0.6)); }}")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        _tile_css[cls] = p
    lab = label(initials(title), "tile " + cls, xalign=0.5, ellipsize=False)
    lab.set_size_request(size, size)
    return lab


_textures = {}


def texture(path, size):
    """A square-cropped texture of an image file (cached)."""
    key = (path, size)
    if key in _textures:
        return _textures[key]
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
    except GLib.Error:
        return None
    w, h = pb.get_width(), pb.get_height()
    s = min(w, h)
    pb = pb.new_subpixbuf((w - s) // 2, (h - s) // 2, s, s).scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
    t = Gdk.Texture.new_for_pixbuf(pb)
    if len(_textures) > 400:
        _textures.clear()
    _textures[key] = t
    return t


def picture(path, size, cls="cover"):
    t = texture(path, size) if path else None
    if t is None:
        return None
    p = Gtk.Picture.new_for_paintable(t)
    p.set_size_request(size, size)
    p.set_can_shrink(True)
    p.set_content_fit(Gtk.ContentFit.COVER)
    p.add_css_class(cls)
    p.set_overflow(Gtk.Overflow.HIDDEN)
    return p


class RowList(Gtk.ScrolledWindow):
    """A scrolling list of selectable rows and section headers. Selection
    is ours (vim keys), not GTK's: sel is an index into the items."""

    def __init__(self, on_activate=None, on_select=None):
        super().__init__(hexpand=True, vexpand=True)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.inner = box(vertical=True, cls="list")
        self.set_child(self.inner)
        self.items, self.widgets = [], []
        self.sel, self.vstart = 0, None
        self.on_activate, self.on_select = on_activate, on_select
        self.placeholder = None

    def set_rows(self, rows, keep=True, empty=None):
        """rows: [("header", widget) | ("item", data, widget)]."""
        old = self.items[self.sel] if keep and 0 <= self.sel < len(self.items) else None
        child = self.inner.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.inner.remove(child)
            child = nxt
        self.items, self.widgets = [], []
        for r in rows:
            if r[0] == "header":
                self.inner.append(r[1])
                continue
            _, data, w = r
            i = len(self.items)
            self.items.append(data)
            self.widgets.append(w)
            w.add_css_class("row")
            click = Gtk.GestureClick()
            click.connect("pressed", self._clicked, i)
            w.add_controller(click)
            self.inner.append(w)
        if not self.items and empty is not None:
            self.inner.append(empty)
        if old is not None and old in self.items:
            self.sel = self.items.index(old)
        self.sel = max(0, min(self.sel, len(self.items) - 1))
        if self.vstart is not None and self.vstart >= len(self.items):
            self.vstart = None
        self._paint()

    def _clicked(self, gesture, n, x, y, i):
        self.select(i)
        if n == 2 and self.on_activate:
            self.on_activate(self.items[i])

    def range(self):
        if self.vstart is None:
            return [self.sel] if self.items else []
        lo, hi = sorted((self.vstart, self.sel))
        return list(range(lo, hi + 1))

    def _paint(self):
        rng = set(self.range()) if self.vstart is not None else set()
        for i, w in enumerate(self.widgets):
            (w.add_css_class if i == self.sel else w.remove_css_class)("sel")
            (w.add_css_class if i in rng else w.remove_css_class)("vis")

    def select(self, i, scroll=True):
        if not self.items:
            return
        self.sel = max(0, min(len(self.items) - 1, i))
        self._paint()
        if scroll:
            GLib.idle_add(self._scroll)
        if self.on_select:
            self.on_select(self.selected())

    def move(self, n):
        self.select(self.sel + n)

    def selected(self):
        return self.items[self.sel] if 0 <= self.sel < len(self.items) else None

    def page(self):
        h = self.get_height() or 400
        return max(1, int(h / 54 / 2))

    def _scroll(self):
        if not (0 <= self.sel < len(self.widgets)):
            return False
        w = self.widgets[self.sel]
        ok, rect = w.compute_bounds(self.inner)
        if not ok:
            return False
        adj = self.get_vadjustment()
        top, bot = rect.get_y(), rect.get_y() + rect.get_height()
        if top - 36 < adj.get_value():
            adj.set_value(max(0, top - 36))
        elif bot + 12 > adj.get_value() + adj.get_page_size():
            adj.set_value(bot + 12 - adj.get_page_size())
        return False

    def visual(self, on=None):
        on = (self.vstart is None) if on is None else on
        self.vstart = self.sel if on else None
        self._paint()
        return on


class LyricsView(Gtk.Box):
    """Lyrics that scroll with the song: the current line lit, the ones
    sung readable, the rest faded. Clicking a line seeks there."""

    def __init__(self, on_seek, big=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, vexpand=True, hexpand=True)
        self.add_css_class("lyrics")
        if big:
            self.add_css_class("big")
        self.on_seek = on_seek
        self.scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_min_content_height(60)
        self.scroll.add_css_class("noscrollbar")
        self.inner = box(vertical=True, margin_start=32 if big else 20, margin_end=24 if big else 16)
        self.scroll.set_child(self.inner)
        self.append(self.scroll)
        self.lines, self.labels, self.synced, self.cur = [], [], False, -2
        self.anim = None
        self.key = None
        # keep the current line centred when the view changes size
        self.scroll.get_vadjustment().connect("notify::page-size", lambda *_: self._resized())

    def _resized(self):
        self._pad()
        if self.synced and self.cur >= 0:
            GLib.idle_add(lambda: (self._center(self.cur), False)[1])

    def set(self, data, key=None, message=None):
        self.key = key
        child = self.inner.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.inner.remove(child)
            child = nxt
        self.labels, self.cur = [], -2
        self.lines = data.get("lines") or [] if data else []
        self.synced = bool(data and data.get("synced"))
        spacer_top = Gtk.Box(height_request=1)
        self.inner.append(spacer_top)
        self.top_spacer = spacer_top
        if message or not self.lines:
            msg = message or ("Looking for lyrics…" if data and data.get("loading") else
                              "No lyrics found for this song.\nLooked in the file, next to it and on LRCLIB.\n:lyrics <search> to pick them by hand")
            lab = label(msg, "plain", xalign=0.5, wrap=True, justify=Gtk.Justification.CENTER, vexpand=True)
            lab.add_css_class("dim")
            self.inner.append(lab)
            self.top_spacer.set_size_request(-1, 120)
            return
        for i, (t, text) in enumerate(self.lines):
            gap = text.strip() in ("", "♪") or text.strip().startswith("♪")
            lab = label(text if text.strip() else "♪", "line" if self.synced else "plain", wrap=True)
            if gap:
                lab.add_css_class("gap")
            if self.synced and t is not None:
                g = Gtk.GestureClick()
                g.connect("pressed", lambda *_a, tt=t: self.on_seek(tt))
                lab.add_controller(g)
                lab.set_cursor(Gdk.Cursor.new_from_name("pointer"))
            self.inner.append(lab)
            self.labels.append(lab)
        bottom = Gtk.Box()
        self.inner.append(bottom)
        self.bottom_spacer = bottom
        GLib.idle_add(self._pad)

    def _pad(self):
        h = self.scroll.get_height() or 400
        if self.synced and self.top_spacer.get_height() != h // 2:
            self.top_spacer.set_size_request(-1, h // 2)
            self.bottom_spacer.set_size_request(-1, h // 2)
            if self.cur >= 0:   # the spacers changed the layout: centre again once it settles
                GLib.timeout_add(80, lambda: (self._center(self.cur), False)[1])
        return False

    def update(self, t):
        if not self.synced or not self.labels:
            return
        k = -1
        for i, (lt, _) in enumerate(self.lines):
            if lt is not None and lt <= t + 0.15:
                k = i
            else:
                break
        if k == self.cur:
            return
        self.cur = k
        for i, lab in enumerate(self.labels):
            (lab.add_css_class if i == k else lab.remove_css_class)("cur")
            (lab.add_css_class if i < k else lab.remove_css_class)("past")
        self._center(max(0, k))

    def current_text(self, t):
        if not self.lines:
            return ""
        txt = ""
        for lt, x in self.lines:
            if lt is None:
                return self.lines[0][1]
            if lt <= t + 0.15:
                txt = x
        return txt or self.lines[0][1]

    def _center(self, k):
        if not (0 <= k < len(self.labels)):
            return
        lab = self.labels[k]
        ok, rect = lab.compute_bounds(self.inner)
        if not ok:
            GLib.timeout_add(60, lambda: (self._center(k), False)[1])
            return
        adj = self.scroll.get_vadjustment()
        target = rect.get_y() + rect.get_height() / 2 - adj.get_page_size() / 2
        target = max(0, min(target, adj.get_upper() - adj.get_page_size()))
        start, t0 = adj.get_value(), GLib.get_monotonic_time()
        if self.anim:
            GLib.source_remove(self.anim)

        def step():
            p = min(1.0, (GLib.get_monotonic_time() - t0) / 380000)
            e = 1 - (1 - p) ** 3
            adj.set_value(start + (target - start) * e)
            if p >= 1:
                self.anim = None
                return False
            return True
        self.anim = GLib.timeout_add(16, step)
