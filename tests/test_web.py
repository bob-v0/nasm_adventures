"""The web API, end to end over HTTP."""

import base64
import http.cookiejar
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from ring.web.server import Server, make_handler


@pytest.fixture
def ui():
    server = Server()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(server))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(route, body=None, token=server.token):
        req = urllib.request.Request(f"{base}/api/{route}?token={token}", method="POST",
                                     data=json.dumps(body or {}).encode())
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    call.base, call.token = base, server.token
    yield call
    httpd.shutdown()


def test_requires_token(ui):
    with pytest.raises(urllib.error.HTTPError) as e:
        ui("state", token="wrong")
    assert e.value.code == 403
    # The token moves from the URL into a cookie via a redirect.
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    with opener.open(f"{ui.base}/?token={ui.token}") as r:
        assert r.url == f"{ui.base}/"
        assert b"NASM Adventures" in r.read()
        assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
        assert r.headers["Referrer-Policy"] == "no-referrer"


def test_rejects_cross_origin_posts(ui):
    req = urllib.request.Request(f"{ui.base}/api/state?token={ui.token}", method="POST",
                                 data=b"{}", headers={"Origin": "https://evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403


def _ws_frame(payload: bytes) -> bytes:
    mask = b"\x01\x02\x03\x04"
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    assert len(payload) < 126
    return bytes([0x81, 0x80 | len(payload)]) + mask + masked


def test_terminal_runs_commands_in_the_level_folder(ui):
    ui("open", {"level": 184})
    host, port = ui.base.removeprefix("http://").split(":")
    sock = socket.create_connection((host, int(port)), timeout=10)
    key = base64.b64encode(b"0123456789abcdef").decode()
    sock.sendall((f"GET /ws/terminal?level=184&token={ui.token} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                  f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                  "Sec-WebSocket-Version: 13\r\n\r\n").encode())
    out = b""
    while b"\r\n\r\n" not in out:
        out += sock.recv(4096)
    assert out.startswith(b"HTTP/1.1 101")
    sock.sendall(_ws_frame(json.dumps({"type": "input", "data": "pwd; echo MARK$((6*7))\n"}).encode()))
    deadline = time.time() + 10
    while b"MARK42" not in out and time.time() < deadline:
        out += sock.recv(65536)
    sock.close()
    assert b"MARK42" in out and b"level184" in out


def test_play_first_level(ui):
    state = ui("state")
    assert state["current"] == 184
    lv = ui("open", {"level": 184})
    assert "Hello, NASM" in lv["brief"] and lv["tests"]

    bad = ui("test", {"level": 184, "text": "mov rax,\n"})
    assert bad["errors"][0]["line"] == 1

    good = "mov rax, 42\nmov rbx, 184\n"
    assert ui("test", {"level": 184, "text": good})["passed"]
    sub = ui("test", {"level": 184, "text": good, "submit": True})
    assert sub["opened"] and sub["next"]["number"] == 183
    assert ui("state")["current"] == 183


def test_debugger_round_trip(ui):
    ui("open", {"level": 184})
    view = ui("debug/start", {"level": 184, "text": "mov rax, 42\nmov rbx, 184\n"})
    sid = view["session"]
    assert view["line"] == 1 and not view["can_back"]
    view = ui("debug/cmd", {"session": sid, "cmd": "continue", "breakpoints": [2]})
    assert view["stop"] == "breakpoint" and view["line"] == 2
    rax = next(r for r in view["regs"] if r["name"] == "rax")
    assert int(rax["value"], 16) == 42 and rax["changed"]
    view = ui("debug/cmd", {"session": sid, "cmd": "back"})
    assert view["line"] == 1
    mem = ui("debug/memory", {"session": sid, "addr": "rsp", "length": 32})
    assert len(mem["rows"]) == 2


def test_sealed_levels_are_refused(ui):
    with pytest.raises(urllib.error.HTTPError) as e:
        ui("open", {"level": 171})
    assert e.value.code == 403


def test_debugger_shows_vector_registers(ui):
    ui("open", {"level": 184})
    view = ui("debug/start", {"level": 184, "text": "pcmpeqd xmm1, xmm1\nvpaddd ymm2, ymm1, ymm1\nnop\n"})
    sid = view["session"]
    assert view["vregs"] == []
    view = ui("debug/cmd", {"session": sid, "cmd": "continue", "breakpoints": [3]})
    regs = {r["name"]: r for r in view["vregs"]}
    assert regs["xmm1"]["value"] == " ".join(["ffffffff"] * 4)
    assert regs["xmm2"]["value"] == " ".join(["fffffffe"] * 4) and regs["xmm2"]["changed"]
