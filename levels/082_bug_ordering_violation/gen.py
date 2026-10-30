def case(name, inject, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"tso": True, "quantum": 10, **inject},
            "expect": {"stdout": "both inside: 0\n", "exit": 0}}


def fixed_tests(ctx):
    return [case("one schedule", {"schedule": 0}),
            case("many schedules", {"schedule_sweep": {"count": 40}})]


def generate(rng, count, ctx):
    return [case("more schedules", {"schedule_sweep": {"count": 40}, "quantum": 30}, hidden=True)]


def witness_test(w, ctx):
    if set(w) != {"schedule"} or not isinstance(w["schedule"], int) or w["schedule"] < 0:
        raise ValueError("the witness is a schedule number: `;! witness schedule = 7`")
    return case("witness", {"schedule": w["schedule"]})


def audit(build):
    """At most one serializing instruction in peterson_lock, none in peterson_unlock."""
    from capstone import CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, Cs
    from ring.emu import Machine
    syms = build.symbols
    if "peterson_lock" not in syms or "peterson_unlock" not in syms:
        return [("peterson_lock and peterson_unlock still exist", False, "")]
    lo, mid = syms["peterson_lock"], syms["peterson_unlock"]
    end = min([a for a in syms.values() if a > mid] + [build.code_range[1]])
    m = Machine(build)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    def fences(a, b):
        n = 0
        for ins in md.disasm(m.read(a, b - a), a):
            if ins.mnemonic in ("mfence", "cpuid") or 0xF0 in ins.prefix or (
                    ins.mnemonic == "xchg" and any(o.type == CS_OP_MEM for o in ins.operands)):
                n += 1
        return n
    in_lock, in_unlock = fences(lo, mid), fences(mid, end)
    ok = in_lock <= 1 and in_unlock == 0
    return [("the minimum fences: at most one in peterson_lock, none in peterson_unlock", ok,
             "" if ok else f"found {in_lock} in peterson_lock and {in_unlock} in peterson_unlock")]
