"""
Checks the data files of the Farmers and Career Guidance sections.

    python check_new_sections.py          -> structure checks (offline, runs in a second)
    python check_new_sections.py --urls   -> also opens every official link and reports the ones that do not answer
                                             (run it on your own computer; some government sites block bots, so
                                             treat a failure as "look at this link", not as proof it is dead)
"""
import glob, json, os, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
problems, urls = [], set()

def need(cond, msg):
    if not cond: problems.append(msg)

# farmers
for f in sorted(glob.glob(os.path.join(HERE, "data", "farmers", "*.json"))):
    for e in json.load(open(f, encoding="utf-8")):
        n = e.get("name", "?")
        for k in ("name", "sub_category", "official_url", "steps", "checked_on", "eligibility_text", "required_documents", "source_organization"):
            need(e.get(k), f"farmers/{os.path.basename(f)}: {n}: missing {k}")
        urls.add(e.get("official_url", ""))
# careers
cd = os.path.join(HERE, "data", "careers")
paths = []
for f in sorted(glob.glob(os.path.join(cd, "paths_*.json"))): paths += json.load(open(f, encoding="utf-8"))
ids = [p["id"] for p in paths]
need(len(ids) == len(set(ids)), "careers: duplicate path id")
STAGES = {"after_10th", "after_12th", "after_diploma", "after_ug", "after_pg"}
for p in paths:
    for k in ("id", "title", "type", "stages", "summary", "qualification", "next_steps", "official_links", "scholarship_keywords"):
        need(p.get(k), f"careers: {p.get('id')}: missing {k}")
    need(set(p.get("stages", [])) <= STAGES, f"careers: {p['id']}: unknown stage")
    need(p.get("budget_level") in ("low", "medium", "high"), f"careers: {p['id']}: budget_level")
    for l in p.get("official_links", []) + [e for e in p.get("entrance_exams", []) if e.get("url")]:
        u = l.get("url", ""); need(u.startswith("https://"), f"careers: {p['id']}: link must be https: {u}"); urls.add(u)
g = json.load(open(os.path.join(cd, "guides.json"), encoding="utf-8"))
for s, v in g["stages"].items():
    for i in v["path_ids"]: need(i in ids, f"guides.json: {s} refers to unknown path {i}")
print(f"{len(paths)} career paths, {len(urls)} distinct official links")
if "--urls" in sys.argv:
    for u in sorted(urls):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=15)
            print("OK  ", r.status, u)
        except Exception as ex:
            print("CHECK", u, "->", ex); 
print("PROBLEMS:" if problems else "No structural problems.")
for p in problems: print(" -", p)
sys.exit(1 if problems else 0)
