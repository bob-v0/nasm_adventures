"""`ring ui`: the web front end, served locally by the engine.

A small JSON API over the same game actions as the CLI, plus the static page in
static/. Access requires a per-run token (printed at startup), because the API can
build and run code.
"""

from __future__ import annotations

import hmac
import json
import os
import mimetypes
import re
import secrets
import threading
import webbrowser
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import briefs, docs
from ..build import BuildError, _inspect
from ..checks import Report, grade
from ..debugger import Session
from ..emu import GPRS, FLAG_BITS
from ..game import build_solution, context, record_pass, setup_level, solution_path
from ..level import Level, all_levels
from ..progress import Progress, dev_mode

STATIC = Path(__file__).parent / "static"
MAX_BODY = 1 << 20  # source files are small; refuse anything bigger
SECURITY_HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
LOCK = threading.Lock()  # one engine, many requests: serialize everything


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class Server:
    def __init__(self, terminal: bool = True):
        self.terminal = terminal
        self.token = os.environ.get("RING_UI_TOKEN") or secrets.token_urlsafe(16)
        self.sessions: dict[str, tuple[Session, dict]] = {}

    # ---- helpers ------------------------------------------------------------------

    def level(self, number: int, prog: Progress) -> Level:
        levels = all_levels()
        if number not in levels:
            raise ApiError(404, f"level {number} does not exist yet")
        if not prog.unlocked(number):
            raise ApiError(403, f"level {number} is sealed")
        return levels[number]

    def save_text(self, lv: Level, prog: Progress, text: str | None) -> Path:
        setup_level(lv, prog)
        sol = solution_path(lv)
        if text is not None:
            sol.write_text(text)
        return sol

    # ---- API ----------------------------------------------------------------------

    def state(self, prog: Progress, body: dict) -> dict:
        levels = []
        for n, lv in sorted(all_levels().items(), reverse=True):
            unlocked = prog.unlocked(n)
            levels.append({"number": n, "title": lv.title if unlocked else None, "arc": lv.arc,
                           "bug": lv.data.get("bug"), "boss": lv.data.get("boss", False),
                           "unlocked": unlocked, "completed": prog.completed(n),
                           "current": n == prog.current})
        return {"current": prog.current, "heat": prog.heat, "badges": prog.data["badges"],
                "cleared": len(prog.data["completed"]), "levels": levels, "dev": dev_mode(),
                "terminal": self.terminal}

    def open_level(self, prog: Progress, body: dict) -> dict:
        lv = self.level(int(body["level"]), prog)
        sol = self.save_text(lv, prog, None)
        tests = lv.all_tests(context(prog), include_hidden=False)
        extra = sorted(p.name for p in sol.parent.iterdir()
                       if p.is_file() and p.stat().st_mode & 0o111)
        used = prog.hints_used(lv.number)
        return {"number": lv.number, "title": lv.title, "arc": lv.arc, "mode": lv.mode,
                "bug": lv.data.get("bug"), "boss": lv.data.get("boss", False),
                "brief": briefs.render(lv.brief, "web"), "introduces": lv.introduces, "text": sol.read_text(),
                "path": str(sol), "tests": [t.name for t in tests],
                "hints": {"count": len(lv.hints),
                          "revealed": {str(i): briefs.render(lv.hints[i - 1], "web") for i in used}},
                "binaries": extra, "completed": prog.completed(lv.number)}

    def save(self, prog: Progress, body: dict) -> dict:
        lv = self.level(int(body["level"]), prog)
        self.save_text(lv, prog, body["text"])
        return {"saved": True}

    def reset(self, prog: Progress, body: dict) -> dict:
        lv = self.level(int(body["level"]), prog)
        setup_level(lv, prog, force=True)
        return {"text": solution_path(lv).read_text()}

    def run_tests(self, prog: Progress, body: dict) -> dict:
        lv = self.level(int(body["level"]), prog)
        submit = bool(body.get("submit"))
        sol = self.save_text(lv, prog, body.get("text"))
        try:
            b = build_solution(lv, sol)
        except BuildError as e:
            return {"build_error": str(e), "errors": _error_lines(str(e))}
        report = grade(lv, b, lv.all_tests(context(prog), include_hidden=submit), context(prog))
        out = _report_json(report, show_hidden_names=dev_mode())
        out["warnings"] = report.warnings
        out["errors"] = _error_lines(report.warnings)
        out["submitted"] = submit
        if submit and report.passed:
            result = record_pass(prog, lv, report)
            out["opened"] = True
            out["badges"] = result.badges
            out["next"] = ({"number": result.next_level.number, "title": result.next_level.title}
                           if result.next_level else None)
        return out

    def hint(self, prog: Progress, body: dict) -> dict:
        lv = self.level(int(body["level"]), prog)
        n = int(body["n"])
        if not 1 <= n <= len(lv.hints):
            raise ApiError(400, "no such hint")
        heat = prog.use_hint(lv.number, n)
        return {"n": n, "text": briefs.render(lv.hints[n - 1], "web"), "heat_added": heat, "heat": prog.heat}

    def docs(self, prog: Progress, body: dict) -> dict:
        term = body.get("q", "").strip()
        return {"text": docs.lookup(term) if term else docs.index()}

    def listing(self, prog: Progress, body: dict) -> dict:
        lv = self.level(int(body["level"]), prog)
        sol = self.save_text(lv, prog, body.get("text"))
        try:
            return {"listing": build_solution(lv, sol).listing}
        except BuildError as e:
            return {"build_error": str(e), "errors": _error_lines(str(e))}

    # ---- debugger -------------------------------------------------------------------

    def debug_start(self, prog: Progress, body: dict) -> dict:
        lv = self.level(int(body["level"]), prog)
        sol = self.save_text(lv, prog, body.get("text"))
        binary = body.get("binary")
        if binary:
            elf = (sol.parent / binary).resolve()
            if elf.parent != sol.parent.resolve() or not elf.is_file():
                raise ApiError(400, "no such program in this level's folder")
            b = _inspect(elf, elf, "program")
            session = Session(b)
            source_lines: list[str] = []
        else:
            try:
                b = build_solution(lv, sol)
            except BuildError as e:
                return {"build_error": str(e), "errors": _error_lines(str(e))}
            tests = lv.all_tests(context(prog), include_hidden=False)
            test = next((t for t in tests if t.name == body.get("test")), tests[0] if tests else None)
            session = Session(b, test, poison=lv.constraints.get("poison", False))
            source_lines = sol.read_text().splitlines()
        sid = secrets.token_hex(8)
        self.sessions = dict(list(self.sessions.items())[-7:])  # keep a few
        self.sessions[sid] = (session, {"prev": session.m.regs(), "binary": bool(binary)})
        out = self.debug_view(sid)
        out["session"] = sid
        out["source_lines"] = len(source_lines)
        return out

    def debug_cmd(self, prog: Progress, body: dict) -> dict:
        sid = body["session"]
        if sid not in self.sessions:
            raise ApiError(404, "debug session expired; start it again")
        s, meta = self.sessions[sid]
        s.breakpoints = set()
        for spec in body.get("breakpoints", [])[:64]:
            try:
                s.breakpoints.add(s.resolve_breakpoint(str(spec)))
            except (ValueError, KeyError):
                pass  # unknown label or no code at that line: ignore
        meta["prev"] = s.m.regs()
        cmd = body["cmd"]
        stop = None
        if cmd == "step":
            s.step(1)
        elif cmd == "line":
            s.step_line()
        elif cmd == "back":
            s.back(1)
        elif cmd == "continue":
            stop = s.cont()
        elif cmd == "rcontinue":
            stop = s.reverse_cont()
        elif cmd == "restart":
            s.restart()
        elif cmd != "view":
            raise ApiError(400, f"unknown command {cmd}")
        out = self.debug_view(sid)
        out["stop"] = stop
        return out

    def debug_memory(self, prog: Progress, body: dict) -> dict:
        s, _ = self.sessions.get(body["session"], (None, None))
        if s is None:
            raise ApiError(404, "debug session expired")
        try:
            addr = s.eval_address(body["addr"])
        except ValueError:
            raise ApiError(400, f"can't read address {body['addr']!r}")
        n = max(16, min(int(body.get("length", 128)), 1024))
        rows = []
        for off in range(0, n, 16):
            a = addr + off
            if not s.m.readable(a, 16):
                rows.append({"addr": f"{a:#x}", "hex": None, "label": None})
                continue
            data = s.m.read(a, 16)
            rows.append({"addr": f"{a:#x}", "hex": data.hex(" "),
                         "ascii": "".join(chr(c) if 32 <= c < 127 else "." for c in data),
                         "label": s.build.symbol_at(a)})
        return {"rows": rows}

    def debug_view(self, sid: str) -> dict:
        s, meta = self.sessions[sid]
        m = s.m
        regs = m.regs()
        prev = meta["prev"]
        flags = regs["rflags"]
        stack = []
        rsp = regs["rsp"]
        for i in range(8):
            a = rsp + 8 * i
            v = int.from_bytes(m.read(a, 8), "little") if m.readable(a, 8) else None
            stack.append({"addr": f"{a:#x}", "value": None if v is None else f"{v:#018x}",
                          "label": None if v is None else s.build.symbol_at(v)})
        disasm = []
        for a, raw, text in s.disasm(m.pc, 10):
            disasm.append({"addr": f"{a:#x}", "bytes": raw.hex(" "), "text": text,
                           "line": s.line(a), "current": a == m.pc})
        return {
            "state": m.state, "fault": m.fault, "exit_code": m.exit_code, "steps": m.steps,
            "can_back": bool(m.history), "line": s.line(), "rip": f"{m.pc:#x}",
            "where": s.build.symbol_at(m.pc), "test": s.test.name if s.test.name != "debug" else None,
            "regs": [{"name": n, "value": f"{regs[n]:016x}", "changed": regs[n] != prev.get(n)}
                     for n in GPRS + ["rip"]],
            "flags": [{"name": n, "set": bool(flags >> b & 1),
                       "changed": (flags ^ prev.get("rflags", flags)) >> b & 1 == 1}
                      for n, b in FLAG_BITS if n not in ("TF", "IF")],
            "stack": stack, "disasm": disasm,
            "stdout": bytes(m.stdout).decode("utf-8", "replace"),
            "stderr": bytes(m.stderr).decode("utf-8", "replace"),
            "syscalls": [str(x) for x in m.syscalls[-12:]],
            "symbols": sorted(n for n in s.build.symbols
                              if not n.startswith("__") and n not in ("_edata", "_end")),
        }

    ROUTES = {
        "state": state, "open": open_level, "save": save, "reset": reset, "test": run_tests,
        "hint": hint, "docs": docs, "listing": listing, "debug/start": debug_start,
        "debug/cmd": debug_cmd, "debug/memory": debug_memory,
    }


