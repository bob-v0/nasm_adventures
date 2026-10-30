#!/usr/bin/env bash
# Smoke test for the player image (run inside the container by CI):
# the web UI serves the page and API, and a level can be played from the CLI.
set -euo pipefail
cd "${RING_WORKSPACE:-/workspace}"

RING_UI_TOKEN=smoke ring ui --no-browser --port 8080 > /tmp/ui.log 2>&1 &
trap 'kill %1 2>/dev/null || true' EXIT

python3 - <<'PY'
import http.cookiejar, json, time, urllib.request

base = "http://127.0.0.1:8080"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
for _ in range(50):  # wait for the server
    try:
        page = opener.open(f"{base}/?token=smoke")  # redirects to / and sets the cookie
        break
    except OSError:
        time.sleep(0.2)
else:
    raise SystemExit("web UI did not start: " + open("/tmp/ui.log").read())
assert page.status == 200 and b"NASM Adventures" in page.read(), "page not served"
req = urllib.request.Request(f"{base}/api/state", method="POST", data=b"{}",
                             headers={"Content-Type": "application/json"})
state = json.loads(opener.open(req).read())
assert state["current"] == 184, state
print("web UI ok")
PY

ring start
if ring test; then echo "the starter should fail"; exit 1; fi
printf 'mov rax, 42\nmov rbx, 184\n' > level184/solution.asm
ring submit
ring status
