"""A shell in the browser: a pseudo-terminal bridged to xterm.js over a WebSocket.

Standard library only. The protocol is minimal RFC 6455: the client sends JSON text
frames ({"type": "input", "data": ...} or {"type": "resize", "cols": .., "rows": ..});
the server sends the terminal's raw output as binary frames.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import pty
import select
import signal
import struct
import subprocess
import termios
import threading
from pathlib import Path

_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1(key.encode() + _GUID).digest()).decode()


def _send_frame(wfile, opcode: int, payload: bytes, lock: threading.Lock) -> None:
    n = len(payload)
    if n < 126:
        header = struct.pack("!BB", 0x80 | opcode, n)
    elif n < 1 << 16:
        header = struct.pack("!BBH", 0x80 | opcode, 126, n)
    else:
        header = struct.pack("!BBQ", 0x80 | opcode, 127, n)
    with lock:
        wfile.write(header + payload)
        wfile.flush()


def _read_exact(rfile, n: int) -> bytes:
    data = rfile.read(n)
    if len(data) < n:
        raise ConnectionError("websocket closed")
    return data


def _read_frame(rfile) -> tuple[int, bytes]:
    b0, b1 = _read_exact(rfile, 2)
    opcode, masked, n = b0 & 0x0F, b1 & 0x80, b1 & 0x7F
    if n == 126:
        n = struct.unpack("!H", _read_exact(rfile, 2))[0]
    elif n == 127:
        n = struct.unpack("!Q", _read_exact(rfile, 8))[0]
    mask = _read_exact(rfile, 4) if masked else b"\0\0\0\0"
    data = bytearray(_read_exact(rfile, n))
    for i in range(n):
        data[i] ^= mask[i % 4]
    return opcode, bytes(data)


def _set_size(fd: int, cols: int, rows: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def run_terminal(rfile, wfile, cwd: Path, banner: str = "") -> None:
    """Serve one terminal session until the browser disconnects or the shell exits."""
    master, slave = pty.openpty()
    shell = os.environ.get("SHELL") or "/bin/bash"
    env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor")
    proc = subprocess.Popen([shell, "-i"], cwd=cwd, stdin=slave, stdout=slave, stderr=slave,
                            env=env, start_new_session=True, close_fds=True)
    os.close(slave)
    lock = threading.Lock()
    if banner:
        _send_frame(wfile, 2, banner.encode(), lock)

    def pump_output():
        try:
            while True:
                r, _, _ = select.select([master], [], [], 0.5)
                if proc.poll() is not None and not r:
                    break
                if r:
                    try:
                        data = os.read(master, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    _send_frame(wfile, 2, data, lock)
            _send_frame(wfile, 8, b"", lock)
        except (OSError, ConnectionError):
            pass

    reader = threading.Thread(target=pump_output, daemon=True)
    reader.start()
    try:
        while proc.poll() is None:
            opcode, data = _read_frame(rfile)
            if opcode == 8:  # close
                break
            if opcode == 9:  # ping
                _send_frame(wfile, 10, data, lock)
                continue
            if opcode not in (1, 2):
                continue
            msg = json.loads(data)
            if msg.get("type") == "input":
                os.write(master, msg["data"].encode())
            elif msg.get("type") == "resize":
                _set_size(master, int(msg["cols"]), int(msg["rows"]))
    except (OSError, ConnectionError, ValueError):
        pass
    finally:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        os.close(master)
        reader.join(timeout=1)
