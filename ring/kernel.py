"""A small emulated Linux kernel for the emulator: a virtual filesystem, file
descriptors, memory syscalls, and fault injection (failing syscalls, short reads),
so levels can test what real programs must survive.

Each process is one Machine (its own Unicorn instance) plus a Proc here holding its
per-process kernel state (fds, signal handlers, heap...). `kernel.proc` is the process
whose code is running; the per-process fields below are reached through it, so most
of the kernel reads as if there were one process. The scheduler lives in emu.py.

The state is plain Python data, so the debugger can snapshot it at each syscall and
step backwards across syscalls (within one process: forks and execs end the history).
"""

from __future__ import annotations

import bisect
import copy
import random
import struct
from dataclasses import dataclass, field

from .kernel_events import EventsMixin

MASK64 = (1 << 64) - 1

# errno values (Linux x86-64)
EPERM, ENOENT, EINTR, EIO, EBADF, EAGAIN, ENOMEM, EACCES, EFAULT = 1, 2, 4, 5, 9, 11, 12, 13, 14
EEXIST, ENOTDIR, EISDIR, EINVAL, EMFILE, ENOTTY, ENOSPC, ESPIPE = 17, 20, 21, 22, 24, 25, 28, 29
ERANGE, ENOSYS, ENOTEMPTY, ELOOP = 34, 38, 39, 40
ESRCH, ENOEXEC, ECHILD, EPIPE, E2BIG, EXDEV = 3, 8, 10, 32, 7, 18
ERRNO_NAMES = {v: k for k, v in globals().items() if k.startswith("E") and isinstance(v, int)}

# open flags
O_ACCMODE, O_RDONLY, O_WRONLY, O_RDWR = 3, 0, 1, 2
O_CREAT, O_EXCL, O_TRUNC, O_APPEND, O_DIRECTORY, O_NOFOLLOW, O_CLOEXEC = (
    0o100, 0o200, 0o1000, 0o2000, 0o200000, 0o400000, 0o2000000)
AT_FDCWD = -100 & MASK64
AT_SYMLINK_NOFOLLOW, AT_EMPTY_PATH = 0x100, 0x1000

S_IFREG, S_IFDIR, S_IFLNK, S_IFCHR, S_IFIFO = 0o100000, 0o040000, 0o120000, 0o020000, 0o010000

NAMES = {0: "read", 1: "write", 2: "open", 3: "close", 4: "stat", 5: "fstat", 6: "lstat",
         8: "lseek", 9: "mmap", 10: "mprotect", 11: "munmap", 12: "brk", 13: "rt_sigaction",
         14: "rt_sigprocmask", 15: "rt_sigreturn", 16: "ioctl", 17: "pread64", 18: "pwrite64",
         20: "writev", 21: "access", 22: "pipe", 32: "dup", 33: "dup2", 35: "nanosleep",
         39: "getpid", 56: "clone", 57: "fork", 59: "execve", 60: "exit", 61: "wait4",
         62: "kill", 72: "fcntl", 79: "getcwd", 80: "chdir", 82: "rename", 83: "mkdir",
         84: "rmdir", 87: "unlink", 88: "symlink", 89: "readlink", 102: "getuid",
         110: "getppid", 24: "sched_yield", 58: "vfork", 292: "dup3", 158: "arch_prctl", 186: "gettid", 201: "time", 217: "getdents64",
         228: "clock_gettime", 231: "exit_group", 257: "openat", 262: "newfstatat",
         200: "tkill", 234: "tgkill", 293: "pipe2", 318: "getrandom",
         41: "socket", 42: "connect", 43: "accept", 48: "shutdown", 49: "bind", 50: "listen",
         54: "setsockopt", 288: "accept4", 213: "epoll_create", 291: "epoll_create1",
         233: "epoll_ctl", 232: "epoll_wait", 281: "epoll_pwait", 283: "timerfd_create",
         0x1002: "ring_choose", 0x1003: "ring_await", 0x1000: "ring_malloc", 0x1001: "ring_free",
         286: "timerfd_settime", 287: "timerfd_gettime", 7: "poll", 290: "eventfd2"}
NUMBERS = {v: k for k, v in NAMES.items()}

SIGILL, SIGFPE, SIGKILL, SIGUSR1, SIGSEGV, SIGPIPE, SIGALRM, SIGTERM, SIGCHLD = 4, 8, 9, 10, 11, 13, 14, 15, 17
SIGINT = 2
SIG_DFL, SIG_IGN = 0, 1
SA_SIGINFO, SA_RESTART, SA_NODEFER, SA_RESETHAND, SA_RESTORER = 4, 0x10000000, 0x40000000, 0x80000000, 0x04000000
SIGNAL_NAMES = {1: "SIGHUP", 2: "SIGINT", 3: "SIGQUIT", 4: "SIGILL", 6: "SIGABRT", 8: "SIGFPE",
                9: "SIGKILL", 10: "SIGUSR1", 11: "SIGSEGV", 12: "SIGUSR2", 13: "SIGPIPE",
                14: "SIGALRM", 15: "SIGTERM", 17: "SIGCHLD"}
IGNORED_BY_DEFAULT = {SIGCHLD, 28, 23}   # SIGCHLD, SIGWINCH, SIGURG

# The game's checked allocator: private syscall numbers used by its malloc/free helpers.
SYS_RING_MALLOC, SYS_RING_FREE = 0x1000, 0x1001
SYS_RING_CHOOSE, SYS_RING_AWAIT = 0x1002, 0x1003   # the task runtime asks the game
CHECKED_HEAP = 0x10000000

HEAP_GAP = 0x1000          # first brk address = end of the program, page-aligned, + a gap
MMAP_BASE = 0x7FFFF7000000  # mmap regions grow down from here


