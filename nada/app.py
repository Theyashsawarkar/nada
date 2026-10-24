"""The resident application (dev.vayu.Nada): one process that holds the
MPD connection, MPRIS, downloads and autoplay, and shows the window when
asked. bin/nada talks to it over D-Bus (org.gtk.Actions)."""
import concurrent.futures
import json
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID  # noqa: E402
from .config import CONFIG  # noqa: E402
from .core import Core  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = self.mini = self.core = self.mpris = None
        self.thumb_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        for name, ptype in (("toggle", None), ("show", None), ("hide", None), ("mini", None), ("quit", None),
                            ("add", GLib.VariantType.new("s")), ("tab", GLib.VariantType.new("s"))):
            a = Gio.SimpleAction.new(name, ptype)
            a.connect("activate", getattr(self, "_act_" + name))
            self.add_action(a)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()   # stay resident: the music, MPRIS and downloads live here
        self.load_css()
        self.core = Core()
        from .mpris import MPRIS
        self.mpris = MPRIS(self.core, self.show_full, self.quit_all)

    def do_activate(self):
        pass   # started by `nada daemon`; windows open through the actions

    def load_css(self):
        css = open(os.path.join(HERE, "style.css")).read()
        css += theme_css()
        try:
            from .config import load
            op = load().get("opacity")
            op = min(1.0, max(0.3, float(theme_glass() if op is None else op)))
        except (TypeError, ValueError):
            op = 0.62
        css += f"\n.nada-root {{ background-color: alpha(@base, {op:.2f}); }}\n"
        user = os.path.join(os.path.dirname(CONFIG), "style.css")
        if os.path.exists(user):
            css += open(user).read()
        if getattr(self, "css_provider", None) is None:
            self.css_provider = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider,
                                                      Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.watch_theme()
        self.css_provider.load_from_string(css)

    def watch_theme(self):
        """Restyles when the theme changes (varna rewrites palette.json)."""
        path = theme_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.theme_monitor = Gio.File.new_for_path(path).monitor_file(Gio.FileMonitorFlags.NONE, None)
            self.theme_monitor.connect("changed", lambda _m, _f, _o, ev: ev in (
                Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED) and self.load_css())
        except GLib.Error:
            pass

    # ------------------------------------------------------------ windows
    def ensure_window(self):
        if self.window is None:
            from .window import Window
            self.window = Window(self, self.core)
        return self.window

    def show_full(self):
        if self.mini is not None:
            self.mini.set_visible(False)
        self.ensure_window().show_window()

    def show_mini(self):
        if self.mini is None:
            from .mini import Mini
            self.mini = Mini(self, self.core)
        if self.window is not None:
            self.window.hide_window()
        self.mini.set_visible(True)
        self.mini.present()

    def quit_all(self):
        self.release()
        self.quit()

    # ------------------------------------------------------------ actions
    def _act_toggle(self, *_):
        w = self.window
        if w is not None and w.get_visible():
            if w.is_active():
                w.hide_window()
            else:
                w.show_window()
        else:
            self.show_full()

    def _act_show(self, *_):
        self.show_full()

    def _act_hide(self, *_):
        if self.window is not None:
            self.window.hide_window()
        if self.mini is not None:
            self.mini.set_visible(False)

    def _act_mini(self, *_):
        if self.mini is not None and self.mini.get_visible():
            self.mini.set_visible(False)
        else:
            self.show_mini()

    def _act_quit(self, *_):
        self.quit_all()

    def _act_tab(self, _a, param):
        self.show_full()
        self.window.switch(param.get_string())

    def _act_add(self, _a, param):
        """{"url": url-or-search, "where": end|next|play}"""
        try:
            req = json.loads(param.get_string())
        except ValueError:
            req = {"url": param.get_string()}
        self.core.add_url(req.get("url", ""), req.get("where", "end"))


def main():
    from . import log
    log.setup("nada").info("nāda starting")
    app = App()
    return app.run([sys.argv[0]])


# The theme: with varna (github.com/Theyashsawarkar/varna) installed, nāda
# takes the current theme's colours (its own pick under `tools.nada`, else
# the desktop's); without it, style.css's Catppuccin Mocha.
THEME_NAMES = {"text": "text", "sub1": "subtext1", "sub0": "subtext0", "ov1": "overlay1", "ov0": "overlay0",
               "s1": "surface1", "s0": "surface0", "base": "base", "crust": "crust", "mauve": "accent", "pink": "pink",
               "red": "red", "peach": "peach", "yellow": "yellow", "green": "green", "teal": "teal", "sky": "sky",
               "blue": "blue", "lavender": "lavender"}


def theme_path():
    return os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "varna", "palette.json")


def theme_glass():
    """The panels' glass from varna (ui.glass), so this window looks like
    Vyom's panels; 0.62 without varna."""
    import json
    try:
        with open(theme_path()) as f:
            return float(json.load(f)["ui"]["glass"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0.62


def theme_css():
    import json
    try:
        with open(theme_path()) as f:
            data = json.load(f)
        colors = ((data.get("tools") or {}).get("nada") or data)["colors"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    return "\n" + "\n".join(f"@define-color {ours} {colors[theirs]};" for ours, theirs in THEME_NAMES.items()
                             if str(colors.get(theirs, "")).startswith("#")) + "\n"

