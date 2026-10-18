"""
Builds the PUBLIC, crawlable pages (no login) from the same data files the app uses.

    python build_seo.py https://your-site.pages.dev [G-XXXXXXXXXX] [--clean]   (frontend URL, no trailing slash; optional Google Analytics ID;
    --clean writes addresses without .html, automatic for *.pages.dev and *.workers.dev; use it on any host that hides .html, e.g. Cloudflare)

Writes into frontend/:  scholarship/<slug>.html   yojana/<slug>.html   scholarships.html   yojana.html
                        sitemap.xml   robots.txt   and refreshes the "Browse" block + title/description in index.html.
Safe to re-run any time (after editing data/*.json). Nothing is invented: every fact on a page comes from the data files.
"""
import glob, html, json, os, re, sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
FE = os.path.join(ROOT, "frontend")
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
try:                                                      # site_config.json (project root) keeps your URL, Google Analytics ID and AdSense ID
    CFG = json.load(open(os.path.join(ROOT, "site_config.json"), encoding="utf-8"))
except Exception:
    CFG = {}
SITE = (ARGS[0] if ARGS else os.getenv("SITE_URL") or CFG.get("site_url") or "https://opportunityhub.pages.dev").rstrip("/")
GA_ID = (ARGS[1] if len(ARGS) > 1 else os.getenv("GA_ID") or CFG.get("ga_id") or "").strip()
ADSENSE = (os.getenv("ADSENSE_CLIENT") or CFG.get("adsense_client") or "").strip()      # e.g. ca-pub-1234567890123456
# Cloudflare Pages redirects /x.html to /x, so on it every address (canonical, sitemap, links) must be written without .html
CLEAN = "--clean" in sys.argv or SITE.endswith((".pages.dev", ".workers.dev"))
if GA_ID and not re.fullmatch(r"G-[A-Z0-9]{4,}", GA_ID):
    sys.exit("GA id must look like G-XXXXXXXXXX (Google Analytics 4 measurement ID)")
if ADSENSE and not re.fullmatch(r"ca-pub-\d{10,}", ADSENSE):
    sys.exit("adsense_client must look like ca-pub-1234567890123456")
EMAIL = "zalteom111@gmail.com"
TODAY = date.today()
YEAR = TODAY.year
E = lambda s: html.escape(str(s), quote=True)

CAT = {"sc": "Scheduled Caste (SC)", "st": "Scheduled Tribe (ST)", "obc": "OBC", "general": "General", "ews": "EWS",
       "minority": "Minority community", "sebc": "SEBC", "sbc": "SBC"}
EDU = {"10th": "Class 10", "12th": "Class 12", "diploma": "Diploma", "bachelors": "Bachelor's degree (UG)", "masters": "Master's degree (PG)"}
SUB = {"crop_insurance": "Crop insurance", "irrigation": "Irrigation", "solar_pump": "Solar pumps", "equipment": "Farm equipment",
       "financial": "Income support and finance", "loans": "Loans and credit", "other": "Other schemes"}


def slugify(s, used):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:70].strip("-") or "scheme"
    base, n = s, 2
    while s in used:
        s, n = f"{base}-{n}", n + 1
    used.add(s)
    return s


def rupees(n):
    n = float(n)
    if n >= 100000:
        v = n / 100000
        return f"₹{v:g} lakh"
    return f"₹{n:,.0f}"


def lst(vals, m):
    return ", ".join(m.get(str(v).lower(), str(v).title()) for v in vals)


def humanize(e):
    out = []
    st, basis = e.get("state"), e.get("state_basis") or "domicile"
    if st:
        out.append(f"Studying in {st}" if basis == "institute" else f"Resident (domicile) of {st}" if basis == "domicile" else f"Linked to {st} (home state or institute state)")
    else:
        out.append("Open to students from any state in India")
    for k, r in e["eligibility_rules"].items():
        if k == "category":
            out.append("Category: " + lst([r["eq"]] if "eq" in r else r.get("in", []), CAT))
        elif k == "family_income" and "lte" in r:
            out.append(f"Family income up to {rupees(r['lte'])} per year")
        elif k == "marks_percent" and "gte" in r:
            out.append(f"At least {r['gte']:g}% marks in the previous exam")
        elif k == "age":
            out.append(f"Age {r['gte']:g} to {r['lte']:g} years" if "gte" in r and "lte" in r else f"Age up to {r['lte']:g} years" if "lte" in r else f"Age {r['gte']:g} years or more")
        elif k == "gender" and "eq" in r:
            out.append(f"Open to {r['eq']} students")
        elif k == "is_disabled":
            out.append("Student with a disability")
        elif k == "course_stream" and "eq" in r:
            out.append(f"{str(r['eq']).title()} stream")
        elif k == "education_level":
            out.append("Education level: " + lst([r["eq"]] if "eq" in r else r.get("in", []), EDU))
    return out


