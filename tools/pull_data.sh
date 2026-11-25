#!/bin/sh
# Copies the latest data written by the cloud update routine (GitHub: Ach-Mich/protest-atlas)
# into this site, then checks it and rebuilds the saved copy, share pages and feed.
# Usage: sh tools/pull_data.sh            (run from anywhere)
set -e
SITE="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$HOME/Downloads/protest-atlas-repo"
[ -d "$REPO/.git" ] || git clone -q https://github.com/Ach-Mich/protest-atlas.git "$REPO"
git -C "$REPO" fetch -q origin
git -C "$REPO" reset -q --hard origin/HEAD
cp "$SITE/data/briefings.json" "$SITE/data/history/previous.json"
cp "$REPO/data/briefings.json" "$SITE/data/briefings.json"
echo "Data from: $(git -C "$REPO" log -1 --format='%s (%ad)' --date=short)"
cd "$SITE"
python3 tools/check_briefings.py
python3 tools/make_fallback.py
python3 tools/build_pages.py ${SITE_URL:+--site "$SITE_URL"}
