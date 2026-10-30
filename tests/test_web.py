"""The web API, end to end over HTTP."""

import json
import threading
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
    with urllib.request.urlopen(f"{ui.base}/?token={ui.token}") as r:
        assert b"NASM Adventures" in r.read()


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