class Block(Exception):
    """Raised by a syscall that must wait (an empty pipe, wait4 with live children).
    The process is parked with rip on its `syscall`, which runs again when it's
    scheduled next."""

    def __init__(self, why: str):
        self.why = why


class Exec(Exception):
    """Raised by a successful execve: the Machine loads the new image."""

    def __init__(self, image: bytes, path: str, argv: list[str], env: list[str]):
        self.image, self.path, self.argv, self.env = image, path, argv, env


class Exit(Exception):
    """Raised by the exit syscalls; carries the status."""

    def __init__(self, status: int):
        self.status = status


@dataclass
class Inode:
    kind: str                      # "file" | "dir" | "symlink"
    data: bytearray = field(default_factory=bytearray)
    target: str = ""               # for symlinks
    mode: int = 0o644
    ino: int = 0
    uid: int = 1000                # 0 = root: the user (uid 1000) may not access() it


@dataclass
class OpenFile:
    kind: str                      # "file" | "dir" | "stdin" | "stdout" | "stderr"
    path: str = ""
    readable: bool = False
    writable: bool = False
    append: bool = False
    pos: int = 0
    pipe: int = 0                  # for kind "pipe": which pipe
    node: Inode | None = None      # the file itself: renaming or replacing the path
                                   # doesn't change what an open descriptor refers to
    nonblock: bool = False         # O_NONBLOCK: EAGAIN instead of waiting
    ref: object = None             # sockets, timers, epoll: which kernel object
    addr: tuple | None = None      # a bound socket's address


PIPE_CAPACITY = 65536
FIRST_PID = 1000


@dataclass
class Proc:
    """Per-process kernel state."""
    pid: int
    ppid: int
    cwd: str = "/work"
    fds: dict[int, OpenFile] = field(default_factory=dict)
    cloexec: set[int] = field(default_factory=set)
    brk_start: int = 0
    brk: int = 0
    mmaps: dict[int, int] = field(default_factory=dict)     # address -> length
    mmap_next: int = MMAP_BASE
    actions: dict[int, tuple[int, int, int, int]] = field(default_factory=dict)  # sig -> handler, flags, restorer, mask
    blocked: int = 0
    pending: list[int] = field(default_factory=list)
    blocks: dict[int, dict] = field(default_factory=dict)  # checked heap: address -> {size, freed, alloc, free}
    checked_next: int = CHECKED_HEAP
    status: int | None = None      # wait status once it has terminated (a zombie until reaped)
    deadline: int | None = None    # a blocking call with a timeout gives up at this time
    command: str = ""


PER_PROCESS = ("cwd", "fds", "cloexec", "brk_start", "brk", "mmaps", "mmap_next", "actions",
               "blocked", "pending", "blocks", "checked_next")


@dataclass
class Injection:
    """Faults a test asks the kernel to inject."""
    fail: list[dict] = field(default_factory=list)     # {"call": "write", "nth": 2, "errno": 28}
    short_reads: bool = False      # read() returns fewer bytes than asked (1..max)
    short_writes: bool = False     # write() to stdout/stderr/files accepts fewer bytes
    signals: list[dict] = field(default_factory=list)  # {"at": instruction count, "sig": 2}
    fs_events: list[dict] = field(default_factory=list)  # another process changes files (see fs_event)
    quantum: int = 500             # instructions a process runs before the next one's turn
    peers: list[dict] = field(default_factory=list)  # scripted clients (see kernel_events)
    schedule: int = 0              # the game's task runtime: 0 = first ready task, else a seed
    cancel_at: int = 0             # cancel the task making the nth await (0 = never)
    seed: str = ""

    @classmethod
    def from_dict(cls, d: dict | None, seed: str) -> "Injection":
        d = d or {}
        return cls(fail=list(d.get("fail", [])), short_reads=d.get("short_reads", False),
                   short_writes=d.get("short_writes", False),
                   signals=list(d.get("signals", [])), fs_events=list(d.get("fs_events", [])),
                   quantum=d.get("quantum", 500), peers=list(d.get("peers", [])),
                   schedule=d.get("schedule", 0), cancel_at=d.get("cancel_at", 0), seed=seed)