def trim(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


def title_for(name, tail):
    short = re.sub(r"\s*\([^)]*\)", "", name).strip()
    for n in (name, short):
        t = f"{n}: {tail} | OpportunityHub"
        if len(t) <= 66:
            return t
    return trim(f"{short} | OpportunityHub", 66)


def fmt_date(d):
    return d.strftime("%d %B %Y").lstrip("0")


try:
    HINDI = json.load(open(os.path.join(FE, "farmers_hi.json"), encoding="utf-8"))["schemes"]
except Exception:
    HINDI = {}


# ---------------- load data ----------------
def load():
    rd = lambda p: json.load(open(p, encoding="utf-8"))
    steps = rd(os.path.join(ROOT, "data", "steps.json"))
    sch, used = [], set()
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "*.json"))):
        if os.path.basename(f) in ("steps.json", "sources.json"):
            continue
        sch += rd(f)
    for e in sch:
        e["kind"], e["slug"] = "scholarship", slugify(e["name"], used)
        tpl = steps.get(e["steps"], {})
        e["steps_en"] = [s.replace("{scheme}", e["name"]) for s in tpl.get("en", [])]
        e["steps_hi"] = [s.replace("{scheme}", e["name"]) for s in tpl.get("hi", [])]
    far, used = [], set()
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "farmers", "*.json"))):
        if not os.path.basename(f).startswith("_"):
            far += rd(f)
    for e in far:
        e["kind"], e["slug"] = "yojana", slugify(e["name"], used)
        e["steps_en"], e["steps_hi"] = e["steps"], []
    return sch, far


# ---------------- html pieces ----------------
NAV = ('<div class="top"><a class="brand" href="/index.html">OpportunityHub</a><span class="nav">'
       '<a href="/scholarships.html">Scholarships</a><a href="/yojana.html">Farmer schemes</a><a href="/career.html">Career guidance</a><a href="/faq.html">FAQ</a><a class="loginlink" href="/index.html#login">Login</a></span></div>')
FOOT = ('<div class="foot"><a href="/privacy.html">Privacy Policy</a>·<a href="/terms.html">Terms of Service</a>·<a href="/faq.html">FAQ</a>·'
        '<a href="/about.html">About</a>·<a href="/faq.html#contact">Contact us</a></div>')


