"""A small MPD client: the text protocol over MPD's unix socket (MPD_HOST)
or TCP. Thread-safe: every command holds the connection's lock, and a
dropped connection is reopened once before giving up."""
import os
import socket
import threading


class MPDError(Exception):
    pass


def address():
    """(host or socket path, port, password) from MPD_HOST / MPD_PORT, else
    MPD's usual socket in $XDG_RUNTIME_DIR, else localhost:6600."""
    host = os.environ.get("MPD_HOST") or ""
    port = int(os.environ.get("MPD_PORT") or 6600)
    password = None
    if "@" in host and not host.startswith("@"):
        password, host = host.rsplit("@", 1)
    if not host:
        sock = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}", "mpd", "socket")
        host = sock if os.path.exists(sock) else "localhost"
    return host, port, password


def quote(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def split_items(pairs, starts=("file", "directory", "playlist")):
    """Splits a flat key/value response into one dict per item."""
    items, cur = [], None
    for k, v in pairs:
        if k in starts:
            cur = {k: v}
            items.append(cur)
        elif cur is not None:
            cur.setdefault(k, v)
    return items


class Client:
    def __init__(self, timeout=10):
        self.lock = threading.RLock()
        self.timeout = timeout
        self.sock = self.f = None
        self.local = False
        self.version = ""

    # ------------------------------------------------------------ connection
    def connect(self):
        with self.lock:
            self.close()
            host, port, password = address()
            if host.startswith("/"):
                s = socket.socket(socket.AF_UNIX)
                s.settimeout(self.timeout)
                s.connect(host)
                self.local = True
            else:
                s = socket.create_connection((host, port), timeout=self.timeout)
                self.local = False
            self.sock, self.f = s, s.makefile("rwb")
            hello = self.f.readline().decode()
            if not hello.startswith("OK MPD"):
                self.close()
                raise MPDError(f"not an MPD server: {hello.strip()}")
            self.version = hello.split()[2]
            if password:
                self._command("password", password)

    def close(self):
        with self.lock:
            for x in (self.f, self.sock):
                try:
                    if x:
                        x.close()
                except OSError:
                    pass
            self.sock = self.f = None

    @property
    def connected(self):
        return self.sock is not None

    # ------------------------------------------------------------ protocol
    def _read(self):
        pairs, binary = [], None
        while True:
            line = self.f.readline()
            if not line:
                raise ConnectionError("MPD closed the connection")
            line = line.decode("utf-8", "replace").rstrip("\n")
            if line == "OK":
                return pairs, binary
            if line.startswith("ACK "):
                msg = line.split("} ", 1)[-1]
                raise MPDError(msg)
            k, _, v = line.partition(": ")
            if k == "binary":
                binary = self.f.read(int(v))
                self.f.readline()
                continue
            pairs.append((k, v))

    def _command(self, name, *args):
        line = " ".join([name, *(quote(a) for a in args)])
        self.f.write((line + "\n").encode())
        self.f.flush()
        return self._read()

    def raw(self, name, *args):
        """(pairs, binary) of one command; reconnects once if the
        connection dropped."""
        with self.lock:
            for attempt in (0, 1):
                try:
                    if not self.connected:
                        self.connect()
                    return self._command(name, *args)
                except (ConnectionError, BrokenPipeError, socket.timeout, OSError) as e:
                    self.close()
                    if attempt:
                        raise MPDError(f"can't reach MPD: {e}") from None

    def pairs(self, name, *args):
        return self.raw(name, *args)[0]

    def dict(self, name, *args):
        return dict(self.pairs(name, *args))

    def items(self, name, *args):
        return split_items(self.pairs(name, *args))

    def run(self, name, *args):
        self.raw(name, *args)

    def values(self, name, *args):
        """The values of a `list` style response."""
        return [v for _, v in self.pairs(name, *args)]

    # ------------------------------------------------------------ helpers
    def status(self):
        return self.dict("status")

    def queue(self):
        return self.items("playlistinfo")

    def addid(self, uri, pos=None, tags=None):
        args = [uri] if pos is None else [uri, str(pos)]
        sid = self.dict("addid", *args)["Id"]
        for k, v in (tags or {}).items():
            if v:
                try:
                    self.run("addtagid", sid, k, str(v))
                except MPDError:
                    pass   # only works for songs outside the database
        return sid

    def picture(self, uri, cmd="albumart"):
        """The cover image bytes for uri (albumart: a cover file in the
        folder; readpicture: embedded in the file), or None."""
        data, offset = b"", 0
        while True:
            try:
                pairs, binary = self.raw(cmd, uri, str(offset))
            except MPDError:
                return None
            if not binary:
                return data or None
            data += binary
            size = int(dict(pairs).get("size", len(data)))
            offset = len(data)
            if offset >= size:
                return data

    def idle(self, *subsystems):
        """Blocks until something changes; returns the changed subsystems.
        Use a separate Client: the connection is busy while idling."""
        with self.lock:
            if not self.connected:
                self.connect()
            self.sock.settimeout(None)
            try:
                pairs, _ = self._command("idle", *subsystems)
            finally:
                if self.sock:
                    self.sock.settimeout(self.timeout)
            return [v for k, v in pairs if k == "changed"]


def seconds(song):
    for k in ("duration", "Time"):
        try:
            return float(song.get(k))
        except (TypeError, ValueError):
            pass
    return 0.0