def _error_lines(text: str) -> list[dict]:
    out = []
    for m in re.finditer(r"solution\.asm:(\d+): (error|warning): (.*)(?:\n    why: (.*))?", text):
        out.append({"line": int(m.group(1)), "kind": m.group(2), "message": m.group(3),
                    "why": m.group(4)})
    return out


def _report_json(report: Report, show_hidden_names: bool) -> dict:
    public = [t for t in report.tests if not t.hidden]
    hidden = [t for t in report.tests if t.hidden]
    failed_hidden = [t for t in hidden if not t.passed]
    return {
        "passed": report.passed,
        "tests": [{"name": t.name, "passed": t.passed, "problems": t.problems} for t in public],
        "hidden": {"total": len(hidden), "passed": len(hidden) - len(failed_hidden),
                   "first_failure": ({"name": failed_hidden[0].name if show_hidden_names else "a hidden test",
                                      "problem": failed_hidden[0].problems[0]}
                                     if failed_hidden else None)},
        "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in report.checks],
        "stretch": [{"name": c.name, "passed": c.passed, "detail": c.detail}
                    for c in report.stretch] if report.passed else [],
        "instructions": len(report.instructions),
    }


def make_handler(server: Server):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # required for WebSocket upgrades; we always send Content-Length

        def log_message(self, fmt, *args):  # quiet
            pass

        def _authorized(self) -> bool:
            q = parse_qs(urlparse(self.path).query)
            if hmac.compare_digest(q.get("token", [""])[0], server.token):
                return True
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return "ring_token" in cookie and hmac.compare_digest(cookie["ring_token"].value,
                                                                  server.token)

        def _same_origin(self) -> bool:
            """Browsers send Origin on WebSocket and fetch POSTs; it must be us."""
            origin = self.headers.get("Origin")
            return origin is None or urlparse(origin).netloc == self.headers.get("Host")

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in SECURITY_HEADERS.items():
                self.send_header(k, v)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if urlparse(self.path).path == "/ws/terminal":
                return self._terminal()
            if not self._authorized():
                msg = b"NASM Adventures: open the link printed by `ring ui` (it contains your access token)."
                return self._send(HTTPStatus.FORBIDDEN, msg, "text/plain; charset=utf-8")
            path = urlparse(self.path).path
            cookie = f"ring_token={server.token}; HttpOnly; SameSite=Strict; Path=/"
            if "token=" in (urlparse(self.path).query or ""):
                # Move the token from the URL into a cookie, so it doesn't linger in
                # history, screenshots or Referer headers.
                return self._send(HTTPStatus.SEE_OTHER, b"", "text/plain",
                                  {"Location": path or "/", "Set-Cookie": cookie})
            name = "index.html" if path in ("/", "") else path.lstrip("/")
            f = (STATIC / name).resolve()
            if STATIC.resolve() not in f.parents or not f.is_file():
                return self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
            ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self._send(200, f.read_bytes(), ctype)

        def _terminal(self):
            from .terminal import accept_key, run_terminal
            if (not server.terminal or not self._authorized() or not self._same_origin()
                    or self.headers.get("Upgrade", "").lower() != "websocket"):
                return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
            q = parse_qs(urlparse(self.path).query)
            try:
                with LOCK:
                    prog = Progress.load()
                    lv = server.level(int(q.get("level", ["0"])[0]), prog)
                    setup_level(lv, prog)
                    cwd = solution_path(lv).parent
            except (ApiError, ValueError):
                return self._send(HTTPStatus.FORBIDDEN, b"no such level", "text/plain")
            self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept_key(self.headers["Sec-WebSocket-Key"]))
            self.end_headers()
            self.close_connection = True
            banner = (f"\x1b[2mLevel {lv.number} folder: {cwd}\r\n"
                      "Programs you build appear here as ./solution after Test or Submit.\x1b[0m\r\n")
            run_terminal(self.rfile, self.wfile, cwd, banner)

        def do_POST(self):
            if not self._authorized():
                return self._send(HTTPStatus.FORBIDDEN, b'{"error":"forbidden"}', "application/json")
            if not self._same_origin():
                return self._send(HTTPStatus.FORBIDDEN, b'{"error":"cross-origin request"}', "application/json")
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY:
                return self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, b'{"error":"request too large"}', "application/json")
            route = urlparse(self.path).path.removeprefix("/api/")
            fn = Server.ROUTES.get(route)
            if fn is None:
                return self._send(404, b'{"error":"no such endpoint"}', "application/json")
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                with LOCK:
                    prog = Progress.load()
                    result = fn(server, prog, body)
                status = 200
            except ApiError as e:
                result, status = {"error": str(e)}, e.status
            except Exception as e:  # report, don't kill the server
                result, status = {"error": f"{type(e).__name__}: {e}"}, 500
            self._send(status, json.dumps(result).encode(), "application/json")

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8080, open_browser: bool = True,
          terminal: bool = True) -> None:
    server = Server(terminal=terminal)
    httpd = ThreadingHTTPServer((host, port), make_handler(server))
    shown = "localhost" if host in ("0.0.0.0", "127.0.0.1", "::") else host
    url = f"http://{shown}:{port}/?token={server.token}"
    print(f"NASM Adventures is running. Open this link in your browser:\n\n    {url}\n")
    print("(Ctrl+C to stop.)", flush=True)
    if open_browser:
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