def page(title, desc, path, body, schema=None, wide=False):
    url = f"{SITE}/{path}"
    ld = f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>' if schema else ""
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{url}">
<meta property="og:type" content="website"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{url}">
<meta name="theme-color" content="#6B21A8"><link href="https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/legal.css">{ld}</head><body>{NAV}<div class="page{" wide" if wide else ""}">{body}</div>{FOOT}</body></html>'''


def ul(items):
    return "<ul>" + "".join(f"<li>{E(i)}</li>" for i in items) + "</ul>"


def ol(items):
    return "<ol>" + "".join(f"<li>{E(i)}</li>" for i in items) + "</ol>"


def deadline_line(e):
    d = e.get("deadline")
    if not d:
        return "The last date is announced on the official website and can change each year. Please check the official portal before you apply."
    dd = datetime.strptime(d, "%Y-%m-%d").date()
    if dd >= TODAY:
        return f"Last date to apply (as listed for this year): {fmt_date(dd)}. Dates can change, so confirm on the official website."
    return f"The last date listed for the previous round was {fmt_date(dd)}. New dates are announced on the official website, so check it for the current round."


def related(e, pool):
    same = [x for x in pool if x is not e and x["kind"] == e["kind"] and (x.get("state") == e.get("state"))]
    rest = [x for x in pool if x is not e and x["kind"] == e["kind"] and x not in same]
    return (same + rest)[:5]


def detail(e, pool):
    k, name = e["kind"], e["name"]
    folder = "scholarship" if k == "scholarship" else "yojana"
    path = f"{folder}/{e['slug']}.html"
    org, off = e.get("source_organization") or "the official authority", e["official_url"]
    elig = humanize(e) if k == "scholarship" else None
    docs = e.get("required_documents") or []
    amount = e.get("amount")
    if k == "scholarship":
        tail = f"Eligibility, How to Apply {YEAR}"
        verified = "Details are compiled from official sources. Always confirm on the official website before applying."
    else:
        tail = f"Benefits, Eligibility, Apply"
        verified = f"Last checked against the official source on {fmt_date(datetime.strptime(e['checked_on'], '%Y-%m-%d').date())}. Always confirm on the official website before applying."
    title = title_for(name, tail)
    desc = trim(f"{e.get('description') or ''} {('Benefit: ' + e['benefits']) if e.get('benefits') else ''}", 155)
    faqs = []
    if elig:
        faqs.append((f"Who is eligible for {name}?", "; ".join(elig) + ". Final eligibility is decided by the official authority."))
    else:
        faqs.append((f"Who is eligible for {name}?", e["eligibility_text"]))
    faqs.append((f"What does {name} give?", " ".join(x for x in [e.get("benefits"), f"Amount: {amount}." if amount else ""] if x)))
    if docs:
        faqs.append((f"Which documents are needed for {name}?", ", ".join(docs) + "."))
    faqs.append((f"What is the official website for {name}?", f"The official website is {off} (source: {org})."))
    faqs = [(q, a) for q, a in faqs if a.strip()]

    b = [f'<div class="card"><p class="meta"><a href="/{"scholarships" if k == "scholarship" else "yojana"}.html">{"Scholarships" if k == "scholarship" else "Farmer schemes"}</a>'
         + (f' › {E(e["state"])}' if e.get("state") else " › All India") + f'</p><h1>{E(name)}</h1>']
    b.append(f'<p>{E(e.get("description") or "")}</p>')
    if amount:
        b.append(f'<p><b>Amount / benefit:</b> {E(amount)}</p>')
    b.append(f'<p class="meta">Source: {E(org)}</p>')
    b.append(f'<div class="contact"><b>Check if you match, free in 1 minute</b><br>Enter a few details and see which scholarships and schemes fit you.<br><a class="mail" href="/index.html">Check my match</a></div>')
    b.append("<h2>What you get</h2>" + f'<p>{E(e.get("benefits") or amount or "See the official website for the exact benefit.")}</p>')
    b.append("<h2>Who is eligible</h2>" + (ul(elig) if elig else f'<p>{E(e["eligibility_text"])}</p>')
             + '<p class="meta">Final eligibility is decided by the official authority. Read the official notification before you apply.</p>')
    if docs:
        b.append("<h2>Documents required</h2>" + ul(docs))
    b.append("<h2>How to apply, step by step</h2>" + ol(e["steps_en"]))
    if e["steps_hi"]:
        b.append('<details lang="hi"><summary>हिंदी में आवेदन कैसे करें</summary>' + ol(e["steps_hi"]) + "</details>")
    b.append("<h2>Last date</h2><p>" + E(deadline_line(e) if k == "scholarship" else "Most farmer schemes accept applications through the year or in notified windows. Check the official portal for the current window.") + "</p>")
    b.append(f'<h2>Official website</h2><p><a href="{E(off)}" target="_blank" rel="noopener nofollow">{E(off)}</a> <span class="meta">({E(org)})</span></p>')
    hi = HINDI.get(name) if k == "yojana" else None
    if hi:                                              # simple Hindi version of the same facts (farmer schemes)
        b.append('<h2 lang="hi">हिंदी में जानकारी</h2><div lang="hi"><p><b>' + E(hi["n"]) + '</b></p>'
                 + (f'<p>{E(hi["a"])}</p>' if hi.get("a") else "") + f'<p>{E(hi["d"])}</p><p><b>फायदा:</b> {E(hi["b"])}</p><p><b>कौन आवेदन कर सकता है:</b> {E(hi["e"])}</p>'
                 + "<p><b>जरूरी कागज:</b></p>" + ul(hi["docs"]) + "<p><b>आवेदन कैसे करें:</b></p>" + ol(hi["steps"]) + "</div>")
    b.append(f'<p class="meta">{E(verified)} Found a mistake? <a href="/faq.html#contact">Tell us</a>.</p></div>')
    b.append('<div class="card"><h2>Frequently asked questions</h2>' + "".join(f"<details><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in faqs) + "</div>")
    rel = related(e, pool)
    if rel:
        b.append('<div class="card"><h2>Related ' + ("scholarships" if k == "scholarship" else "schemes") + '</h2><ul class="rel">'
                 + "".join(f'<li><a href="/{folder}/{x["slug"]}.html">{E(x["name"])}</a></li>' for x in rel) + "</ul></div>")
    schema = {"@context": "https://schema.org", "@type": "FAQPage",
              "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}
    return path, page(title, desc, path, "".join(b), schema), title, desc


def hub(kind, items):
    k = kind == "scholarship"
    folder = "scholarship" if k else "yojana"
    path = "scholarships.html" if k else "yojana.html"
    h1 = f"Government scholarships in India {YEAR}" if k else f"Farmer schemes (yojana) in India {YEAR}"
    intro = ("Central and state scholarships for students. Open any scholarship to see who is eligible, documents, how to apply and the official link."
             if k else "Central and state schemes for farmers: income support, crop insurance, irrigation, solar pumps, equipment and loans. Open any scheme for eligibility, documents and how to apply.")
    groups = {}
    for e in items:
        groups.setdefault(e.get("state") or "All India (central)", []).append(e)
    order = sorted(groups, key=lambda g: (not g.startswith("All India"), g))
    body = [f'<div class="card"><h1>{h1}</h1><p>{intro}</p><p class="meta">{len(items)} listed. Not sure which fit you? <a href="/index.html">Check your match free</a>.</p></div>']
    for g in order:
        body.append(f'<div class="card"><h2>{E(g)}</h2><ul class="rel">' + "".join(
            f'<li><a href="/{folder}/{x["slug"]}.html">{E(x["name"])}</a>' + (f' <span class="meta">· {E(SUB.get(x["sub_category"], ""))}</span>' if not k else "") + "</li>"
            for x in sorted(groups[g], key=lambda z: z["name"])) + "</ul></div>")
    title = f"{h1} | OpportunityHub" if len(h1) < 45 else h1
    desc = trim(intro, 155)
    schema = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{SITE}/{folder}/{x['slug']}.html", "name": x["name"]} for i, x in enumerate(items)]}
    return path, page(title, desc, path, "".join(body), schema, wide=True)


def about():
    body = f'''<div class="card"><h1>About OpportunityHub</h1>
