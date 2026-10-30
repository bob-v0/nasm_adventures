SECRET = "root:$6$Zr1ng0$9f8a7cbd0e:19700:0:99999:7:::\n"
REPORT = "quarterly numbers: 42\n"
NOTES = "remember the milk\n"
MOTD = "welcome to ring 116\n"
DENIED = "access denied\n"

FILES = {
    "/etc/shadow": {"text": SECRET, "uid": 0, "mode": 0o600},
    "/etc/motd": {"text": MOTD, "uid": 0, "mode": 0o644},
    "/tmp/report": REPORT,
    "/home/player/notes.txt": NOTES,
    "/tmp/to_notes": {"symlink": "/home/player/notes.txt"},
    "/tmp/to_shadow": {"symlink": "/etc/shadow"},
}

ATTACK = {"symlink": ["/tmp/report", "/etc/shadow"],
          "describe": "replaced /tmp/report with a symlink to /etc/shadow"}


def case(name, path, readable_text=None, hidden=False, inject=None, may_refuse=False):
    """readable_text: what the file holds if the user may read it (None: must be refused)."""
    t = {"name": name, "hidden": hidden, "argv": ["./showfile", path], "files": FILES,
         "expect": {"check": True, "fds_open": [0, 1, 2], "readable": readable_text,
                    "may_refuse": may_refuse}}
    if inject:
        t["inject"] = inject
    return t


def check(test, m):
    out, err = bytes(m.stdout).decode("latin-1"), bytes(m.stderr).decode("latin-1")
    if "s3cr" in out or "$6$" in out:
        return ["it printed /etc/shadow: the user can read root's password hashes"]
    want = test.expect["readable"]
    printed = (out, err, m.exit_code) == (want, "", 0)
    refused = (out, err, m.exit_code) == ("", DENIED, 1)
    if want is None and not refused:
        return [f"it must refuse (stderr {DENIED!r}, exit 1); got stdout {out!r}, stderr {err!r}, "
                f"exit {m.exit_code}"]
    if want is not None and not printed and not (refused and test.expect["may_refuse"]):
        return [f"expected the file's contents {want!r} and exit 0; got stdout {out!r}, "
                f"stderr {err!r}, exit {m.exit_code}"]
    return []


def fixed_tests(ctx):
    return [case("the user's own file", "/tmp/report", REPORT),
            case("root's secret", "/etc/shadow"),
            case("a file everyone may read", "/etc/motd", MOTD)]


def generate(rng, count, ctx):
    return [
        case("a missing file", "/tmp/nothing", hidden=True),
        case("a symlink to the user's file", "/tmp/to_notes", NOTES, hidden=True, may_refuse=True),
        case("a symlink to the secret", "/tmp/to_shadow", hidden=True),
        case("an attacker who swaps the file at every possible moment", "/tmp/report", REPORT,
             hidden=True, may_refuse=True, inject={"fs_sweep": ATTACK}),
    ]


def witness_test(w, ctx):
    from ring.kernel import NAMES
    if set(w) - {"after", "nth"} or not isinstance(w.get("after"), str):
        raise ValueError('the witness names the syscall after which the attacker strikes, '
                         'e.g. `;! witness after = "open"` (and optionally `nth = 2`)')
    if w["after"] not in NAMES.values():
        raise ValueError(f"{w['after']!r} is not a syscall name the game knows")
    return case("witness", "/tmp/report", REPORT, may_refuse=True,
                inject={"fs_events": [{**ATTACK, "after": w["after"], "nth": w.get("nth", 1)}]})
