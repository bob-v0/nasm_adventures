"""Debug Adapter Protocol server over stdio (`ring dap`).

Supports stepping, step-back / reverse-continue, line and instruction breakpoints,
registers/flags as variables, readMemory and disassemble. VS Code (and later the web
UI) talk to this. Launch arguments: {"level": 184, "test": "<test name>"?, "stopOnEntry": true}.
"""

from __future__ import annotations

import base64
import json
import sys
from typing import BinaryIO

from .emu import FLAG_BITS, GPRS
from .debugger import Session

THREAD_ID = 1
REGS_REF, FLAGS_REF, OUTPUT_REF = 1, 2, 3


class DapServer:
    def __init__(self, inp: BinaryIO, out: BinaryIO, session_factory):
        self.inp, self.out = inp, out
        self.session_factory = session_factory  # (launch_args) -> Session
        self.s: Session | None = None
        self.seq = 1
        self.pending_lines: dict[str, list[int]] = {}
        self.instruction_bps: set[int] = set()
        self.line_bps: set[int] = set()
        self.running = True

    # -- framing ------------------------------------------------------------------

    def read_message(self) -> dict | None:
        headers = {}
        while True:
            line = self.inp.readline()
            if not line:
                return None
            line = line.decode().strip()
            if not line:
                break
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
        body = self.inp.read(int(headers["content-length"]))
        return json.loads(body)

    def send(self, msg: dict) -> None:
        msg["seq"] = self.seq
        self.seq += 1
        data = json.dumps(msg).encode()
        self.out.write(f"Content-Length: {len(data)}\r\n\r\n".encode() + data)
        self.out.flush()

    def respond(self, req: dict, body: dict | None = None, success: bool = True,
                message: str | None = None) -> None:
        msg = {"type": "response", "request_seq": req["seq"], "command": req["command"],
               "success": success, "body": body or {}}
        if message:
            msg["message"] = message
        self.send(msg)

    def event(self, name: str, body: dict | None = None) -> None:
        self.send({"type": "event", "event": name, "body": body or {}})

    # -- main loop --------------------------------------------------------------------

    def serve(self) -> None:
        while self.running:
            req = self.read_message()
            if req is None:
                return
            handler = getattr(self, "on_" + req["command"], None)
            if handler is None:
                self.respond(req, success=False, message=f"unsupported: {req['command']}")
                continue
            try:
                handler(req, req.get("arguments", {}))
            except Exception as e:  # report to client rather than crash the adapter
                self.respond(req, success=False, message=str(e))

    # -- requests ---------------------------------------------------------------------

    def on_initialize(self, req, args):
        self.respond(req, {
            "supportsConfigurationDoneRequest": True,
            "supportsStepBack": True,
            "supportsReadMemoryRequest": True,
            "supportsDisassembleRequest": True,
            "supportsInstructionBreakpoints": True,
            "supportsSteppingGranularity": True,
            "supportsRestartRequest": True,
            "supportsEvaluateForHovers": True,
        })

    def on_launch(self, req, args):
        self.s = self.session_factory(args)
        self.stop_on_entry = args.get("stopOnEntry", True)
        self.respond(req)
        self.event("initialized")

    def on_setBreakpoints(self, req, args):
        results = []
        self.line_bps = set()
        for bp in args.get("breakpoints", []):
            try:
                addr = self.s.resolve_breakpoint(str(bp["line"]))
                self.line_bps.add(addr)
                results.append({"verified": True, "line": self.s.line(addr)})
            except ValueError as e:
                results.append({"verified": False, "message": str(e)})
        self._sync_breakpoints()
        self.respond(req, {"breakpoints": results})

    def on_setInstructionBreakpoints(self, req, args):
        self.instruction_bps = {int(b["instructionReference"], 0) + b.get("offset", 0)
                                for b in args.get("breakpoints", [])}
        self._sync_breakpoints()
        self.respond(req, {"breakpoints": [{"verified": True} for _ in self.instruction_bps]})

    def _sync_breakpoints(self):
        self.s.breakpoints = self.line_bps | self.instruction_bps

    def on_setExceptionBreakpoints(self, req, args):
        self.respond(req, {"breakpoints": []})

    def on_configurationDone(self, req, args):
        self.respond(req)
        if self.stop_on_entry:
            self.stopped("entry")
        else:
            self._after_run(self.s.cont())

    def on_threads(self, req, args):
        self.respond(req, {"threads": [{"id": THREAD_ID, "name": "cpu0"}]})

    def on_stackTrace(self, req, args):
        m = self.s.m
        line = self.s.line()
        frame = {"id": 1, "name": self.s.build.symbol_at(m.pc) or f"{m.pc:#x}",
                 "line": line or 0, "column": 1, "instructionPointerReference": hex(m.pc)}
        if line:
            frame["source"] = {"name": self.s.build.source.name, "path": str(self.s.build.source)}
        self.respond(req, {"stackFrames": [frame], "totalFrames": 1})

    def on_scopes(self, req, args):
        self.respond(req, {"scopes": [
            {"name": "Registers", "variablesReference": REGS_REF, "expensive": False},
            {"name": "Flags", "variablesReference": FLAGS_REF, "expensive": False},
            {"name": "Output", "variablesReference": OUTPUT_REF, "expensive": False},
        ]})

    def on_variables(self, req, args):
        m = self.s.m
        ref = args["variablesReference"]
        if ref == REGS_REF:
            vs = [{"name": n, "value": f"{m.reg(n):#018x}", "variablesReference": 0,
                   "memoryReference": hex(m.reg(n))} for n in GPRS + ["rip", "rflags"]]
        elif ref == FLAGS_REF:
            f = m.reg("rflags")
            vs = [{"name": n, "value": str(f >> b & 1), "variablesReference": 0} for n, b in FLAG_BITS]
        else:
            vs = [{"name": "stdout", "value": repr(bytes(m.stdout)), "variablesReference": 0},
                  {"name": "stderr", "value": repr(bytes(m.stderr)), "variablesReference": 0},
                  {"name": "state", "value": m.state, "variablesReference": 0}]
        self.respond(req, {"variables": vs})

    def on_evaluate(self, req, args):
        addr = self.s.eval_address(args["expression"])
        self.respond(req, {"result": f"{addr:#x} ({addr})", "variablesReference": 0,
                           "memoryReference": hex(addr)})

    def on_readMemory(self, req, args):
        addr = int(args["memoryReference"], 0) + args.get("offset", 0)
        count = args["count"]
        size = count
        while size > 0 and not self.s.m.readable(addr, size):
            size -= 1
        data = self.s.m.read(addr, size) if size else b""
        self.respond(req, {"address": hex(addr), "data": base64.b64encode(data).decode(),
                           "unreadableBytes": count - size})

    def on_disassemble(self, req, args):
        addr = int(args["memoryReference"], 0) + args.get("offset", 0)
        count = args["instructionCount"]
        out = []
        for a, raw, text in self.s.disasm(addr, count):
            ins = {"address": hex(a), "instructionBytes": raw.hex(" "), "instruction": text}
            if self.s.line(a):
                ins["line"] = self.s.line(a)
                ins["location"] = {"path": str(self.s.build.source)}
            out.append(ins)
        while len(out) < count:
            out.append({"address": "0x0", "instruction": "??", "presentationHint": "invalid"})
        self.respond(req, {"instructions": out})

    def _step_cmd(self, req, args, fn):
        self.respond(req)
        fn(args)
        self._after_run("step")

    def on_next(self, req, args):
        self._step_cmd(req, args, lambda a: self.s.step(1) if a.get("granularity") == "instruction"
                       else self.s.step_line())

    def on_stepIn(self, req, args):
        self.on_next(req, args)

    def on_stepOut(self, req, args):
        self.on_next(req, args)

    def on_stepBack(self, req, args):
        self._step_cmd(req, args, lambda a: self.s.back(1))

    def on_continue(self, req, args):
        self.respond(req, {"allThreadsContinued": True})
        self._after_run(self.s.cont())

    def on_reverseContinue(self, req, args):
        self.respond(req)
        reason = self.s.reverse_cont()
        self.stopped("breakpoint" if reason == "breakpoint" else "entry")

    def on_restart(self, req, args):
        self.s.restart()
        self.respond(req)
        self.stopped("entry")

    def on_pause(self, req, args):
        self.respond(req)
        self.stopped("pause")

    def on_disconnect(self, req, args):
        self.respond(req)
        self.running = False

    on_terminate = on_disconnect

    def _after_run(self, reason: str) -> None:
        m = self.s.m
        if m.finished:
            text = {"done": ("your function returned\n" if m.build.mode == "function"
                             else "reached the end of your code\n"),
                    "exited": f"program exited with status {m.exit_code}\n",
                    "fault": f"{m.fault}\n", "limit": "step limit reached\n"}[m.state]
            self.event("output", {"category": "console", "output": text})
            # Stay stopped (not terminated) so the player can step back from the end.
            self.stopped("exception" if m.state == "fault" else "step",
                         description=text.strip())
        else:
            self.stopped("breakpoint" if reason == "breakpoint" else "step")

    def stopped(self, reason: str, description: str | None = None) -> None:
        body = {"reason": reason, "threadId": THREAD_ID, "allThreadsStopped": True}
        if description:
            body["description"] = description
            body["text"] = description
        self.event("stopped", body)


def serve_stdio(session_factory) -> None:
    DapServer(sys.stdin.buffer, sys.stdout.buffer, session_factory).serve()