<p>OpportunityHub is a free, independent website that helps students and farmers in India find government scholarships and schemes in one place, and check which ones may suit them.</p>
<h2>What we do</h2><p>We collect scheme details from official government sources, write them in simple language, and link to the official website for every scheme so you can apply there. We do not charge any fee and we do not apply on your behalf.</p>
<h2>How we keep information correct</h2><p>Every scheme page shows its official source. Deadlines and amounts can change, so please confirm on the official website before applying. If you find a mistake, email us and we will fix it.</p>
<h2>Independent project</h2><p>We are not a government body and not affiliated with any scheme listed here. Read our <a href="/terms.html">Terms</a> and <a href="/privacy.html">Privacy Policy</a>.</p>
<h2>Contact</h2><p><a href="mailto:{EMAIL}">{EMAIL}</a></p></div>'''
    return page("About OpportunityHub: free scholarship and farmer scheme guide", "OpportunityHub is a free, independent guide to government scholarships and farmer schemes in India, with links to the official source for every scheme.", "about.html", body)



# ---------------- career guidance pages ----------------
TYPE_LABELS = {"stream_choice": "Stream choice", "certificate": "Certificate / short course", "degree": "Degree", "diploma": "Diploma",
               "professional": "Professional course", "govt_job": "Government job", "private_job": "Private job", "competitive_exam": "Competitive exam",
               "skill": "Skill development", "freelancing": "Freelancing", "entrepreneurship": "Entrepreneurship", "study_abroad": "Study abroad"}
DEFAULT_FEES = "Fees change every year and differ by college and state, so they are not listed here. Check the fee structure on the official admission site before you decide."


def load_careers():
    rd = lambda p: json.load(open(p, encoding="utf-8"))
    d = os.path.join(ROOT, "data", "careers")
    paths = []
    for f in sorted(glob.glob(os.path.join(d, "paths_*.json"))):
        paths += rd(f)
    guides = rd(os.path.join(d, "guides.json"))
    for p in paths:
        p["slug"] = p["id"].replace("_", "-")
    return paths, guides


def stage_slug(st):
    return "career-" + st.replace("_", "-")


def career_detail(p, by_id, guides):
    name, path = p["title"], f"career/{p['slug']}.html"
    label = TYPE_LABELS.get(p["type"], p["type"])
    title = title_for(name, "Eligibility, Exams, Jobs")
    desc = trim(p["summary"], 155)
    exams = p.get("entrance_exams") or []
    faqs = [(f"What is {name}?", p["summary"]), (f"Who can join {name}?", p["qualification"])]
    if exams:
        faqs.append((f"Which exams or entry routes are used for {name}?", "; ".join(x["name"] for x in exams) + ". Always confirm dates and rules on the official website."))
    if p.get("opportunities"):
        faqs.append((f"What can you do after {name}?", "; ".join(p["opportunities"]) + "."))
    first = (p["stages"] or [""])[0]
    b = [f'<div class="card"><p class="meta"><a href="/career.html">Career guidance</a> › <a href="/{stage_slug(first)}.html">{E(guides["stages"][first]["title"])}</a></p><h1>{E(name)}</h1>'
         f'<p><b>{E(label)}</b></p><p>{E(p["summary"])}</p>'
         '<div class="contact"><b>Not sure what suits you?</b><br>Answer a few questions and get options matched to your stage, interests and budget.<br>'
         '<a class="mail" href="/index.html">Find my best options</a></div>']
    b.append("<h2>Who can join</h2><p>" + E(p["qualification"]) + "</p>")
    if p.get("courses"):
        b.append("<h2>Courses and options inside this path</h2>" + ul(p["courses"]))
    if exams:
        b.append("<h2>Entrance exams and entry routes</h2><ul>" + "".join(
            f'<li>{E(x["name"])}' + (f' – <a href="{E(x["url"])}" target="_blank" rel="noopener nofollow">official site</a>' if x.get("url") else "") + "</li>" for x in exams) + "</ul>")
    if p.get("opportunities"):
        b.append("<h2>What you can do after this</h2>" + ul(p["opportunities"]))
    if p.get("next_steps"):
        b.append("<h2>Next steps</h2>" + ol(p["next_steps"]))
    if p.get("official_links"):
        b.append("<h2>Official links</h2><ul>" + "".join(
            f'<li><a href="{E(x["url"])}" target="_blank" rel="noopener nofollow">{E(x["label"])}</a></li>' for x in p["official_links"]) + "</ul>")
    b.append(f'<p class="meta">{E(p.get("fees_note") or DEFAULT_FEES)} {E(guides["disclaimer"])}</p></div>')
    b.append('<div class="card"><h2>Frequently asked questions</h2>' + "".join(f"<details><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in faqs) + "</div>")
    rel = [by_id[i] for i in guides["stages"][first]["path_ids"] if i in by_id and i != p["id"] and by_id[i]["type"] == p["type"]][:5]
    if rel:
        b.append('<div class="card"><h2>Related options</h2><ul class="rel">' + "".join(f'<li><a href="/career/{x["slug"]}.html">{E(x["title"])}</a></li>' for x in rel) + "</ul></div>")
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}
    return path, page(title, desc, path, "".join(b), schema)


def career_stage_page(st, info, by_id, guides):
    path = f"{stage_slug(st)}.html"
    items = [by_id[i] for i in info["path_ids"] if i in by_id]
    low = info["title"][0].lower() + info["title"][1:]
    h1 = f"Courses and career options {low} in India {YEAR}"
    groups = {}
    for x in items:
        groups.setdefault(TYPE_LABELS.get(x["type"], x["type"]), []).append(x)
    body = [f'<div class="card"><p class="meta"><a href="/career.html">Career guidance</a></p><h1>{E(h1)}</h1><p>{E(info["summary"])}</p>'
            + (ul(info["key_points"]) if info.get("key_points") else "") + f'<p class="meta">{len(items)} options below, from short courses to degrees, exams and jobs. '
            '<a href="/index.html">Get options matched to you</a>.</p></div>']
    for g, xs in groups.items():
        body.append(f'<div class="card"><h2>{E(g)}</h2><ul class="rel">' + "".join(
            f'<li><a href="/career/{x["slug"]}.html"><b>{E(x["title"])}</b></a><br><span class="meta">{E(trim(x["summary"], 130))}</span></li>' for x in xs) + "</ul></div>")
    title = trim(h1, 66)
    desc = trim(f"{len(items)} study, training, exam and job options {low}: who can join, entrance exams, official links and what to do next.", 155)
    schema = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{SITE}/career/{x['slug']}.html", "name": x["title"]} for i, x in enumerate(items)]}
    return path, page(title, desc, path, "".join(body), schema, wide=True)


def career_hub(paths, guides):
    path = "career.html"
    body = [f'<div class="card"><h1>Career guidance: study options after 10th, 12th, diploma and graduation</h1>'
            f'<p>{len(paths)} study and career options explained in simple language: who can join, which exams, official links and what you can do next. Pick where you are now.</p>'
            '<p class="meta">General information only. Always confirm details on the official website. <a href="/index.html">Get options matched to you</a>.</p></div>']
    body.append('<div class="card"><h2>Where are you now?</h2><ul class="rel">' + "".join(
        f'<li><a href="/{stage_slug(k)}.html"><b>{E(v["title"])}</b></a> <span class="meta">· {len(v["path_ids"])} options</span></li>' for k, v in guides["stages"].items()) + "</ul></div>")
    title = "Career guidance in India: courses and jobs after 10th, 12th, graduation | OpportunityHub"
    return path, page(trim(title, 66) if len(title) > 66 else title, "Find courses, diplomas, exams and jobs after 10th, 12th, diploma, graduation and post-graduation, with entrance exams and official links.", path, "".join(body), wide=True)


def write(rel, content):
    p = os.path.join(FE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)


def patch_index(sch, far):
    p = os.path.join(FE, "index.html")
    s = open(p, encoding="utf-8").read()
    s = re.sub(r"<title>.*?</title>", "<title>OpportunityHub: Government Scholarships and Farmer Schemes in India</title>", s, 1, re.S)
    d = "Find government scholarships, farmer schemes (yojana) and career guidance in India. See who is eligible, documents needed and how to apply, with official links. Free."
    s = re.sub(r'<meta name="description" content=".*?">', f'<meta name="description" content="{E(d)}">', s, 1)
    s = re.sub(r'<link rel="canonical" href=".*?">\n?', "", s)           # always point to the current SITE
    s = s.replace("</title>", f'</title>\n<link rel="canonical" href="{SITE}/">', 1)
    s = re.sub(r'<meta property="og:url" content=".*?">', "", s)
    s = s.replace('<meta property="og:image"', f'<meta property="og:url" content="{SITE}/"><meta property="og:image"', 1)
    s = re.sub(r'(<meta property="og:image" content=")[^"]*(banner-share\.jpg")', rf'\g<1>{SITE}/\g<2>', s)
    top = [x for x in sch if not x.get("state")][:8]
    blk = ('<!--SEO-BROWSE--><section class="browse"><div class="bsplit">'
           '<picture><source srcset="laptop-mockup.webp" type="image/webp"><img src="laptop-mockup.jpg" width="750" height="513" loading="lazy" '
           'alt="OpportunityHub on a laptop: scholarships, farmer schemes and career guidance"></picture>'
           '<div class="btext"><h2>Browse without logging in</h2>'
           '<p>Read eligibility, documents and how to apply for government scholarships and farmer schemes, and see study and career options after 10th, 12th and graduation. Free, no account needed.</p>'
           '<div class="bbtn"><a href="/scholarships.html">All scholarships</a><a href="/yojana.html">All farmer schemes</a><a href="/career.html">Career guidance</a></div></div></div><ul>'
           + "".join(f'<li><a href="/scholarship/{x["slug"]}.html">{E(x["name"])}</a></li>' for x in top)
           + '</ul></section><!--/SEO-BROWSE-->'
           '<!--HELP--><section class="helpband"><picture><source srcset="support-help.webp" type="image/webp"><img src="support-help.jpg" width="900" height="687" loading="lazy" alt="Helpful support team at work"></picture>'
           f'<div><h2>Need help? Write to us</h2><p>Have a question, found a wrong detail, or stuck while logging in? Send us an email and we will get back to you as soon as we can.</p>'
           f'<a class="mailbtn" href="mailto:{EMAIL}?subject=OpportunityHub%20help">{EMAIL}</a><a class="faqlink" href="/faq.html">Read the FAQ</a></div></section><!--/HELP-->')
    s = re.sub(r"<!--SEO-BROWSE-->.*?<!--/SEO-BROWSE-->", "", s, flags=re.S)
    s = re.sub(r"<!--HELP-->.*?<!--/HELP-->", "", s, flags=re.S)
    s = s.replace('<footer class="sitefoot">', blk + '\n<footer class="sitefoot">', 1)
    if ".browse{" not in s:
        s = s.replace("</style>", """  .browse{max-width:720px;margin:0 auto;padding:10px 20px 10px;text-align:center}.browse h2{color:var(--brand);font-size:20px;margin:0 0 6px}
  .browse p{color:var(--soft);font-size:14px;margin:0 0 10px}.bbtn{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:12px}
  .bbtn a{background:var(--brand);color:#fff;padding:10px 18px;border-radius:10px;text-decoration:none;font-weight:700;font-size:14px}
  .browse ul{list-style:none;padding:0;margin:0;font-size:13.5px}.browse li{margin:4px 0}.browse li a{color:var(--brand);font-weight:600;text-decoration:none}
</style>""", 1)
    s = s.replace('·<a href="faq.html">FAQ</a>', '·<a href="faq.html">FAQ</a>·<a href="about.html">About</a>') if 'about.html">About' not in s else s
    open(p, "w", encoding="utf-8").write(s)


GA_BLOCK = ('<!--GA--><script async src="https://www.googletagmanager.com/gtag/js?id={id}"></script><script>window.dataLayer=window.dataLayer||[];'
            "function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{id}');</script><!--/GA-->")
ADS_BLOCK = '<!--ADS--><script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={id}" crossorigin="anonymous"></script><!--/ADS-->'
GA_SENT = "We use Google Analytics to count visits (pages viewed, device type and approximate location) in aggregate. It places cookies in your browser."
ADS_SENT = ("This site shows ads served by Google AdSense. Google and other third-party vendors use cookies to show ads based on your visits to this site and other websites. "
            "You can opt out of personalised ads in Google's Ads Settings (adssettings.google.com) or at www.aboutads.info.")
NO_ADS_SENT = "We do not use advertising or tracking cookies."


def cookie_sentence():
    if ADSENSE:
        return (GA_SENT + " " if GA_ID else "") + ADS_SENT + " You can also block cookies in your browser settings."
    if GA_ID:
        return GA_SENT + " We do not use advertising cookies and we do not sell this data. You can block analytics cookies in your browser settings."
    return NO_ADS_SENT


def inject_analytics():
    """Adds (or removes) the Google AdSense and Google Analytics tags on every public page and keeps the privacy policy truthful."""
    for f in glob.glob(os.path.join(FE, "**", "*.html"), recursive=True):
        if os.path.basename(f) == "admin.html":
            continue
        s = open(f, encoding="utf-8").read()
        s = re.sub(r"<!--ADS-->.*?<!--/ADS-->", "", s, flags=re.S)
        s = re.sub(r'<script async src="https://pagead2\.googlesyndication\.com/pagead/js/adsbygoogle\.js\?client=ca-pub-\d+" crossorigin="anonymous"></script>\s*', "", s)   # a copy pasted by hand
        s = re.sub(r"<!--GA-->.*?<!--/GA-->", "", s, flags=re.S)
        if ADSENSE:
            s = s.replace("<head>", "<head>" + ADS_BLOCK.format(id=ADSENSE), 1)          # right at the start of <head>, as AdSense asks
        if GA_ID:
            s = s.replace("</head>", GA_BLOCK.format(id=GA_ID) + "</head>", 1)
        if os.path.basename(f) == "privacy.html":
            s = re.sub(r"<!--PRIV-COOKIES-->.*?<!--/PRIV-COOKIES-->", lambda m: f"<!--PRIV-COOKIES-->{cookie_sentence()}<!--/PRIV-COOKIES-->", s, flags=re.S)
            s = re.sub(r"<!--PRIV-ADS-->.*?<!--/PRIV-ADS-->", lambda m: "<!--PRIV-ADS-->" + (". This site shows ads served by Google AdSense (see section 5)." if ADSENSE else " and we do not show advertising.") + "<!--/PRIV-ADS-->", s, flags=re.S)
        open(f, "w", encoding="utf-8").write(s)
    ads_txt = os.path.join(FE, "ads.txt")                                                # tells ad buyers that this publisher ID is allowed to sell your ad space
    if ADSENSE:
        open(ads_txt, "w").write(f"google.com, pub-{ADSENSE[len('ca-pub-'):]}, DIRECT, f08c47fec0942fa0\n")
    elif os.path.exists(ads_txt):
        os.remove(ads_txt)


def make_clean_urls():
    """Rewrite every address to its extension-less form (/privacy.html -> /privacy, /index.html -> /) in pages, sitemap and JSON-LD."""
    def rel(m):
        path = m.group(2)
        return f'{m.group(1)}"/{"" if path == "index" else path}{m.group(3) or ""}"'
    for f in glob.glob(os.path.join(FE, "**", "*.html"), recursive=True) + [os.path.join(FE, "sitemap.xml")]:
        s = open(f, encoding="utf-8").read()
        s = re.sub(r'(href=)"/?((?!https?:|mailto:|//)[A-Za-z0-9_\-/]+?)\.html(#[^"]*)?"', rel, s)          # our own links, absolute or relative
        s = re.sub(re.escape(SITE) + r'/([^"\s<>]*?)\.html', lambda m: SITE + "/" + ("" if m.group(1) == "index" else m.group(1)), s)   # canonical, og:url, sitemap, JSON-LD
        open(f, "w", encoding="utf-8").write(s)


def not_found_page():
    return page("Page not found | OpportunityHub", "This page could not be found.", "404.html",
                '<div class="card"><h1>Page not found</h1><p>We could not find that page. Try the <a href="/index.html">home page</a>, '
                '<a href="/scholarships.html">scholarships</a>, <a href="/yojana.html">farmer schemes</a> or <a href="/career.html">career guidance</a>.</p></div>')


def main():
    sch, far = load()
    allp, urls = sch + far, ["", "scholarships.html", "yojana.html", "faq.html", "about.html", "privacy.html", "terms.html"]
    for d in ("scholarship", "yojana"):                       # rebuild from scratch so removed schemes disappear
        for f in glob.glob(os.path.join(FE, d, "*.html")):
            os.remove(f)
    report = []
    for e in allp:
        path, html_, title, desc = detail(e, allp)
        write(path, html_); urls.append(path); report.append((len(title), len(desc), path))
    for kind, items in (("scholarship", sch), ("yojana", far)):
        path, h = hub(kind, items); write(path, h)
    write("about.html", about())
    write("404.html", not_found_page().replace(f'<link rel="canonical" href="{SITE}/404.html">', '<meta name="robots" content="noindex">'))
    cpaths, cguides = load_careers()
    cby = {x["id"]: x for x in cpaths}
    for f in glob.glob(os.path.join(FE, "career", "*.html")):
        os.remove(f)
    for x in cpaths:
        pth, h = career_detail(x, cby, cguides); write(pth, h); urls.append(pth)
    for st, info in cguides["stages"].items():
        pth, h = career_stage_page(st, info, cby, cguides); write(pth, h); urls.append(pth)
    pth, h = career_hub(cpaths, cguides); write(pth, h); urls.append(pth)
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{SITE}/{u}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /admin.html\n\nSitemap: {SITE}/sitemap.xml\n")
    patch_index(sch, far)
    for f in ("privacy.html", "terms.html", "faq.html"):                 # add About to the footer of the older pages
        p = os.path.join(FE, f); s = open(p, encoding="utf-8").read()
        if 'about.html">About' not in s:
            open(p, "w", encoding="utf-8").write(s.replace('<a href="faq.html">FAQ</a>·<a href="faq.html#contact">', '<a href="faq.html">FAQ</a>·<a href="about.html">About</a>·<a href="faq.html#contact">'))
    inject_analytics()
    if CLEAN:
        make_clean_urls()
    print(f"adsense = {ADSENSE or 'off'}; clean urls = {CLEAN}; {len(cpaths)} career pages, {len(cguides['stages'])} stage pages, analytics = {GA_ID or 'off'}")
    print(f"{len(sch)} scholarship pages + {len(far)} yojana pages, sitemap with {len(urls)} URLs, site = {SITE}")
    print(f"longest title {max(r[0] for r in report)} chars, longest description {max(r[1] for r in report)} chars")


main()
