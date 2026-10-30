"""Events for the emulated kernel: non-blocking I/O, stream sockets whose other ends are
scripted clients ("peers"), epoll, timerfd, and virtual time.

Virtual time: every syscall takes 1 µs. When every process is waiting, time jumps to
the next thing that can happen (a peer's next step, a timer, an epoll timeout), so
waiting a minute costs nothing and every run is the same.

A peer can also be the writing end of a pipe the program inherits:
    {"pipe": 3, "steps": [{"send": "21.5\n"}, {"sleep": 10000}, {"send": "22"}, ...]}
it closes the pipe when its steps are done.

A peer is a client script from the test, e.g.
    {"connect": 7000, "at": 1000, "steps": [{"send": "hi\\n"}, {"expect": "hi\\n"}, {"close": true}]}
Steps: send / send_hex, expect (wait for exactly these bytes; optionally "after" / "within":
µs since the step began, for things that must happen at the right time), drain (take what's there),
sleep (µs), shutdown (stop sending: the server reads EOF), close (stop sending and
receiving), expect_eof (wait until the server closes the connection).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

EAGAIN, EBADF, EINVAL, EPIPE, ENOTSOCK, EADDRINUSE, ECONNREFUSED, EEXIST, ENOENT, EPERM = (
    11, 9, 22, 32, 88, 98, 111, 17, 2, 1)
ENOTCONN, EAFNOSUPPORT, EOPNOTSUPP, EFAULT = 107, 97, 95, 14
AF_UNIX, AF_INET, SOCK_STREAM = 1, 2, 1
NONBLOCK, CLOEXEC = 0o4000, 0o2000000            # O_/SOCK_/TFD_ flags share these values
EPOLLIN, EPOLLOUT, EPOLLERR, EPOLLHUP, EPOLLRDHUP = 0x1, 0x4, 0x8, 0x10, 0x2000
EPOLLONESHOT, EPOLLET = 1 << 30, 1 << 31
SOCKET_CAPACITY = 65536
US = 1000                                        # ns per µs
PEER_PATIENCE = 2_000_000 * US                   # a peer gives up after 2 s of waiting


@dataclass
class Conn:
    to_server: bytearray = field(default_factory=bytearray)
    to_client: bytearray = field(default_factory=bytearray)
    client_sending: bool = True      # False after the peer's shutdown/close: server reads EOF
    client_reading: bool = True      # False after the peer's close: server writes get EPIPE
    port: int = 0
    accepted: bool = False


@dataclass
class Peer:
    script: dict
    index: int
    step: int = 0
    conn: int | None = None
    wake: int = 0                    # don't act before this time
    waiting_since: int | None = None
    received: bytearray = field(default_factory=bytearray)
    errors: list[str] = field(default_factory=list)
    done: bool = False
    tries: int = 0
    pipe: int | None = None          # a pipe peer: the pipe it writes
    step_started: int = 0

    @property
    def name(self) -> str:
        return self.script.get("name", f"client {self.index + 1}")


@dataclass
class Timer:
    next_ns: int = 0                 # 0: disarmed
    interval_ns: int = 0
    expirations: int = 0


def _ms(us: int) -> str:
    return f"{us / 1000:g} ms"


class EventsMixin:
    """Mixed into Kernel; uses its fds, procs, time_ns, _new_fd, _chunk..."""

    def init_events(self, peers: list[dict]) -> None:
        self.conns: dict[int, Conn] = {}
        self.listeners: dict[tuple, list[int]] = {}       # address -> backlog of conn ids
        self.timers: dict[int, Timer] = {}
        self.epolls: dict[int, dict[int, list[int]]] = {}   # id -> fd -> [events, data]
        self.peers = [Peer(p, i, wake=p.get("at", 0) * US + self.time_ns)
                      for i, p in enumerate(peers)]
        self.next_obj = 1
        self.peer_pipes: set[int] = set()                  # pipes whose writer is a peer
        from .kernel import OpenFile
        for p in self.peers:
            if "pipe" in p.script:
                p.pipe = len(self.pipes) + 1
                self.pipes[p.pipe] = bytearray()
                self.peer_pipes.add(p.pipe)
                self.proc.fds[p.script["pipe"]] = OpenFile("pipe", f"pipe:[{p.pipe}]",
                                                           readable=True, pipe=p.pipe)

    def _obj(self) -> int:
        self.next_obj += 1
        return self.next_obj

    # ---- virtual time -----------------------------------------------------------------------

    def tick(self) -> None:
        """Called at every syscall: time moves on, timers fire, peers act."""
        self.time_ns += US
        self.run_peers()

    def next_event(self) -> int | None:
        """When something will happen next without any process doing anything."""
        times = [p.wake for p in self.peers if not p.done and p.wake > self.time_ns]
        times += [p.waiting_since + PEER_PATIENCE for p in self.peers
                  if not p.done and p.waiting_since is not None]
        times += [t.next_ns for t in self.timers.values() if t.next_ns]
        times += [p.deadline for p in self.procs.values()
                  if p.status is None and p.deadline is not None]
        future = [t for t in times if t > self.time_ns]
        return min(future) if future else None

    def advance_time(self) -> bool:
        """Everyone waits: jump to the next event. False if nothing will ever happen."""
        t = self.next_event()
        if t is None:
            return False
        self.time_ns = t
        self.run_peers()
        return True

    def _fire_timers(self) -> None:
        for t in self.timers.values():
            if t.next_ns and self.time_ns >= t.next_ns:
                if t.interval_ns:
                    n = (self.time_ns - t.next_ns) // t.interval_ns + 1
                    t.expirations += n
                    t.next_ns += n * t.interval_ns
                else:
                    t.expirations += 1
                    t.next_ns = 0

    # ---- peers ------------------------------------------------------------------------------

    @property
    def peers_done(self) -> bool:
        return bool(self.peers) and all(p.done for p in self.peers)

    def run_peers(self) -> bool:
        self._fire_timers()
        acted = False
        for p in self.peers:
            while not p.done and self.time_ns >= p.wake and self._peer_step(p):
                acted = True
        return acted

    def _peer_fail(self, p: Peer, why: str) -> None:
        p.errors.append(why)
        p.done = True
        self.peer_pipes.discard(p.pipe)
        if p.conn is not None:
            c = self.conns[p.conn]
            c.client_sending = c.client_reading = False

    def _peer_step(self, p: Peer) -> bool:
        """Try p's current step. True if it finished the step (and may go on)."""
        if p.pipe is not None:
            return self._pipe_peer_step(p)
        if p.conn is None:                         # first: connect
            backlog = self.listeners.get(self._address(p.script["connect"]))
            if backlog is None:
                p.tries += 1
                if p.tries > 100:
                    self._peer_fail(p, f"couldn't connect to {p.script['connect']}: "
                                       "nobody is listening there")
                    return False
                p.wake = self.time_ns + 1000 * US           # try again in 1 ms
                return False
            p.conn = self._obj()
            self.conns[p.conn] = Conn(port=40000 + p.index)
            backlog.append(p.conn)
            p.step_started = self.time_ns
            return True
        steps = p.script.get("steps", [])
        if p.step >= len(steps):
            p.done = True
            return False
        s, c = steps[p.step], self.conns[p.conn]
        if "send" in s or "send_hex" in s:
            data = bytes.fromhex(s["send_hex"]) if "send_hex" in s else s["send"].encode()
            if c.client_sending:
                c.to_server += data
        elif "expect" in s:
            want = s["expect"].encode()
            closed = self._server_closed(p.conn)
            late = "within" in s and (self.time_ns - p.step_started) // US > s["within"]
            if len(c.to_client) < len(want) and not closed and late:
                self._peer_fail(p, f"waited {_ms(s['within'])} for {want!r} (it should have come "
                                   f"by then) but got only {bytes(c.to_client)!r}")
                return False
            if len(c.to_client) < len(want) and not closed:
                if "within" in s:            # come back exactly at the limit
                    p.wake = max(p.wake, p.step_started + s["within"] * US + US)
                return self._peer_wait(p, f"waited for {want!r} but got only {bytes(c.to_client)!r}")
            got = bytes(c.to_client[:len(want)])
            del c.to_client[:len(want)]
            p.received += got
            if got != want:
                end = " and then the server closed the connection" if closed and len(got) < len(want) else ""
                self._peer_fail(p, f"expected {want!r}, got {got!r}{end}")
                return False
            waited = (self.time_ns - p.step_started) // US
            if "after" in s and waited < s["after"]:
                self._peer_fail(p, f"got {want!r} too early: {_ms(waited)} after the previous "
                                   f"step, expected at least {_ms(s['after'])}")
                return False
        elif "drain" in s:
            p.received += c.to_client
            c.to_client.clear()
        elif "sleep" in s:
            if p.waiting_since is None:
                p.waiting_since = self.time_ns         # (marks the sleep as started)
                p.wake = self.time_ns + s["sleep"] * US
                return False
        elif "shutdown" in s:
            c.client_sending = False
        elif "close" in s:
            c.client_sending = c.client_reading = False
        elif "expect_eof" in s:
            if not self._server_closed(p.conn):
                if c.to_client:
                    p.received += c.to_client
                    c.to_client.clear()
                return self._peer_wait(p, "waited for the server to close the connection")
            if c.to_client:
                self._peer_fail(p, f"expected the connection to close, got {bytes(c.to_client)!r} first")
                return False
        p.step += 1
        p.waiting_since = None
        p.step_started = self.time_ns
        return True

    def _pipe_peer_step(self, p: Peer) -> bool:
        steps = p.script.get("steps", [])
        if p.step >= len(steps) or "close" in steps[p.step]:
            p.done = True
            self.peer_pipes.discard(p.pipe)            # the program reads EOF
            return False
        s, buf = steps[p.step], self.pipes[p.pipe]
        if "send" in s:
            data = s["send"].encode()
            if len(buf) + len(data) > 65536:
                return self._peer_wait(p, "the pipe stayed full: nobody read it")
            buf += data
        elif "sleep" in s and p.waiting_since is None:
            p.waiting_since = self.time_ns
            p.wake = self.time_ns + s["sleep"] * US
            return False
        p.step += 1
        p.waiting_since = None
        return True

    def _peer_wait(self, p: Peer, why: str) -> bool:
        if p.waiting_since is None:
            p.waiting_since = self.time_ns
        elif self.time_ns - p.waiting_since >= PEER_PATIENCE:
            self._peer_fail(p, f"{why} (gave up after {PEER_PATIENCE // 10**9} s)")
        return False

    def peer_report(self) -> list[str]:
        out = []
        for p in self.peers:
            out += [f"{p.name}: {e}" for e in p.errors]
            if not p.done and not p.errors:
                steps = p.script.get("steps", [])
                what = (f"was still at step {p.step + 1} ({steps[p.step]})" if p.step < len(steps)
                        else "never finished")
                if p.conn is None:
                    what = "never got connected"
                out.append(f"{p.name}: {what}")
        return out

    # ---- sockets ------------------------------------------------------------------------------

    @staticmethod
    def _address(a) -> tuple:
        return ("inet", a) if isinstance(a, int) else ("unix", a)

    def _conn_open(self, conn: int) -> bool:
        """Does the server still hold this connection open, in any process?"""
        return any(f.kind == "conn" and f.ref == conn
                   for p in self.procs.values() if p.status is None for f in p.fds.values())

    def _server_closed(self, conn: int) -> bool:
        return self.conns[conn].accepted and not self._conn_open(conn)

    def _ref_open(self, kind: str, ref) -> bool:
        return any(f.kind == kind and f.ref == ref
                   for p in self.procs.values() if p.status is None for f in p.fds.values())

    def file_closed(self, f) -> None:
        """A descriptor was closed: if it was the last one, the object goes away."""
        if f.kind == "listen" and not self._ref_open("listen", f.ref):
            self.listeners.pop(f.ref, None)

    def sys_socket(self, m, domain, type_, protocol, *_):
        if domain not in (AF_UNIX, AF_INET):
            return -EAFNOSUPPORT
        if type_ & 0xF != SOCK_STREAM:
            return -EINVAL
        from .kernel import OpenFile
        fd = self._new_fd(OpenFile("socket", f"socket:[{self._obj()}]", readable=True,
                                   writable=True, nonblock=bool(type_ & NONBLOCK)))
        if type_ & CLOEXEC:
            self.cloexec.add(fd)
        return fd

    def _sockaddr(self, m, addr, length) -> tuple | int:
        if length < 2 or not m.readable(addr, min(length, 110)):
            return -EINVAL if length < 2 else -EFAULT
        raw = m.read(addr, min(length, 110))
        family = struct.unpack_from("<H", raw)[0]
        if family == AF_INET:
            if length < 16:
                return -EINVAL
            return ("inet", struct.unpack_from(">H", raw, 2)[0])
        if family == AF_UNIX:
            return ("unix", raw[2:].split(b"\0")[0].decode("utf-8", "replace"))
        return -EAFNOSUPPORT

    def sys_setsockopt(self, m, fd, *_):
        f = self.fds.get(fd)
        return -EBADF if f is None else 0 if f.kind in ("socket", "listen", "conn") else -ENOTSOCK

    def sys_bind(self, m, fd, addr, length, *_):
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        if f.kind != "socket":
            return -ENOTSOCK if f.kind not in ("listen", "conn") else -EINVAL
        a = self._sockaddr(m, addr, length)
        if isinstance(a, int):
            return a
        if a in self.listeners:
            return -EADDRINUSE
        f.addr = a
        return 0

    def sys_listen(self, m, fd, backlog, *_):
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        if f.kind == "listen":
            return 0
        if f.kind != "socket" or f.addr is None:
            return -EINVAL if f.kind == "socket" else -ENOTSOCK
        if f.addr in self.listeners:
            return -EADDRINUSE
        f.kind, f.ref = "listen", f.addr
        self.listeners[f.addr] = []
        return 0

    def sys_accept(self, m, fd, addr, addrlen, *_):
        return self.sys_accept4(m, fd, addr, addrlen, 0)

    def sys_accept4(self, m, fd, addr, addrlen, flags, *_):
        from .kernel import Block, OpenFile
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        if f.kind != "listen":
            return -EINVAL if f.kind == "socket" else -ENOTSOCK
        backlog = self.listeners[f.ref]
        if not backlog:
            if f.nonblock:
                return -EAGAIN
            raise Block(f"accept on fd {fd}: no client is connecting")
        conn = backlog.pop(0)
        self.conns[conn].accepted = True
        new = self._new_fd(OpenFile("conn", f"socket:[{conn}]", readable=True, writable=True,
                                    nonblock=bool(flags & NONBLOCK), ref=conn))
        if flags & CLOEXEC:
            self.cloexec.add(new)
        if addr and addrlen:
            if f.ref[0] == "inet":
                sa = struct.pack("<H", AF_INET) + struct.pack(">H", self.conns[conn].port) \
                    + bytes([127, 0, 0, 1]) + bytes(8)
            else:
                sa = struct.pack("<H", AF_UNIX)
            room = struct.unpack("<I", m.read(addrlen, 4))[0]
            m.kernel_write(addr, sa[:room])
            m.kernel_write(addrlen, struct.pack("<I", len(sa)))
        return new

    def sys_shutdown(self, m, fd, how, *_):
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        return 0 if f.kind == "conn" else -ENOTCONN

    def read_conn(self, f, fd, count) -> bytes:
        from .kernel import Block
        c = self.conns[f.ref]
        if not c.to_server:
            if not c.client_sending:
                return b""                                   # the client is done: EOF
            if f.nonblock:
                raise OSError(EAGAIN)
            raise Block(f"read from a connection with no data yet (fd {fd})")
        data = bytes(c.to_server[:self._chunk(min(count, len(c.to_server)), self.inject.short_reads)])
        del c.to_server[:len(data)]
        return data

    def write_conn(self, f, fd, n) -> int:
        """How many bytes the connection takes now (the caller copies them)."""
        from .kernel import Block, SIGPIPE
        c = self.conns[f.ref]
        if not c.client_reading:
            self.raise_signal(SIGPIPE)
            raise OSError(EPIPE)
        room = SOCKET_CAPACITY - len(c.to_client)
        if room == 0 and n:
            if f.nonblock:
                raise OSError(EAGAIN)
            raise Block(f"write to a connection whose client isn't reading (fd {fd})")
        return min(n, room)

    # ---- timerfd ------------------------------------------------------------------------------

    def sys_timerfd_create(self, m, clock, flags, *_):
        from .kernel import OpenFile
        if clock not in (0, 1) or flags & ~(NONBLOCK | CLOEXEC):
            return -EINVAL
        t = self._obj()
        self.timers[t] = Timer()
        fd = self._new_fd(OpenFile("timer", f"anon_inode:[timerfd]", readable=True,
                                   nonblock=bool(flags & NONBLOCK), ref=t))
        if flags & CLOEXEC:
            self.cloexec.add(fd)
        return fd

    def sys_timerfd_settime(self, m, fd, flags, new, old, *_):
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        if f.kind != "timer":
            return -EINVAL
        t = self.timers[f.ref]
        if old:
            self.sys_timerfd_gettime(m, fd, old)
        if not m.readable(new, 32):
            return -EFAULT
        isec, insec, vsec, vnsec = struct.unpack("<qqqq", m.read(new, 32))
        if not (0 <= insec < 10**9 and 0 <= vnsec < 10**9) or isec < 0 or vsec < 0:
            return -EINVAL
        value = vsec * 10**9 + vnsec
        t.interval_ns = isec * 10**9 + insec
        t.expirations = 0
        if value == 0:
            t.next_ns = 0
        else:
            t.next_ns = value if flags & 1 else self.time_ns + value   # TFD_TIMER_ABSTIME
        return 0

    def sys_timerfd_gettime(self, m, fd, cur, *_):
        f = self.fds.get(fd)
        if f is None or f.kind != "timer":
            return -EBADF if f is None else -EINVAL
        t = self.timers[f.ref]
        left = max(t.next_ns - self.time_ns, 0) if t.next_ns else 0
        m.kernel_write(cur, struct.pack("<qqqq", t.interval_ns // 10**9, t.interval_ns % 10**9,
                                        left // 10**9, left % 10**9))
        return 0

    def read_timer(self, f, fd, count) -> bytes:
        from .kernel import Block
        if count < 8:
            raise OSError(EINVAL)
        self._fire_timers()
        t = self.timers[f.ref]
        if not t.expirations:
            if f.nonblock:
                raise OSError(EAGAIN)
            raise Block(f"read from a timerfd that hasn't expired (fd {fd})")
        n, t.expirations = t.expirations, 0
        return struct.pack("<Q", n)

    # ---- readiness and epoll ------------------------------------------------------------------

    def ready(self, f) -> int:
        """The EPOLL* events a descriptor has right now (level-triggered)."""
        if f.kind == "pipe":
            if f.readable:
                ev = EPOLLIN if self.pipes[f.pipe] else 0
                return ev | ((EPOLLIN | EPOLLHUP) if not self._pipe_has(f.pipe, writable=True) else 0)
            if not self._pipe_has(f.pipe, writable=False):
                return EPOLLERR
            return EPOLLOUT if len(self.pipes[f.pipe]) < 65536 else 0
        if f.kind == "conn":
            c = self.conns[f.ref]
            ev = EPOLLIN if c.to_server else 0
            if not c.client_sending:
                ev |= EPOLLIN | EPOLLRDHUP
            if not c.client_reading:
                ev |= EPOLLHUP | EPOLLERR
            elif len(c.to_client) < SOCKET_CAPACITY:
                ev |= EPOLLOUT
            return ev
        if f.kind == "listen":
            return EPOLLIN if self.listeners.get(f.ref) else 0
        if f.kind == "timer":
            self._fire_timers()
            return EPOLLIN if self.timers[f.ref].expirations else 0
        if f.kind == "stdin":
            return EPOLLIN | (EPOLLHUP if self.stdin_pos >= len(self.stdin) else 0)
        if f.kind in ("stdout", "stderr"):
            return EPOLLOUT
        return EPOLLIN | EPOLLOUT

    def sys_epoll_create(self, m, size, *_):
        return self.sys_epoll_create1(m, 0) if size > 0 else -EINVAL

    def sys_epoll_create1(self, m, flags, *_):
        from .kernel import OpenFile
        if flags & ~CLOEXEC:
            return -EINVAL
        e = self._obj()
        self.epolls[e] = {}
        fd = self._new_fd(OpenFile("epoll", "anon_inode:[eventpoll]", readable=True, ref=e))
        if flags & CLOEXEC:
            self.cloexec.add(fd)
        return fd

    def sys_epoll_ctl(self, m, epfd, op, fd, event, *_):
        e = self.fds.get(epfd)
        if e is None or fd not in self.fds:
            return -EBADF
        if e.kind != "epoll" or epfd == fd:
            return -EINVAL
        if self.fds[fd].kind in ("file", "dir"):
            return -EPERM                    # regular files are always "ready": not allowed
        interest = self.epolls[e.ref]
        ADD, DEL, MOD = 1, 2, 3
        if op == DEL:
            return 0 if interest.pop(fd, None) is not None else -ENOENT
        if op not in (ADD, MOD):
            return -EINVAL
        if not m.readable(event, 12):
            return -EFAULT
        events, data = struct.unpack("<IQ", m.read(event, 12))   # packed: 12 bytes
        if op == ADD and fd in interest:
            return -EEXIST
        if op == MOD and fd not in interest:
            return -ENOENT
        interest[fd] = [events, data]
        return 0

    def sys_epoll_wait(self, m, epfd, events, maxevents, timeout, *_):
        from .kernel import Block
        e = self.fds.get(epfd)
        if e is None:
            return -EBADF
        if e.kind != "epoll" or not 0 < maxevents <= 1024:
            return -EINVAL
        if not m.writable(events, 12 * maxevents):
            return -EFAULT
        interest = self.epolls[e.ref]
        out = []
        for fd, (want, data) in list(interest.items()):
            f = self.fds.get(fd)
            if f is None:                    # closed: a closed fd leaves the interest list
                del interest[fd]
                continue
            if want & EPOLLONESHOT and want & 0xFFFF == 0:
                continue
            got = self.ready(f) & (want | EPOLLERR | EPOLLHUP)
            if got:
                out.append(struct.pack("<IQ", got, data))
                if want & EPOLLONESHOT:
                    interest[fd][0] = want & ~0xFFFF   # disabled until EPOLL_CTL_MOD
                if len(out) == maxevents:
                    break
        timeout = timeout - (1 << 64) if timeout >> 63 else timeout
        timeout = timeout - (1 << 32) if timeout >> 31 and timeout < 1 << 32 else timeout
        if not out and timeout != 0:
            if self.proc.deadline is None and timeout > 0:
                self.proc.deadline = self.time_ns + timeout * 10**6
            if self.proc.deadline is None or self.time_ns < self.proc.deadline:
                raise Block(f"epoll_wait on fd {epfd}: nothing is ready")
        if out:
            m.kernel_write(events, b"".join(out))
        return len(out)

    def sys_epoll_pwait(self, m, epfd, events, maxevents, timeout, sigmask, *_):
        return self.sys_epoll_wait(m, epfd, events, maxevents, timeout)
