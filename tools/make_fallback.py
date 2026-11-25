#!/usr/bin/env python3
"""Save a backup copy of data/briefings.json that the page can show if the live file can't load.

Writes data/briefings-fallback.js. Being a script (not JSON), it also loads when
index.html is opened straight from disk, where the live fetch is blocked.

Run it after each data update, once tools/check_briefings.py passes:
    python3 tools/check_briefings.py && python3 tools/make_fallback.py
"""
import json
import sys
from datetime import datetime, timezone

src = sys.argv[1] if len(sys.argv) > 1 else "data/briefings.json"
dst = sys.argv[2] if len(sys.argv) > 2 else "data/briefings-fallback.js"

with open(src, encoding="utf-8") as fh:
    data = json.load(fh)
saved = datetime.now(timezone.utc).isoformat(timespec="minutes")
body = json.dumps({"savedAt": saved, "data": data}, ensure_ascii=False, separators=(",", ":"))
with open(dst, "w", encoding="utf-8") as fh:
    fh.write("// Backup copy of data/briefings.json, made by tools/make_fallback.py. Do not edit by hand.\n")
    fh.write("window.PA_FALLBACK=" + body.replace("</", "<\\/") + ";\n")
print(f"Saved {len(data)} countries to {dst}")
