import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    m = json.load(f)

removed = m.pop("key", None) is not None

# Replace the dev-only localhost host permission with the production origin.
# `<all_urls>` already covers it, but the published manifest should request the
# origin it actually talks to, not a laptop's localhost.
hp = m.get("host_permissions", [])
m["host_permissions"] = [
    "https://traba-hero-production-b6b9.up.railway.app/*" if h == "http://localhost:8010/*" else h
    for h in hp
]

with open(path, "w", encoding="utf-8") as f:
    json.dump(m, f, separators=(",", ":"), ensure_ascii=False)

print("key removed:", removed)
print("host_permissions:", m["host_permissions"])
