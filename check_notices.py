"""
Looks for NEW scholarship announcements on the official portals listed in data/sources.json.
    python check_notices.py                      (needs DATABASE_URL, like seed_all.py)
    python check_notices.py --sources my.json    (use another list)
    python check_notices.py --auto-publish       (skip the review step: found notices go live at once, marked 'auto-detected' for students)

What it does: opens each portal's page, collects links whose text looks like a notice (scholarship / notice / circular / last date / extended ...),
and saves the ones not seen before as DRAFT notices. NOTHING reaches students until you open admin.html, read the official page, and press Publish.
Best-effort only: portals that build their notice list with JavaScript, block bots or have a broken certificate will show nothing here —
add those notices by hand in admin.html. Run it daily or weekly; adding a portal = adding one line to data/sources.json.
"""
import json, os, sys, urllib.request
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin
from app.database import SessionLocal, Base, engine
from app.models.core import Notice

KEYWORDS = ("scholarship", "notice", "circular", "notification", "last date", "extended", "extension", "guideline", "advertisement",
            "छात्रवृत्ति", "सूचना", "अंतिम तिथि", "परिपत्र", "अधिसूचना")
MAX_PER_SOURCE = 10
AUTO_PUBLISH = "--auto-publish" in sys.argv


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.href = None; self.text = []; self.found = []
    def handle_starttag(self, tag, attrs):
        if tag == "a": self.href = dict(attrs).get("href"); self.text = []
    def handle_data(self, data):
        if self.href is not None: self.text.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.found.append((" ".join("".join(self.text).split()), self.href)); self.href = None


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OpportunityHub notice check)"})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", errors="ignore")


if __name__ == "__main__":
    path = sys.argv[sys.argv.index("--sources") + 1] if "--sources" in sys.argv else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sources.json")
    sources = json.load(open(path, encoding="utf-8"))
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    known = {u for (u,) in db.query(Notice.url).all()}
    total = 0
    for s in sources:
        try:
            p = Links(); p.feed(fetch(s["url"]))
        except Exception as e:
            print(f"- {s['name']}: could not open ({type(e).__name__}) — add notices by hand"); continue
        new = 0
        for text, href in p.found:
            url = urljoin(s["url"], href or "")
            if len(text) < 12 or not url.startswith("http") or url in known: continue
            if not any(k in text.lower() for k in KEYWORDS): continue
            db.add(Notice(title=text[:200], url=url, source_name=s["name"], state=s.get("state"), is_published=AUTO_PUBLISH, auto_found=True,
                          published_on=datetime.utcnow()))
            known.add(url); new += 1
            if new >= MAX_PER_SOURCE: break
        total += new
        print(f"- {s['name']}: {new} new draft(s)")
    db.commit(); db.close()
    print(f"\n{total} notice(s) saved " + ("and PUBLISHED (marked auto-detected)." if AUTO_PUBLISH else "as drafts. Open admin.html -> Notices, skim them, delete the junk, publish the useful ones."))
