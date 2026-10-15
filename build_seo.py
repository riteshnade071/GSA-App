"""
Builds the PUBLIC, crawlable pages (no login) from the same data files the app uses.

    python build_seo.py https://your-site.netlify.app          (your real frontend URL, no trailing slash)

Writes into frontend/:  scholarship/<slug>.html   yojana/<slug>.html   scholarships.html   yojana.html
                        sitemap.xml   robots.txt   and refreshes the "Browse" block + title/description in index.html.
Safe to re-run any time (after editing data/*.json). Nothing is invented: every fact on a page comes from the data files.
"""
import glob, html, json, os, re, sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
FE = os.path.join(ROOT, "frontend")
SITE = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("SITE_URL", "https://opportunity-hub-pwsy.onrender.com")).rstrip("/")
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
       '<a href="/scholarships.html">Scholarships</a><a href="/yojana.html">Farmer schemes</a><a href="/faq.html">FAQ</a></span></div>')
FOOT = ('<div class="foot"><a href="/privacy.html">Privacy Policy</a>·<a href="/terms.html">Terms of Service</a>·<a href="/faq.html">FAQ</a>·'
        '<a href="/about.html">About</a>·<a href="/faq.html#contact">Contact us</a></div>')


def page(title, desc, path, body, schema=None):
    url = f"{SITE}/{path}"
    ld = f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>' if schema else ""
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{url}">
<meta property="og:type" content="website"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{url}">
<meta name="theme-color" content="#6B21A8"><link href="https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/legal.css">{ld}</head><body>{NAV}<div class="page">{body}</div>{FOOT}</body></html>'''


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
    return path, page(title, desc, path, "".join(body), schema)


def about():
    body = f'''<div class="card"><h1>About OpportunityHub</h1>
<p>OpportunityHub is a free, independent website that helps students and farmers in India find government scholarships and schemes in one place, and check which ones may suit them.</p>
<h2>What we do</h2><p>We collect scheme details from official government sources, write them in simple language, and link to the official website for every scheme so you can apply there. We do not charge any fee and we do not apply on your behalf.</p>
<h2>How we keep information correct</h2><p>Every scheme page shows its official source. Deadlines and amounts can change, so please confirm on the official website before applying. If you find a mistake, email us and we will fix it.</p>
<h2>Independent project</h2><p>We are not a government body and not affiliated with any scheme listed here. Read our <a href="/terms.html">Terms</a> and <a href="/privacy.html">Privacy Policy</a>.</p>
<h2>Contact</h2><p><a href="mailto:{EMAIL}">{EMAIL}</a></p></div>'''
    return page("About OpportunityHub: free scholarship and farmer scheme guide", "OpportunityHub is a free, independent guide to government scholarships and farmer schemes in India, with links to the official source for every scheme.", "about.html", body)


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
    blk = ('<!--SEO-BROWSE--><section class="browse"><h2>Browse without logging in</h2>'
           '<p>Read eligibility, documents and how to apply for government scholarships and farmer schemes. Free, no account needed.</p>'
           '<div class="bbtn"><a href="/scholarships.html">All scholarships</a><a href="/yojana.html">All farmer schemes</a></div><ul>'
           + "".join(f'<li><a href="/scholarship/{x["slug"]}.html">{E(x["name"])}</a></li>' for x in top)
           + '</ul></section><!--/SEO-BROWSE-->')
    s = re.sub(r"<!--SEO-BROWSE-->.*?<!--/SEO-BROWSE-->", "", s, flags=re.S)
    s = s.replace('<footer class="sitefoot">', blk + '\n<footer class="sitefoot">', 1)
    if ".browse{" not in s:
        s = s.replace("</style>", """  .browse{max-width:720px;margin:0 auto;padding:10px 20px 10px;text-align:center}.browse h2{color:var(--brand);font-size:20px;margin:0 0 6px}
  .browse p{color:var(--soft);font-size:14px;margin:0 0 10px}.bbtn{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:12px}
  .bbtn a{background:var(--brand);color:#fff;padding:10px 18px;border-radius:10px;text-decoration:none;font-weight:700;font-size:14px}
  .browse ul{list-style:none;padding:0;margin:0;font-size:13.5px}.browse li{margin:4px 0}.browse li a{color:var(--brand);font-weight:600;text-decoration:none}
</style>""", 1)
    s = s.replace('·<a href="faq.html">FAQ</a>', '·<a href="faq.html">FAQ</a>·<a href="about.html">About</a>') if 'about.html">About' not in s else s
    open(p, "w", encoding="utf-8").write(s)


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
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{SITE}/{u}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nDisallow: /admin.html\n\nSitemap: {SITE}/sitemap.xml\n")
    patch_index(sch, far)
    for f in ("privacy.html", "terms.html", "faq.html"):                 # add About to the footer of the older pages
        p = os.path.join(FE, f); s = open(p, encoding="utf-8").read()
        if 'about.html">About' not in s:
            open(p, "w", encoding="utf-8").write(s.replace('<a href="faq.html">FAQ</a>·<a href="faq.html#contact">', '<a href="faq.html">FAQ</a>·<a href="about.html">About</a>·<a href="faq.html#contact">'))
    print(f"{len(sch)} scholarship pages + {len(far)} yojana pages, sitemap with {len(urls)} URLs, site = {SITE}")
    print(f"longest title {max(r[0] for r in report)} chars, longest description {max(r[1] for r in report)} chars")


main()
