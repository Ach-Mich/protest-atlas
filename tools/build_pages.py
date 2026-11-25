#!/usr/bin/env python3
"""Build the files that make Protest Atlas shareable and followable.

From data/briefings.json it writes:
  c/<code>/index.html   one readable page per country (full briefing in plain HTML),
                        with its own title, description and preview picture: search
                        engines can index it, and a link pasted into WhatsApp, X,
                        Signal or Slack shows a proper card.
  c/<code>/card.png     the 1200x630 preview picture for that country
  card.png              the preview picture for the home page
  feed.xml              RSS feed: latest protest day and announced date per country
  robots.txt, sitemap.xml  for search engines (the sitemap needs --site)

Usage (from the site folder):
  python3 tools/build_pages.py --site https://your-address.example
Link previews need the full public address of the site (--site). Without it the
pages are still built, with relative links, and previews won't show until you
rebuild with --site. Pictures need Google Chrome; without it they are skipped.
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from email.utils import format_datetime

def find_chrome():
    """Google Chrome on a Mac, or Chrome/Chromium on Linux (e.g. GitHub Actions). $CHROME wins."""
    import shutil
    for c in (os.environ.get("CHROME"), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if c and os.path.exists(c):
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(name):
            return shutil.which(name)
    return ""


CHROME = find_chrome()
THEMES = {"cost": "Cost of living", "wages": "Wages & jobs", "housing": "Housing", "education": "Education",
          "austerity": "Pensions & austerity", "services": "Public services & health",
          "governance": "Corruption & governance", "war": "War, conscription & foreign policy",
          "media": "Media freedom", "rights": "Rights & equality"}
E = html.escape


def long_date(iso):
    d = datetime.fromisoformat(iso[:10])
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"


def latest_event(x):
    ev = sorted(x.get("events") or [], key=lambda e: e["date"])
    return ev[-1] if ev else None


def turnout(e):
    if not e:
        return ""
    if e.get("orgc"):
        s = f"{e['orgc']:,} according to organisers"
        if e.get("off"):
            s += f", {e['off']:,} official"
        return s
    if e.get("off"):
        return f"{e['off']:,} official count"
    return "Turnout not reported"


def reasons(x):
    return x.get("reasons") or [THEMES.get(t, t) for t in x.get("themes") or []]


def description(x):
    s = (x.get("summary") or "").strip()
    if len(s) > 200:
        s = s[:197].rsplit(" ", 1)[0] + "…"
    return s or "Checked daily by Protest Atlas."


def card_html(title, kicker, lines, next_line):
    rows = "".join(f"<p>{E(l)}</p>" for l in lines if l)
    nxt = f'<p class="next">{E(next_line)}</p>' if next_line else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@400;700&display=block" rel="stylesheet"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1200px;height:630px;background:#F8F5EE;color:#1F2A33;font-family:Futura,"Jost","Avenir Next",sans-serif;padding:64px 72px;position:relative;overflow:hidden}}
.brand{{font-size:26px;font-weight:700;text-transform:uppercase;letter-spacing:.02em}}
.kick{{margin-top:54px;font-size:28px;color:#5B6770}}
h1{{font-size:{110 if len(title) < 12 else 84}px;line-height:.95;font-weight:700;text-transform:uppercase;letter-spacing:-.01em;margin-top:10px}}
.lines{{margin-top:26px;font-size:30px;line-height:1.35;color:#3A4650;max-width:1000px}}
.lines p{{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}}
.next{{color:#E85D24;font-weight:700}}
.bar{{position:absolute;left:0;right:0;bottom:0;height:18px;background:#1F2A33}}
</style></head><body><div class="brand">Protest Atlas</div><div class="kick">{E(kicker)}</div>
<h1>{E(title)}</h1><div class="lines">{rows}{nxt}</div><div class="bar"></div></body></html>"""


def shoot(html_text, out_png):
    """Render 1200x630 HTML to PNG with headless Chrome. Returns True on success."""
    if not CHROME:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "card.html")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(html_text)
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--window-size=1200,630", "--virtual-time-budget=5000", "--no-sandbox",
                            f"--screenshot={out_png}", "file://" + src],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and os.path.exists(out_png)


