"""Checks the scholarship / farmer-scheme data files and runs the real matching engine on them.
Standard library only: runs without FastAPI or a database. Same load rules as seed_all.py and farmer_loader.py."""
import glob, json, os, re, unittest
from datetime import datetime
from types import SimpleNamespace as NS
from app.services.eligibility_service import evaluate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
read = lambda p: json.load(open(p, encoding="utf-8"))
SUB = {"crop_insurance", "irrigation", "solar_pump", "equipment", "financial", "loans", "other"}
TAGS = {"any_farmer", "small_marginal", "landowner", "tenant", "landless", "sc_st", "women", "fpo_coop"}
FIELDS = {"country", "state", "study_state", "age", "gender", "education_level", "marks_percent", "course_stream",
          "family_income", "category", "is_disabled", "target_countries", "interests"}
OPS = {"eq", "neq", "in", "not_in", "gte", "lte", "gt", "lt", "is_true"}

STEPS = read(os.path.join(ROOT, "data", "steps.json"))
SCHOLARSHIPS = []
for f in sorted(glob.glob(os.path.join(ROOT, "data", "*.json"))):
    if os.path.basename(f) not in ("steps.json", "sources.json"):
        SCHOLARSHIPS += read(f)
FARMERS = []
for f in sorted(glob.glob(os.path.join(ROOT, "data", "farmers", "*.json"))):
    if not os.path.basename(f).startswith("_"):
        FARMERS += read(f)
BY_NAME = {e["name"]: e for e in SCHOLARSHIPS}


def opp(name):
    e = next(e for n, e in BY_NAME.items() if n.startswith(name))
    return NS(eligibility_rules=e["eligibility_rules"], country="IN", state=e.get("state"), state_basis=e.get("state_basis", "domicile"))


def student(**kw):
    base = dict(country="IN", state="Maharashtra", study_state=None, age=19, gender="male", education_level="bachelors", marks_percent=70,
                course_stream="science", family_income=200000, category="general", is_disabled=False)
    base.update(kw)
    return NS(**base)


class DataFiles(unittest.TestCase):
    def test_scholarships_load_like_seed_all(self):
        self.assertGreater(len(SCHOLARSHIPS), 30)
        for e in SCHOLARSHIPS:
            for k in ("name", "official_url", "eligibility_rules", "steps"):
                self.assertIsNotNone(e.get(k), (e.get("name"), k))
            self.assertIn(e["steps"], STEPS, e["name"])
            self.assertTrue(e["official_url"].startswith("https://"), e["name"])
            if e.get("deadline"):
                datetime.strptime(e["deadline"], "%Y-%m-%d")
            for field, ops in e["eligibility_rules"].items():
                self.assertIn(field, FIELDS, e["name"]); self.assertTrue(set(ops) <= OPS, e["name"])
        names = [e["name"] for e in SCHOLARSHIPS]
        self.assertEqual(len(names), len(set(names)), "duplicate scholarship name")

    def test_farmer_schemes_load_like_farmer_loader(self):
        self.assertGreater(len(FARMERS), 15)
        for e in FARMERS:
            for k in ("name", "sub_category", "official_url", "steps", "checked_on", "eligibility_text"):
                self.assertTrue(e.get(k), (e.get("name"), k))
            self.assertIn(e["sub_category"], SUB); self.assertTrue(set(e.get("tags", [])) <= TAGS)
            self.assertTrue(e["official_url"].startswith("https://"))
            datetime.strptime(e["checked_on"], "%Y-%m-%d")
        self.assertEqual(len({e["name"] for e in FARMERS}), len(FARMERS))

    def test_every_steps_template_has_matching_english_and_hindi(self):
        for name, t in STEPS.items():
            self.assertEqual(len(t["en"]), len(t["hi"]), name)
            self.assertTrue(all(s.strip() for s in t["en"] + t["hi"]), name)