class Kernel(EventsMixin):
    def __init__(self, stdin: bytes = b"", files: dict[str, bytes | str] | None = None,
                 inject: Injection | None = None, cwd: str = "/work"):
        self.machines: dict = {}      # pid -> Machine (outside snapshots)
        self.stdin = stdin
        self.stdin_pos = 0
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.inject = inject or Injection()
        self.rng = random.Random(f"kernel:{self.inject.seed}")
        self.calls: dict[str, int] = {}
        self.inodes: dict[str, Inode] = {}
        self.next_ino = 100
        for d in ("/", "/work", "/tmp", "/etc", "/home"):
            self._add(d, Inode("dir", mode=0o755))
        for path, content in (files or {}).items():
            if isinstance(content, dict):   # {"text"/"hex", "uid", "mode", "symlink"}
                if "symlink" in content:
                    self.make_file(path, symlink_to=content["symlink"])
                    continue
                data = bytes.fromhex(content["hex"]) if "hex" in content else content.get("text", "")
                self.make_file(path, data, uid=content.get("uid", 1000),
                               mode=content.get("mode", 0o644))
            else:
                self.make_file(path, content)
        self.time_ns = 1_700_000_000 * 10**9    # a fixed, deterministic clock
        self.writes: list[tuple[int, int, int]] = []   # (time_ns, fd, bytes) of every write
        self.pipes: dict[int, bytearray] = {}
        self.procs: dict[int, Proc] = {}
        self.next_pid = FIRST_PID
        self.proc = self.new_proc(FIRST_PID - 1)
        self.proc.cwd = cwd
        self.proc.fds = {0: OpenFile("stdin", readable=True), 1: OpenFile("stdout", writable=True),
                         2: OpenFile("stderr", writable=True)}
        self.events: list[str] = []             # what happened to processes, for reports
        self.fs_events: list[dict] = list(self.inject.fs_events)
        self.init_events(self.inject.peers)
        self.sched_rng = random.Random(f"schedule:{self.inject.schedule}")
        self.awaits: list[int] = []             # task id at each await point
        self.await_fns: list[int] = []          # ...and the function that task runs

    def new_proc(self, ppid: int) -> Proc:
        p = Proc(self.next_pid, ppid)
        self.procs[p.pid] = p
        self.next_pid += 1
        return p

    # ---- filesystem --------------------------------------------------------------------

    def _add(self, path: str, inode: Inode) -> Inode:
        inode.ino = self.next_ino
        self.next_ino += 1
        self.inodes[path] = inode
        return inode

    def make_file(self, path: str, content: bytes | str = b"", symlink_to: str | None = None,
                  uid: int = 1000, mode: int = 0o644) -> None:
        path = self.normalize(path)
        parent = path.rsplit("/", 1)[0] or "/"
        if parent not in self.inodes:
            self.make_dir(parent)
        if symlink_to is not None:
            self._add(path, Inode("symlink", target=symlink_to, mode=0o777))
        else:
            data = content.encode() if isinstance(content, str) else bytes(content)
            self._add(path, Inode("file", bytearray(data), mode=mode, uid=uid))

    def make_dir(self, path: str) -> None:
        path = self.normalize(path)
        parent = path.rsplit("/", 1)[0] or "/"
        if parent != path and parent not in self.inodes:
            self.make_dir(parent)
        self._add(path, Inode("dir", mode=0o755))

    def normalize(self, path: str, base: str | None = None) -> str:
        if not path.startswith("/"):
            path = (base or getattr(self, "cwd", "/")).rstrip("/") + "/" + path
        parts: list[str] = []
        for p in path.split("/"):
            if p in ("", "."):
                continue
            if p == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        return "/" + "/".join(parts)

    def resolve(self, path: str, follow: bool = True, depth: int = 0) -> tuple[str, Inode | None]:
        """Follow symlinks in every component (and the last one if `follow`)."""
        if depth > 8:
            raise OSError(ELOOP)
        path = self.normalize(path)
        parts = [p for p in path.split("/") if p]
        cur = "/"
        for i, p in enumerate(parts):
            nxt = self.normalize(p, cur)
            node = self.inodes.get(nxt)
            last = i == len(parts) - 1
            if node is not None and node.kind == "symlink" and (follow or not last):
                target = self.normalize(node.target, cur)
                rest = "/".join(parts[i + 1:])
                return self.resolve(target + ("/" + rest if rest else ""), follow, depth + 1)
            if not last and (node is None or node.kind != "dir"):
                raise OSError(ENOENT if node is None else ENOTDIR)
            cur = nxt
        return cur, self.inodes.get(cur)

    def file_text(self, path: str) -> bytes | None:
        node = self.inodes.get(self.normalize(path))
        return bytes(node.data) if node is not None and node.kind == "file" else None

    # ---- snapshots (for stepping backwards) -------------------------------------------------

    def snapshot(self) -> dict:
        return copy.deepcopy({k: v for k, v in self.__dict__.items()
                              if k not in ("stdin", "machines")})

    def restore(self, snap: dict) -> None:
        self.__dict__.update(copy.deepcopy(snap))
        for pid, m in self.machines.items():    # the machines keep using the restored Procs
            m.proc = self.procs.get(pid, m.proc)

    # ---- helpers ------------------------------------------------------------------------------

    def _injected(self, name: str) -> int | None:
        n = self.calls[name] = self.calls.get(name, 0) + 1
        for rule in self.inject.fail:
            if rule["call"] == name and rule.get("nth", 1) in (n, 0):
                return -rule["errno"]
        return None

    def _new_fd(self, f: OpenFile) -> int:
        fd = 0
        while fd in self.fds:
            fd += 1
        if fd >= 64:
            raise OSError(EMFILE)
        self.fds[fd] = f
        return fd

    def _cstring(self, m, addr: int, limit: int = 4096) -> str:
        out = bytearray()
        while len(out) < limit:
            if not m.readable(addr + len(out), 1):
                raise OSError(EFAULT)
            c = m.read(addr + len(out), 1)
            if c == b"\0":
                return out.decode("utf-8", "replace")
            out += c
        raise OSError(EINVAL)

    def _chunk(self, n: int, short: bool) -> int:
        if short and n > 1:
            return self.rng.randint(1, n)
        return n

    # ---- the syscall entry point ------------------------------------------------------------------

    def syscall(self, m, nr: int, args: tuple[int, ...]) -> int:
        name = NAMES.get(nr, f"syscall_{nr}")
        if name in ("exit", "exit_group"):
            raise Exit(args[0] & 0xFF)
        self.tick()
        injected = self._injected(name)
        if injected is not None:
            return injected
        if nr == SYS_RING_MALLOC:
            return self.ring_malloc(m, args[0])
        if nr == SYS_RING_FREE:
            return self.ring_free(m, args[0])
        if nr == SYS_RING_CHOOSE:      # which of n ready tasks runs next
            n = args[0]
            if self.inject.schedule == 0 or n <= 1:
                return 0
            return self.sched_rng.randrange(n)
        if nr == SYS_RING_AWAIT:       # a task reached an await point: cancel it here?
            self.awaits.append(args[0])
            self.await_fns.append(args[1])
            return int(len(self.awaits) == self.inject.cancel_at)
        handler = getattr(self, "sys_" + name, None)
        if handler is None:
            return -ENOSYS
        try:
            result = handler(m, *args)
        except OSError as e:
            result = -(e.args[0] if e.args and isinstance(e.args[0], int) else EINVAL)
        except Block:
            self.calls[name] -= 1     # it will be called again
            self.time_ns -= 1000      # ...and waiting isn't a syscall's worth of time
            raise
        self.proc.deadline = None
        return result

    def after_syscall(self, name: str) -> None:
        """Another process (the 'attacker' of a race level) changes the filesystem right
        after the current process's nth call of `name`."""
        for ev in list(self.fs_events):
            if ev["after"] == name and ev.get("nth", 1) == self.calls.get(name, 0) \
                    and self.proc.pid == FIRST_PID:
                self.fs_events.remove(ev)
                self.fs_event(ev)

    def fs_event(self, ev: dict) -> None:
        if "symlink" in ev:            # replace a path with a symlink: [path, target]
            path, target = ev["symlink"]
            self.inodes.pop(self.normalize(path), None)
            self.make_file(path, symlink_to=target)
        if "write" in ev:              # replace a path with a regular file: [path, text]
            path, text = ev["write"]
            self.inodes.pop(self.normalize(path), None)
            self.make_file(path, text)
        if "unlink" in ev:
            self.inodes.pop(self.normalize(ev["unlink"]), None)
        self.events.append(f"another process: {ev.get('describe', ev)}")

    # ---- file descriptors -------------------------------------------------------------------------

    def sys_read(self, m, fd, buf, count, *_):
        f = self.fds.get(fd)
        if f is None or not f.readable:
            return -EBADF
        if f.kind == "dir":
            return -EISDIR
        if f.kind == "conn":
            data = self.read_conn(f, fd, count)
        elif f.kind == "timer":
            data = self.read_timer(f, fd, count)
        elif f.kind in ("socket", "listen", "epoll"):
            return -EINVAL if f.kind != "socket" else -107   # ENOTCONN
        elif f.kind == "pipe":
            buf_ = self.pipes[f.pipe]
            if not buf_:
                if not self._pipe_has(f.pipe, writable=True):
                    return 0                                   # every write end is closed: EOF
                if f.nonblock:
                    return -EAGAIN
                raise Block(f"read from an empty pipe (fd {fd})")
            data = bytes(buf_[:self._chunk(min(count, len(buf_)), self.inject.short_reads)])
            del buf_[:len(data)]
        elif f.kind == "stdin":
            data = self.stdin[self.stdin_pos:self.stdin_pos + count]
            data = data[:self._chunk(len(data), self.inject.short_reads)]
            self.stdin_pos += len(data)
        else:
            node = f.node
            data = bytes(node.data[f.pos:f.pos + count]) if node else b""
            data = data[:self._chunk(len(data), self.inject.short_reads)]
            f.pos += len(data)
        if data:
            if not m.writable(buf, len(data)):
                return -EFAULT
            m.kernel_write(buf, data)
        return len(data)

    def sys_write(self, m, fd, buf, count, *_):
        f = self.fds.get(fd)
        if f is None or not f.writable:
            return -EBADF
        n = m.readable_prefix(buf, count)
        if count and (buf + count > m.USER_LIMIT or n == 0):
            return -EFAULT
        if f.kind == "pipe":
            if not self._pipe_has(f.pipe, writable=False):
                self.raise_signal(SIGPIPE)
                return -EPIPE
            room = PIPE_CAPACITY - len(self.pipes[f.pipe])
            if room == 0 and n:
                if f.nonblock:
                    return -EAGAIN
                raise Block(f"write to a full pipe (fd {fd})")
            n = min(n, room)
        elif f.kind == "conn":
            n = self.write_conn(f, fd, n)
        elif f.kind in ("socket", "listen", "epoll", "timer"):
            return -EINVAL if f.kind != "socket" else -107
        n = self._chunk(n, self.inject.short_writes)
        data = m.read(buf, n)  # like Linux: up to the first unreadable byte
        self.writes.append((self.time_ns, fd, n))
        if f.kind == "stdout":
            self.stdout += data
        elif f.kind == "stderr":
            self.stderr += data
        elif f.kind == "pipe":
            self.pipes[f.pipe] += data
        elif f.kind == "conn":
            self.conns[f.ref].to_client += data
        else:
            node = f.node
            if f.append:
                f.pos = len(node.data)
            if f.pos > len(node.data):
                node.data += bytes(f.pos - len(node.data))
            node.data[f.pos:f.pos + n] = data
            f.pos += n
        return n

    def sys_open(self, m, path, flags, mode, *_):
        return self.sys_openat(m, AT_FDCWD, path, flags, mode)

    def sys_openat(self, m, dirfd, path_addr, flags, mode, *_):
        path = self._cstring(m, path_addr)
        if dirfd != AT_FDCWD and not path.startswith("/"):
            d = self.fds.get(dirfd)
            if d is None:
                return -EBADF
            if d.kind != "dir":
                return -ENOTDIR
            path = d.path.rstrip("/") + "/" + path
        acc = flags & O_ACCMODE
        try:
            full, node = self.resolve(path, follow=not flags & O_NOFOLLOW)
        except OSError as e:
            return -e.args[0]
        if node is not None and node.kind == "symlink":   # O_NOFOLLOW on a symlink
            return -ELOOP
        if node is None:
            if not flags & O_CREAT:
                return -ENOENT
            parent = full.rsplit("/", 1)[0] or "/"
            if self.inodes.get(parent, Inode("file")).kind != "dir":
                return -ENOENT
            node = self._add(full, Inode("file", mode=mode & 0o777))
        elif flags & O_CREAT and flags & O_EXCL:
            return -EEXIST
        if node.kind == "dir":
            if acc != O_RDONLY:
                return -EISDIR
            fd = self._new_fd(OpenFile("dir", full, readable=True, node=node))
            if flags & O_CLOEXEC:
                self.cloexec.add(fd)
            return fd
        if flags & O_DIRECTORY:
            return -ENOTDIR
        if flags & O_TRUNC and acc != O_RDONLY:
            node.data.clear()
        fd = self._new_fd(OpenFile("file", full, readable=acc in (O_RDONLY, O_RDWR),
                                   writable=acc in (O_WRONLY, O_RDWR),
                                   append=bool(flags & O_APPEND), node=node))
        if flags & O_CLOEXEC:
            self.cloexec.add(fd)
        self.fds[fd].nonblock = bool(flags & 0o4000)
        return fd

    def sys_close(self, m, fd, *_):
        self.cloexec.discard(fd)
        f = self.fds.pop(fd, None)
        if f is None:
            return -EBADF
        self.file_closed(f)
        return 0

    def sys_lseek(self, m, fd, offset, whence, *_):
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        if f.kind != "file":
            return -ESPIPE
        offset = offset - (1 << 64) if offset >> 63 else offset
        size = len(f.node.data)
        base = {0: 0, 1: f.pos, 2: size}.get(whence)
        if base is None or base + offset < 0:
            return -EINVAL
        f.pos = base + offset
        return f.pos

    def _stat_bytes(self, node: Inode | None, kind: str) -> bytes:
        uid = 1000
        if kind == "pipe":
            mode, size, ino = S_IFIFO | 0o600, 0, 2
        elif kind in ("socket", "listen", "conn"):
            mode, size, ino = 0o140000 | 0o777, 0, 4
        elif kind in ("epoll", "timer"):
            mode, size, ino = 0o600, 0, 5
        elif node is None:  # a terminal
            mode, size, ino = S_IFCHR | 0o620, 0, 3
        else:
            mode = {"file": S_IFREG, "dir": S_IFDIR, "symlink": S_IFLNK}[node.kind] | node.mode
            size = len(node.target) if node.kind == "symlink" else len(node.data)
            ino, uid = node.ino, node.uid
        st = bytearray(144)
        struct.pack_into("<QQQIII", st, 0, 0x803, ino, 1, mode, uid, uid)
        struct.pack_into("<qqq", st, 48, size, 4096, (size + 511) // 512)
        for off in (72, 88, 104):
            struct.pack_into("<qq", st, off, self.time_ns // 10**9, 0)
        return bytes(st)

    def sys_fstat(self, m, fd, statbuf, *_):
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        node = f.node if f.kind in ("file", "dir") else None
        m.kernel_write(statbuf, self._stat_bytes(node, f.kind))
        return 0

    def sys_newfstatat(self, m, dirfd, path_addr, statbuf, flags, *_):
        path = self._cstring(m, path_addr)
        if not path and flags & AT_EMPTY_PATH:
            return self.sys_fstat(m, dirfd, statbuf)
        try:
            _, node = self.resolve(path, follow=not flags & AT_SYMLINK_NOFOLLOW)
        except OSError as e:
            return -e.args[0]
        if node is None:
            return -ENOENT
        m.kernel_write(statbuf, self._stat_bytes(node, node.kind))
        return 0

    def sys_stat(self, m, path, statbuf, *_):
        return self.sys_newfstatat(m, AT_FDCWD, path, statbuf, 0)

    def sys_lstat(self, m, path, statbuf, *_):
        return self.sys_newfstatat(m, AT_FDCWD, path, statbuf, AT_SYMLINK_NOFOLLOW)

    def sys_ioctl(self, m, fd, *_):
        return -EBADF if fd not in self.fds else -ENOTTY

    def sys_unlink(self, m, path_addr, *_):
        path = self.normalize(self._cstring(m, path_addr))
        node = self.inodes.get(path)
        if node is None:
            return -ENOENT
        if node.kind == "dir":
            return -EISDIR
        del self.inodes[path]
        return 0

    def sys_mkdir(self, m, path_addr, mode, *_):
        path = self.normalize(self._cstring(m, path_addr))
        if path in self.inodes:
            return -EEXIST
        if self.inodes.get(path.rsplit("/", 1)[0] or "/", Inode("file")).kind != "dir":
            return -ENOENT
        self._add(path, Inode("dir", mode=mode & 0o777))
        return 0

    def sys_getcwd(self, m, buf, size, *_):
        data = self.cwd.encode() + b"\0"
        if len(data) > size:
            return -ERANGE
        m.kernel_write(buf, data)
        return len(data)

    def sys_chdir(self, m, path_addr, *_):
        try:
            full, node = self.resolve(self._cstring(m, path_addr))
        except OSError as e:
            return -e.args[0]
        if node is None:
            return -ENOENT
        if node.kind != "dir":
            return -ENOTDIR
        self.cwd = full
        return 0

    # ---- memory ---------------------------------------------------------------------------------

    def sys_brk(self, m, addr, *_):
        if addr <= self.brk_start or addr > self.brk_start + (1 << 30):
            return self.brk                         # query (or refuse): current break
        m.resize_region(self.brk_start, self.brk, addr)
        self.brk = addr
        return self.brk

    def sys_mmap(self, m, addr, length, prot, flags, fd, offset):
        if length == 0:
            return -EINVAL
        length = (length + 0xFFF) & ~0xFFF
        fd = fd - (1 << 64) if fd >> 63 else fd
        MAP_ANONYMOUS, MAP_FIXED = 0x20, 0x10
        data = b""
        if not flags & MAP_ANONYMOUS:
            f = self.fds.get(fd)
            if f is None or f.kind != "file":
                return -EBADF
            data = bytes(f.node.data[offset:offset + length])
        if flags & MAP_FIXED:
            start = addr
        else:
            self.mmap_next -= length
            start = self.mmap_next
        m.map_region(start, length, prot, data)
        self.mmaps[start] = length
        return start

    def sys_munmap(self, m, addr, length, *_):
        if addr & 0xFFF:
            return -EINVAL
        length = (length + 0xFFF) & ~0xFFF
        m.unmap_region(addr, length)
        self.mmaps.pop(addr, None)
        return 0

    def sys_mprotect(self, m, addr, length, prot, *_):
        if addr & 0xFFF:
            return -EINVAL
        m.protect_region(addr, (length + 0xFFF) & ~0xFFF, prot)
        return 0

    # ---- misc ---------------------------------------------------------------------------------

    def sys_getpid(self, m, *_):
        return self.proc.pid

    def sys_getppid(self, m, *_):
        return self.proc.ppid

    def sys_getuid(self, m, *_):
        return 1000

    def sys_gettid(self, m, *_):
        return self.proc.pid

    def sys_clock_gettime(self, m, clock, tp, *_):
        m.kernel_write(tp, struct.pack("<qq", self.time_ns // 10**9, self.time_ns % 10**9))
        return 0

    def sys_nanosleep(self, m, req, rem, *_):
        sec, nsec = struct.unpack("<qq", m.read(req, 16))
        if nsec < 0 or nsec >= 10**9 or sec < 0:
            return -EINVAL
        self.time_ns += sec * 10**9 + nsec           # sleeping is instant, time still passes
        return 0

    def sys_getrandom(self, m, buf, count, *_):
        m.kernel_write(buf, self.rng.randbytes(count))
        return count

    def sys_arch_prctl(self, m, code, addr, *_):
        ARCH_SET_FS = 0x1002
        if code == ARCH_SET_FS:
            m.set_fs_base(addr)
            return 0
        return -EINVAL

    # ---- signals --------------------------------------------------------------------------------

    def sys_rt_sigaction(self, m, sig, act, oldact, sigsetsize, *_):
        if not 1 <= sig <= 64 or sig in (SIGKILL, 19) or sigsetsize != 8:
            return -EINVAL
        if oldact:
            old = self.actions.get(sig, (SIG_DFL, 0, 0, 0))
            m.kernel_write(oldact, struct.pack("<QQQQ", *old))
        if act:
            handler, flags, restorer, mask = struct.unpack("<QQQQ", m.read(act, 32))
            self.actions[sig] = (handler, flags, restorer, mask)
        return 0

    def sys_rt_sigprocmask(self, m, how, nset, oset, sigsetsize, *_):
        if sigsetsize != 8:
            return -EINVAL
        if oset:
            m.kernel_write(oset, struct.pack("<Q", self.blocked))
        if nset:
            mask = struct.unpack("<Q", m.read(nset, 8))[0] & ~((1 << (SIGKILL - 1)) | (1 << 18))
            if how == 0:
                self.blocked |= mask
            elif how == 1:
                self.blocked &= ~mask
            elif how == 2:
                self.blocked = mask
            else:
                return -EINVAL
        return 0

    def sys_kill(self, m, pid, sig, *_):
        if pid in (0, MASK64):
            pid = self.proc.pid
        target = self.procs.get(pid)
        if target is None or target.status is not None:
            return -ESRCH
        if not 0 <= sig <= 64:
            return -EINVAL
        if sig:
            self.signal_proc(target, sig)
        return 0

    def sys_tgkill(self, m, tgid, tid, sig, *_):
        return self.sys_kill(m, tgid, sig)

    def raise_signal(self, sig: int) -> None:
        self.signal_proc(self.proc, sig)

    def signal_proc(self, proc: Proc, sig: int) -> None:
        if sig not in proc.pending:
            proc.pending.append(sig)

    def next_deliverable(self) -> int | None:
        for sig in self.pending:
            if not self.blocked >> (sig - 1) & 1 or sig == SIGKILL:
                self.pending.remove(sig)
                return sig
        return None

    def deliverable_pending(self) -> int | None:
        """A pending, unblocked signal that isn't ignored (it interrupts a blocking call)."""
        for sig in list(self.pending):
            if self.blocked >> (sig - 1) & 1 and sig != SIGKILL:
                continue
            if self.disposition(sig) == "ignore":
                self.pending.remove(sig)
                continue
            return sig
        return None

    def disposition(self, sig: int) -> str:
        handler = self.actions.get(sig, (SIG_DFL,))[0]
        if sig == SIGKILL:
            return "kill"
        if handler == SIG_IGN or (handler == SIG_DFL and sig in IGNORED_BY_DEFAULT):
            return "ignore"
        return "kill" if handler == SIG_DFL else "handle"

    # ---- the game's checked allocator -------------------------------------------------------------

    def ring_malloc(self, m, size):
        """Never reuses memory; red zones around every block; freed blocks are poisoned
        and watched, so any later access is caught."""
        size = max(size, 1)
        if size > 1 << 24:
            return 0
        start = (self.checked_next + 16 + 15) & ~15
        end = start + size
        self.checked_next = end + 16
        m.ensure_checked_heap(self.checked_next)
        self.blocks[start] = {"size": size, "freed": False, "alloc": m.caller_line(),
                              "free": None}
        return start

    def ring_free(self, m, addr):
        if addr == 0:
            return 0
        b = self.blocks.get(addr)
        if b is None:
            m.memory_error(f"free() of {addr:#x}, which malloc never returned")
            return 0
        if b["freed"]:
            m.memory_error(f"double free of the block at {addr:#x} (allocated at {b['alloc']}, "
                           f"first freed at {b['free']})")
            return 0
        b["freed"] = True
        b["free"] = m.caller_line()
        m.kernel_write(addr, b"\xDD" * b["size"])
        return 0

    def checked_block(self, addr: int) -> tuple[int, dict] | None:
        last = getattr(self, "_last_block", None)          # accesses come in runs
        if last is not None and last[1] is self.blocks.get(last[0]) \
                and last[0] - 16 <= addr < last[0] + last[1]["size"] + 16:
            return last
        found = self._find_block(addr)
        if found is not None:
            self._last_block = found
        return found

    def _find_block(self, addr: int) -> tuple[int, dict] | None:
        # Blocks are handed out at increasing addresses, so the dict's keys are sorted.
        cache = getattr(self, "_block_starts", None)   # (the dict it was made from, its keys)
        if cache is None or cache[0] is not self.blocks or len(cache[1]) != len(self.blocks):
            cache = self._block_starts = (self.blocks, list(self.blocks))
        starts = cache[1]
        i = bisect.bisect_right(starts, addr + 16) - 1
        for start in starts[max(i - 1, 0):i + 2]:
            b = self.blocks[start]
            if start - 16 <= addr < start + b["size"] + 16:
                return start, b
        return None

    # ---- pipes and descriptors ------------------------------------------------------------------

    def _pipe_has(self, pipe: int, writable: bool) -> bool:
        """Does any live process still hold this pipe's write (or read) end?"""
        if writable and pipe in self.peer_pipes:
            return True
        for p in self.procs.values():
            if p.status is None:
                for f in p.fds.values():
                    if f.kind == "pipe" and f.pipe == pipe and (f.writable if writable else f.readable):
                        return True
        return False

    def sys_pipe(self, m, fds_addr, *_):
        return self.sys_pipe2(m, fds_addr, 0)

    def sys_pipe2(self, m, fds_addr, flags, *_):
        if flags & ~(O_CLOEXEC | 0o4000):
            return -EINVAL
        if not m.writable(fds_addr, 8):
            return -EFAULT
        n = len(self.pipes) + 1
        self.pipes[n] = bytearray()
        r = self._new_fd(OpenFile("pipe", f"pipe:[{n}]", readable=True, pipe=n))
        try:
            w = self._new_fd(OpenFile("pipe", f"pipe:[{n}]", writable=True, pipe=n))
        except OSError:
            del self.fds[r]
            raise
        if flags & O_CLOEXEC:
            self.cloexec |= {r, w}
        self.fds[r].nonblock = self.fds[w].nonblock = bool(flags & 0o4000)
        m.kernel_write(fds_addr, struct.pack("<ii", r, w))
        return 0

    def sys_dup(self, m, fd, *_):
        if fd not in self.fds:
            return -EBADF
        return self._new_fd(self.fds[fd])

    def sys_dup2(self, m, old, new, *_):
        if old not in self.fds:
            return -EBADF
        if new >= 64:
            return -EBADF
        if old != new:
            self.fds[new] = self.fds[old]
            self.cloexec.discard(new)
        return new

    def sys_dup3(self, m, old, new, flags, *_):
        if old == new or flags & ~O_CLOEXEC:
            return -EINVAL
        r = self.sys_dup2(m, old, new)
        if r >= 0 and flags & O_CLOEXEC:
            self.cloexec.add(new)
        return r

    def sys_fcntl(self, m, fd, cmd, arg, *_):
        F_DUPFD, F_GETFD, F_SETFD, F_GETFL, F_DUPFD_CLOEXEC = 0, 1, 2, 3, 1030
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        if cmd in (F_DUPFD, F_DUPFD_CLOEXEC):
            new = arg
            while new in self.fds:
                new += 1
            if new >= 64:
                return -EMFILE
            self.fds[new] = f
            if cmd == F_DUPFD_CLOEXEC:
                self.cloexec.add(new)
            return new
        if cmd == F_GETFD:
            return int(fd in self.cloexec)
        if cmd == F_SETFD:
            (self.cloexec.add if arg & 1 else self.cloexec.discard)(fd)
            return 0
        if cmd == F_GETFL:
            return (O_RDWR if f.readable and f.writable else O_WRONLY if f.writable else O_RDONLY) \
                | (O_APPEND if f.append else 0) | (0o4000 if f.nonblock else 0)
        if cmd == 4:                                    # F_SETFL: O_APPEND and O_NONBLOCK
            f.append, f.nonblock = bool(arg & O_APPEND), bool(arg & 0o4000)
            return 0
        return -EINVAL

    # ---- processes --------------------------------------------------------------------------------

    def sys_fork(self, m, *_):
        child = self.new_proc(self.proc.pid)
        for name in PER_PROCESS:
            setattr(child, name, copy.deepcopy(getattr(self.proc, name)))
        child.fds = dict(self.proc.fds)          # the open files themselves are shared
        child.pending = []
        child.command = self.proc.command
        m.fork(child)
        self.events.append(f"pid {self.proc.pid} forked pid {child.pid}")
        return child.pid

    def sys_vfork(self, m, *_):
        return self.sys_fork(m)

    def sys_clone(self, m, flags, stack, *_):
        CLONE_VM, CLONE_THREAD = 0x100, 0x10000
        if flags & (CLONE_VM | CLONE_THREAD) or stack:
            return -ENOSYS          # threads come later in the game
        return self.sys_fork(m)

    def _strings(self, m, addr: int) -> list[str]:
        out = []
        while addr:
            if not m.readable(addr + 8 * len(out), 8):
                raise OSError(EFAULT)
            ptr = struct.unpack("<Q", m.read(addr + 8 * len(out), 8))[0]
            if ptr == 0:
                return out
            out.append(self._cstring(m, ptr))
            if len(out) > 256:
                raise OSError(E2BIG)
        return out

    def sys_execve(self, m, path_addr, argv_addr, envp_addr, *_):
        path = self._cstring(m, path_addr)
        argv, env = self._strings(m, argv_addr), self._strings(m, envp_addr)
        try:
            full, node = self.resolve(path)
        except OSError as e:
            return -e.args[0]
        if node is None:
            return -ENOENT
        if node.kind == "dir":
            return -EACCES
        if not node.mode & 0o111:
            return -EACCES
        if bytes(node.data[:4]) != b"\x7fELF":
            return -ENOEXEC
        for fd in sorted(self.cloexec):
            f = self.fds.pop(fd, None)
            if f is not None:
                self.file_closed(f)
        self.cloexec = set()
        self.actions = {s: a for s, a in self.actions.items() if a[0] == SIG_IGN}
        self.mmaps, self.mmap_next, self.blocks = {}, MMAP_BASE, {}
        self.checked_next = CHECKED_HEAP
        self.proc.command = full
        self.events.append(f"pid {self.proc.pid} executed {full} {argv[1:]}")
        raise Exec(bytes(node.data), full, argv, env)

    def process_exit(self, proc: Proc, status: int) -> None:
        """A process terminated with a wait status: (code << 8) for exit(code), or the
        signal number when killed. Its files close; its parent gets SIGCHLD."""
        proc.status = status
        closed, proc.fds = proc.fds, {}
        proc.cloexec = set()
        for f in closed.values():
            self.file_closed(f)
        for p in self.procs.values():   # orphans are adopted (by "init", which reaps them)
            if p.ppid == proc.pid:
                p.ppid = 1
        parent = self.procs.get(proc.ppid)
        if parent is not None and parent.status is None:
            self.signal_proc(parent, SIGCHLD)
        else:
            self.procs.pop(proc.pid, None)  # nobody will wait for it

    def sys_wait4(self, m, pid, status_addr, options, rusage, *_):
        WNOHANG = 1
        pid = pid - (1 << 64) if pid >> 63 else pid
        kids = [p for p in self.procs.values() if p.ppid == self.proc.pid
                and (pid == -1 or p.pid == pid)]
        if not kids:
            return -ECHILD
        for k in kids:
            if k.status is not None:
                if status_addr:
                    if not m.writable(status_addr, 4):
                        return -EFAULT
                    m.kernel_write(status_addr, struct.pack("<i", k.status))
                del self.procs[k.pid]
                return k.pid
        if options & WNOHANG:
            return 0
        raise Block(f"wait4 for {'any child' if pid == -1 else f'pid {pid}'}")

    def sys_sched_yield(self, m, *_):
        m.yield_cpu()
        return 0

    # ---- more filesystem --------------------------------------------------------------------------

    def sys_access(self, m, path_addr, mode, *_):
        """Checks with the REAL user's rights (uid 1000), unlike open() in a privileged program."""
        try:
            _, node = self.resolve(self._cstring(m, path_addr))
        except OSError as e:
            return -e.args[0]
        if node is None:
            return -ENOENT
        if mode and node.uid != 1000 and not node.mode & 0o004:
            return -EACCES
        return 0

    def sys_readlink(self, m, path_addr, buf, size, *_):
        node = self.inodes.get(self.normalize(self._cstring(m, path_addr)))
        if node is None:
            return -ENOENT
        if node.kind != "symlink":
            return -EINVAL
        data = node.target.encode()[:size]
        m.kernel_write(buf, data)
        return len(data)

    def sys_symlink(self, m, target_addr, path_addr, *_):
        target, path = self._cstring(m, target_addr), self.normalize(self._cstring(m, path_addr))
        if path in self.inodes:
            return -EEXIST
        self.make_file(path, symlink_to=target)
        return 0

    def sys_rename(self, m, old_addr, new_addr, *_):
        old, new = self.normalize(self._cstring(m, old_addr)), self.normalize(self._cstring(m, new_addr))
        node = self.inodes.get(old)
        if node is None:
            return -ENOENT
        if node.kind == "dir":
            return -EXDEV            # keep directory renames out of the model
        self.inodes[new] = self.inodes.pop(old)
        return 0

    def sys_rmdir(self, m, path_addr, *_):
        path = self.normalize(self._cstring(m, path_addr))
        node = self.inodes.get(path)
        if node is None:
            return -ENOENT
        if node.kind != "dir":
            return -ENOTDIR
        if self._children(path):
            return -ENOTEMPTY
        del self.inodes[path]
        return 0

    def _children(self, path: str) -> list[str]:
        prefix = path.rstrip("/") + "/"
        return sorted(p[len(prefix):] for p in self.inodes
                      if p.startswith(prefix) and "/" not in p[len(prefix):] and p != path)

    def sys_getdents64(self, m, fd, buf, count, *_):
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        if f.kind != "dir":
            return -ENOTDIR
        names = [".", ".."] + self._children(f.path)
        out = bytearray()
        DT = {"dir": 4, "file": 8, "symlink": 10}
        while f.pos < len(names):
            name = names[f.pos]
            node = self.inodes.get(self.normalize(name, f.path))
            ino = node.ino if node else 1
            reclen = (19 + len(name.encode()) + 1 + 7) & ~7
            if len(out) + reclen > count:
                if not out:
                    return -EINVAL
                break
            rec = struct.pack("<QqHB", ino, f.pos + 1, reclen, DT.get(node.kind if node else "dir", 0))
            out += rec + name.encode() + bytes(reclen - len(rec) - len(name.encode()))
            f.pos += 1
        if out:
            if not m.writable(buf, len(out)):
                return -EFAULT
            m.kernel_write(buf, bytes(out))
        return len(out)


def _per_process(name: str) -> property:
    return property(lambda self: getattr(self.proc, name),
                    lambda self, value: setattr(self.proc, name, value))


for _name in PER_PROCESS:
    setattr(Kernel, _name, _per_process(_name))