DEMAND = {"policy": "Policy change", "programme": "Change of programme", "resignation": "Resignation"}
RESP = {"none": "No response yet", "talks": "Talks offered", "crisis": "Government crisis"}
PAGE_CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{background:#F8F5EE;color:#1F2A33;font:400 17px/1.6 Jost,Futura,"Avenir Next",sans-serif}
a{color:inherit;text-underline-offset:3px}
.wrap{max-width:780px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid #DDD7CB}header .wrap{display:flex;justify-content:space-between;align-items:center;height:60px;max-width:1240px}
.logo{font-weight:800;text-transform:uppercase;text-decoration:none}
h1{font:800 clamp(48px,9vw,84px)/.9 Jost,Futura,sans-serif;text-transform:uppercase;margin:40px 0 10px}
.checked{font-size:14px;color:#5B6770;margin-bottom:16px}
.lede{font-size:19px;color:#3A4650;margin-bottom:12px}
p{margin-bottom:10px;color:#3A4650}
h2{font:700 22px/1.2 Jost,Futura,sans-serif;text-transform:uppercase;border-top:3px solid #1F2A33;padding-top:12px;margin:34px 0 12px}
.next b{color:#18695F}
.day{border-bottom:1px solid #DDD7CB;padding:12px 0}.day:last-child{border:0}
.day h3{font-size:17px;font-weight:600}
.meta{font-size:14px;color:#5B6770}
.srcs{font-size:13px;color:#5B6770}
dl{display:grid;grid-template-columns:120px 1fr;gap:6px 14px}dt{color:#5B6770}
.cta{display:inline-block;margin:28px 0 8px;font-weight:700;border-bottom:3px solid #1F2A33;text-decoration:none}
footer{border-top:1px solid #DDD7CB;margin-top:50px;padding:18px 0 40px;font-size:14px;color:#5B6770}"""


def src_line(src):
    if not src:
        return ""
    return '<p class="srcs">Sources: ' + ", ".join(f'<a href="{E(u)}" rel="noopener">{E(t)}</a>' for t, u in src) + "</p>"


def share_page(code, x, site):
    """A full, readable page per country: indexable by search engines and shown when a link is shared."""
    base = site.rstrip("/") if site else ""
    url = f"{base}/c/{code.lower()}/" if base else f"c/{code.lower()}/"
    img = f"{base}/c/{code.lower()}/card.png" if base else "card.png"
    title = f"{x['country']}: who is protesting and why | Protest Atlas"
    desc = description(x)
    live = f"../../#{code}"
    body = []
    if x.get("checkedAt"):
        body.append(f'<p class="checked">Last checked {E(long_date(x["checkedAt"]))} at {E(x["checkedAt"][11:16])}.</p>')
    body.append(f'<p class="lede">{E(x.get("summary") or "No national protest found in our sources for the last 30 days.")}</p>')
    if x.get("tier") == "watch":
        r = reasons(x)
        body.append(f'<p><b>Why they protest:</b> {E("; ".join(r)) + "." if r else "no clear demands reported so far."}</p>')
    if x.get("nextDate") and x.get("next"):
        body.append(f'<p class="next"><b>Next protest, {E(long_date(x["nextDate"]))}.</b> {E(x["next"])}</p>')
    groups = x.get("groups") or []
    if groups:
        body.append("<h2>Who is protesting, and what they want</h2>")
        for g in groups:
            body.append(f'<p><b>{E(g.get("name",""))}</b> <span class="meta">{E(g.get("since",""))}</span><br>{E(" · ".join(g.get("items") or []))}</p>')
    p = x.get("pressure")
    if p:
        rows = [("Demand", DEMAND.get(p.get("demand"), ""), p.get("demandNote")),
                ("Response", RESP.get(p.get("response"), ""), p.get("responseNote"))]
        if p.get("fragility"):
            rows.append(("Government", p["fragility"].capitalize(), p.get("fragilityNote")))
        if p.get("crackdown"):
            rows.append(("Policing", "Heavy", p.get("crackdownNote")))
        body.append("<h2>Pressure on government</h2><dl>" + "".join(
            f"<dt>{k}</dt><dd><b>{E(v)}</b>{'. ' + E(n[0].upper() + n[1:]) if n else ''}</dd>" for k, v, n in rows if v) + "</dl>" + src_line(p.get("src")))
    events = sorted(x.get("events") or [], key=lambda e: e["date"], reverse=True)
    if events:
        body.append("<h2>Protest days</h2>")
        for e in events:
            figs = [f"{n:,} {l}" for n, l in ((e.get("off"), "official"), (e.get("orgc"), "organisers"), (e.get("arrests"), "arrests")) if n is not None]
            body.append(f'<div class="day"><h3>{E(e["title"])}</h3><p class="meta">{E(long_date(e["date"]))}. {E(" · ".join(figs) if figs else "Turnout not reported")}</p>'
                        + (f'<p>{E(e["extra"])}</p>' if e.get("extra") else "") + src_line(e.get("src")) + "</div>")
    body.append(f'<p><a class="cta" href="{live}">See {E(x["country"])} on the live atlas</a></p>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Protest Atlas">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}">
<meta property="og:image" content="{E(img)}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{E(url)}">
<link rel="stylesheet" href="../../fonts/fonts.css">
<script data-goatcounter="https://protestatlas.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
<style>{PAGE_CSS}</style>
</head><body>
<header><div class="wrap"><a class="logo" href="../../">Protest Atlas</a><a href="../../#countries">All countries</a></div></header>
<main class="wrap"><h1>{E(x['country'])}</h1>
{chr(10).join(body)}
</main>
<footer><div class="wrap">Protest Atlas is an independent project. <a href="../../about.html">About</a> · <a href="../../about.html#corrections">Send a correction</a></div></footer>
</body></html>
"""


def feed(data, site):
    base = site.rstrip("/") if site else ""
    items = []
    for code, x in data.items():
        if x.get("tier") != "watch":
            continue
        link = f"{base}/c/{code.lower()}/" if base else f"c/{code.lower()}/"
        e = latest_event(x)
        if e:
            items.append((e["date"], f"{code}-{e['date']}-protest",
                          f"{x['country']}: {e['title']}",
                          f"{long_date(e['date'])}. {turnout(e)}. Why: {', '.join(reasons(x)) or 'no clear demands reported'}.",
                          link))
        if x.get("nextDate"):
            # Dated when we learned of it (last update), never in the future: email services
            # hold back or skip future-dated items.
            known = (x.get("updatedAt") or x.get("checkedAt") or x["nextDate"])[:10]
            items.append((min(known, x["nextDate"]), f"{code}-{x['nextDate']}-next",
                          f"{x['country']}: next protest {long_date(x['nextDate'])}",
                          x.get("next") or "", link))
    items.sort(key=lambda i: i[0], reverse=True)
    now = format_datetime(datetime.now(timezone.utc))
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           "<title>Protest Atlas</title>", f"<link>{E(base or '.')}/</link>",
           "<description>National protests and strikes across Europe, checked daily.</description>",
           f"<lastBuildDate>{now}</lastBuildDate>"]
    for d, guid, title, desc, link in items[:60]:
        pub = format_datetime(datetime.fromisoformat(d + "T09:00:00+00:00"))
        out.append(f"<item><title>{E(title)}</title><link>{E(link)}</link><guid isPermaLink=\"false\">{E(guid)}</guid>"
                   f"<pubDate>{pub}</pubDate><description>{E(desc)}</description></item>")
    out.append("</channel></rss>")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=os.environ.get("PROTEST_ATLAS_SITE", ""),
                    help="public address of the site, e.g. https://example.github.io/protest-atlas")
    ap.add_argument("--data", default="data/briefings.json")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args()
    with open(a.data, encoding="utf-8") as fh:
        data = json.load(fh)

    # remove pages of countries no longer in the data, keep the others (and their pictures)
    if os.path.isdir("c"):
        for d in os.listdir("c"):
            if d.upper() not in data and os.path.isdir(os.path.join("c", d)):
                shutil.rmtree(os.path.join("c", d))
    images = not a.no_images and bool(CHROME)
    made = 0
    for code, x in data.items():
        folder = os.path.join("c", code.lower())
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(share_page(code, x, a.site))
        if images:
            e = latest_event(x)
            if x.get("tier") == "watch":
                kicker = f"Latest protest, {long_date(e['date'])}" if e else "On watch"
                lines = [e["title"] if e else "", turnout(e) if e else "",
                         ("Why: " + ", ".join(reasons(x))) if reasons(x) else ""]
            else:
                kicker, lines = "Checked daily", ["No national protest reported recently."]
            nxt = f"Next protest: {long_date(x['nextDate'])}" if x.get("nextDate") else ""
            made += shoot(card_html(x["country"], kicker, lines, nxt), os.path.join(folder, "card.png"))
    if images:
        watched = sum(1 for x in data.values() if x.get("tier") == "watch")
        shoot(card_html("Who's on the street", "Europe, checked every morning",
                        [f"{watched} countries on watch", "Who is marching, why, how many, and what comes next."], ""),
              "card.png")
    with open("feed.xml", "w", encoding="utf-8") as fh:
        fh.write(feed(data, a.site))
    base = a.site.rstrip("/")
    with open("robots.txt", "w", encoding="utf-8") as fh:
        fh.write("User-agent: *\nAllow: /\n" + (f"Sitemap: {base}/sitemap.xml\n" if base else ""))
    if base:
        today = datetime.now(timezone.utc).date().isoformat()
        urls = [f"{base}/", f"{base}/about.html", f"{base}/rss.html"] + [f"{base}/c/{c.lower()}/" for c in sorted(data)]
        with open("sitemap.xml", "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                     + "".join(f"<url><loc>{E(u)}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n")

    print(f"Built {len(data)} country pages in c/, feed.xml"
          + (f", {made} preview pictures" if images else ", no pictures (Chrome not found or --no-images)"))
    if not a.site:
        print("Note: no --site given. Link previews need the site's full public address; "
              "rebuild with --site https://... once the site is online.", file=sys.stderr)


if __name__ == "__main__":
    main()