class Matching(unittest.TestCase):
    def match(self, name, **kw):
        return evaluate(student(**kw), opp(name))

    def test_girl_sees_pragati_boy_does_not(self):
        self.assertNotEqual(self.match("AICTE Pragati", gender="female", family_income=600000)["match"], "excluded")
        self.assertEqual(self.match("AICTE Pragati", gender="male", family_income=600000)["match"], "excluded")
        self.assertEqual(self.match("AICTE Pragati", gender="female", family_income=900000)["match"], "excluded")

    def test_disability_schemes(self):
        for n in ("AICTE Saksham", "Post-Matric Scholarship for Students with Disabilities"):
            self.assertNotEqual(self.match(n, is_disabled=True, family_income=200000)["match"], "excluded", n)
            self.assertEqual(self.match(n, is_disabled=False)["match"], "excluded", n)

    def test_pre_matric_sc_and_st(self):
        sc = self.match("Pre-Matric Scholarship for SC", education_level="10th", category="sc", family_income=200000)
        self.assertEqual(sc["match"], "high", sc)
        self.assertEqual(self.match("Pre-Matric Scholarship for SC", education_level="10th", category="st")["match"], "excluded")
        self.assertEqual(self.match("Pre-Matric Scholarship for ST", education_level="10th", category="st", family_income=300000)["match"], "excluded")
        self.assertEqual(self.match("Pre-Matric Scholarship for ST", education_level="bachelors", category="st")["match"], "excluded")

    def test_top_class_sc_needs_sc_category_and_income(self):
        self.assertNotEqual(self.match("Top Class Education Scheme for SC", category="sc", family_income=700000)["match"], "excluded")
        self.assertEqual(self.match("Top Class Education Scheme for SC", category="obc", family_income=300000)["match"], "excluded")
        self.assertEqual(self.match("Top Class Education Scheme for SC", category="sc", family_income=900000)["match"], "excluded")

    def test_ugc_pg_schemes_age_and_gender(self):
        self.assertNotEqual(self.match("UGC Post Graduate Indira Gandhi", gender="female", age=24)["match"], "excluded")
        self.assertEqual(self.match("UGC Post Graduate Indira Gandhi", gender="female", age=35)["match"], "excluded")
        self.assertEqual(self.match("UGC Post Graduate Indira Gandhi", gender="male", age=24)["match"], "excluded")
        self.assertEqual(self.match("UGC Post Graduate Merit Scholarship", age=35)["match"], "excluded")

    def test_inspire_she_age_stream(self):
        self.assertNotEqual(self.match("INSPIRE", education_level="12th", age=18, course_stream="science")["match"], "excluded")
        self.assertEqual(self.match("INSPIRE", education_level="12th", age=18, course_stream="commerce")["match"], "excluded")
        self.assertEqual(self.match("INSPIRE", education_level="12th", age=25, course_stream="science")["match"], "excluded")

    def test_state_schemes_only_for_that_state(self):
        self.assertNotEqual(self.match("CM Raitha Vidya Nidhi", state="Karnataka", education_level="bachelors")["match"], "excluded")
        self.assertEqual(self.match("CM Raitha Vidya Nidhi", state="Kerala", education_level="bachelors")["match"], "excluded")
        self.assertEqual(self.match("District Merit Scholarship (Kerala", state="Maharashtra", education_level="12th")["match"], "excluded")
        self.assertNotEqual(self.match("District Merit Scholarship (Kerala", state="Kerala", education_level="12th")["match"], "excluded")
        self.assertEqual(self.match("Mukhyamantri Kanya Utthan", state="Bihar", gender="male", education_level="bachelors")["match"], "excluded")

    def test_half_filled_profile_is_partial_not_excluded(self):
        p = NS(country="IN", state="Karnataka", study_state=None, age=None, gender=None, education_level=None, marks_percent=None,
               course_stream=None, family_income=None, category=None, is_disabled=None)
        self.assertEqual(evaluate(p, opp("AICTE Pragati"))["match"], "partial")

    def test_no_scholarship_crashes_on_a_blank_or_full_profile(self):
        blank = NS(**{k: None for k in ("country", "state", "study_state", "age", "gender", "education_level", "marks_percent",
                                         "course_stream", "family_income", "category", "is_disabled")})
        for e in SCHOLARSHIPS:
            o = NS(eligibility_rules=e["eligibility_rules"], country="IN", state=e.get("state"), state_basis=e.get("state_basis", "domicile"))
            for p in (blank, student(), student(category="sc", gender="female", is_disabled=True, education_level="12th")):
                self.assertIn(evaluate(p, o)["match"], ("high", "partial", "excluded"), e["name"])


if __name__ == "__main__":
    unittest.main()
