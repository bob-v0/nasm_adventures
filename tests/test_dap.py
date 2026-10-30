"""Drive the DAP server the way an editor would."""

import io
import json

from ring.authoring import build_copy
from ring.dap import DapServer
from ring.debugger import Session
from ring.level import all_levels


def encode(messages):
    out = b""
    for i, (cmd, args) in enumerate(messages, 1):
        body = json.dumps({"seq": i, "type": "request", "command": cmd, "arguments": args}).encode()
        out += f"Content-Length: {len(body)}\r\n\r\n".encode() + body
    return out


def decode(raw):
    msgs = []
    while raw:
        header, _, rest = raw.partition(b"\r\n\r\n")
        n = int(header.split(b":")[1])
        msgs.append(json.loads(rest[:n]))
        raw = rest[n:]
    return msgs


def test_dap_session(tmp_path):
    lv = all_levels()[183]
    b = build_copy(lv, lv.reference, tmp_path)
    test = lv.tests[0]
    requests = [
        ("initialize", {"adapterID": "ring"}),
        ("launch", {"level": 183}),
        ("setBreakpoints", {"source": {"path": str(b.source)}, "breakpoints": [{"line": 3}]}),
        ("configurationDone", {}),
        ("continue", {"threadId": 1}),
        ("scopes", {"frameId": 1}),
        ("variables", {"variablesReference": 1}),
        ("stepBack", {"threadId": 1}),
        ("stackTrace", {"threadId": 1}),
        ("readMemory", {"memoryReference": hex(b.symbols["_start"]), "count": 4}),
        ("disassemble", {"memoryReference": hex(b.symbols["_start"]), "instructionCount": 2}),
        ("disconnect", {}),
    ]
    out = io.BytesIO()
    DapServer(io.BytesIO(encode(requests)), out, lambda args: Session(b, test)).serve()
    msgs = decode(out.getvalue())
    responses = {m["command"]: m for m in msgs if m["type"] == "response"}
    assert all(r["success"] for r in responses.values()), [r for r in responses.values() if not r["success"]]
    assert responses["initialize"]["body"]["supportsStepBack"]
    assert responses["setBreakpoints"]["body"]["breakpoints"][0]["verified"]
    stops = [m["body"]["reason"] for m in msgs if m.get("event") == "stopped"]
    assert stops[:2] == ["entry", "breakpoint"]
    regs = {v["name"]: int(v["value"], 16) for v in responses["variables"]["body"]["variables"]}
    # at the breakpoint (line 3), lines 1-2 have run: rax=B(2), rbx=C(3)
    assert (regs["rax"], regs["rbx"], regs["rcx"]) == (2, 3, 1)
    # stepping back lands on line 2
    assert responses["stackTrace"]["body"]["stackFrames"][0]["line"] == 2
    assert len(responses["disassemble"]["body"]["instructions"]) == 2
