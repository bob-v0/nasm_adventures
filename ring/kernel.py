"""A small emulated Linux kernel for the emulator: a virtual filesystem, file
descriptors, memory syscalls, and fault injection (failing syscalls, short reads),
so levels can test what real programs must survive.

The kernel works on one process (the Machine). Its state is plain Python data, so
the debugger can snapshot it at each syscall and step backwards across syscalls.
"""

from __future__ import annotations

import copy
import random
import struct
from dataclasses import dataclass, field

MASK64 = (1 << 64) - 1

# errno values (Linux x86-64)
EPERM, ENOENT, EINTR, EIO, EBADF, EAGAIN, ENOMEM, EACCES, EFAULT = 1, 2, 4, 5, 9, 11, 12, 13, 14
EEXIST, ENOTDIR, EISDIR, EINVAL, EMFILE, ENOTTY, ENOSPC, ESPIPE = 17, 20, 21, 22, 24, 25, 28, 29
ERANGE, ENOSYS, ENOTEMPTY, ELOOP = 34, 38, 39, 40
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
         110: "getppid", 158: "arch_prctl", 186: "gettid", 201: "time", 217: "getdents64",
         228: "clock_gettime", 231: "exit_group", 257: "openat", 262: "newfstatat",
         293: "pipe2", 318: "getrandom"}
NUMBERS = {v: k for k, v in NAMES.items()}

HEAP_GAP = 0x1000          # first brk address = end of the program, page-aligned, + a gap
MMAP_BASE = 0x7FFFF7000000  # mmap regions grow down from here


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


@dataclass
class OpenFile:
    kind: str                      # "file" | "dir" | "stdin" | "stdout" | "stderr"
    path: str = ""
    readable: bool = False
    writable: bool = False
    append: bool = False
    pos: int = 0


@dataclass
class Injection:
    """Faults a test asks the kernel to inject."""
    fail: list[dict] = field(default_factory=list)     # {"call": "write", "nth": 2, "errno": 28}
    short_reads: bool = False      # read() returns fewer bytes than asked (1..max)
    short_writes: bool = False     # write() to stdout/stderr/files accepts fewer bytes
    seed: str = ""

    @classmethod
    def from_dict(cls, d: dict | None, seed: str) -> "Injection":
        d = d or {}
        return cls(fail=list(d.get("fail", [])), short_reads=d.get("short_reads", False),
                   short_writes=d.get("short_writes", False), seed=seed)


class Kernel:
    def __init__(self, stdin: bytes = b"", files: dict[str, bytes | str] | None = None,
                 inject: Injection | None = None, cwd: str = "/work"):
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
            self.make_file(path, content)
        self.cwd = cwd
        self.fds: dict[int, OpenFile] = {0: OpenFile("stdin", readable=True),
                                         1: OpenFile("stdout", writable=True),
                                         2: OpenFile("stderr", writable=True)}
        self.brk_start = self.brk = 0
        self.mmaps: dict[int, int] = {}          # address -> length
        self.mmap_next = MMAP_BASE
        self.time_ns = 1_700_000_000 * 10**9    # a fixed, deterministic clock

    # ---- filesystem --------------------------------------------------------------------

    def _add(self, path: str, inode: Inode) -> Inode:
        inode.ino = self.next_ino
        self.next_ino += 1
        self.inodes[path] = inode
        return inode

    def make_file(self, path: str, content: bytes | str = b"", symlink_to: str | None = None) -> None:
        path = self.normalize(path)
        parent = path.rsplit("/", 1)[0] or "/"
        if parent not in self.inodes:
            self.make_dir(parent)
        if symlink_to is not None:
            self._add(path, Inode("symlink", target=symlink_to, mode=0o777))
        else:
            data = content.encode() if isinstance(content, str) else bytes(content)
            self._add(path, Inode("file", bytearray(data)))

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
        return copy.deepcopy({k: v for k, v in self.__dict__.items() if k != "stdin"})

    def restore(self, snap: dict) -> None:
        self.__dict__.update(copy.deepcopy(snap))

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
        injected = self._injected(name)
        if injected is not None:
            return injected
        handler = getattr(self, "sys_" + name, None)
        if handler is None:
            return -ENOSYS
        try:
            return handler(m, *args)
        except OSError as e:
            return -(e.args[0] if e.args and isinstance(e.args[0], int) else EINVAL)

    # ---- file descriptors -------------------------------------------------------------------------

    def sys_read(self, m, fd, buf, count, *_):
        f = self.fds.get(fd)
        if f is None or not f.readable:
            return -EBADF
        if f.kind == "dir":
            return -EISDIR
        if f.kind == "stdin":
            data = self.stdin[self.stdin_pos:self.stdin_pos + count]
            data = data[:self._chunk(len(data), self.inject.short_reads)]
            self.stdin_pos += len(data)
        else:
            node = self.inodes.get(f.path)
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
        n = self._chunk(n, self.inject.short_writes)
        data = m.read(buf, n)  # like Linux: up to the first unreadable byte
        if f.kind == "stdout":
            self.stdout += data
        elif f.kind == "stderr":
            self.stderr += data
        else:
            node = self.inodes[f.path]
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
            return self._new_fd(OpenFile("dir", full, readable=True))
        if flags & O_DIRECTORY:
            return -ENOTDIR
        if flags & O_TRUNC and acc != O_RDONLY:
            node.data.clear()
        return self._new_fd(OpenFile("file", full, readable=acc in (O_RDONLY, O_RDWR),
                                     writable=acc in (O_WRONLY, O_RDWR),
                                     append=bool(flags & O_APPEND)))

    def sys_close(self, m, fd, *_):
        return 0 if self.fds.pop(fd, None) is not None else -EBADF

    def sys_lseek(self, m, fd, offset, whence, *_):
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        if f.kind != "file":
            return -ESPIPE
        offset = offset - (1 << 64) if offset >> 63 else offset
        size = len(self.inodes[f.path].data)
        base = {0: 0, 1: f.pos, 2: size}.get(whence)
        if base is None or base + offset < 0:
            return -EINVAL
        f.pos = base + offset
        return f.pos

    def _stat_bytes(self, node: Inode | None, kind: str) -> bytes:
        if node is None:  # a terminal
            mode, size, ino = S_IFCHR | 0o620, 0, 3
        else:
            mode = {"file": S_IFREG, "dir": S_IFDIR, "symlink": S_IFLNK}[node.kind] | node.mode
            size = len(node.target) if node.kind == "symlink" else len(node.data)
            ino = node.ino
        st = bytearray(144)
        struct.pack_into("<QQQIII", st, 0, 0x803, ino, 1, mode, 1000, 1000)
        struct.pack_into("<qqq", st, 48, size, 4096, (size + 511) // 512)
        for off in (72, 88, 104):
            struct.pack_into("<qq", st, off, self.time_ns // 10**9, 0)
        return bytes(st)

    def sys_fstat(self, m, fd, statbuf, *_):
        f = self.fds.get(fd)
        if f is None:
            return -EBADF
        node = self.inodes.get(f.path) if f.kind in ("file", "dir") else None
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
            data = bytes(self.inodes[f.path].data[offset:offset + length])
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
        return 1000

    def sys_getppid(self, m, *_):
        return 999

    def sys_getuid(self, m, *_):
        return 1000

    def sys_gettid(self, m, *_):
        return 1000

    def sys_clock_gettime(self, m, clock, tp, *_):
        self.time_ns += 1000                         # time moves forward a little per call
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
