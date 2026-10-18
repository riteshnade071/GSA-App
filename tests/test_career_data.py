import glob, json, os, unittest

D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "careers")
REQ = ["id", "title", "type", "stages", "streams", "interests", "skills", "goals", "budget_level", "summary", "qualification",
       "courses", "entrance_exams", "opportunities", "next_steps", "official_links", "scholarship_keywords"]


def load():
    paths = []
    for f in sorted(glob.glob(os.path.join(D, "paths_*.json"))):
        paths += json.load(open(f, encoding="utf-8"))
    return paths, json.load(open(os.path.join(D, "guides.json"), encoding="utf-8")), json.load(open(os.path.join(D, "questionnaire.json"), encoding="utf-8"))


class CareerData(unittest.TestCase):
    def test_every_path_is_complete_and_listed_in_its_stages(self):
        paths, guides, q = load()
        opts = {x["id"]: {o["value"] for o in x.get("options", [])} for x in q["questions"]}
        ids = [p["id"] for p in paths]
        self.assertEqual(len(ids), len(set(ids)), "duplicate path ids")
        for p in paths:
            for k in REQ:
                self.assertIn(k, p, f"{p['id']} is missing {k}")
            for st in p["stages"]:
                self.assertIn(p["id"], guides["stages"][st]["path_ids"], f"{p['id']} not listed in stage {st}")
            for key, field in (("interests", "interests"), ("skills", "skills"), ("goals", "goal"), ("streams", "stream")):
                for v in p[key]:
                    self.assertIn(v, opts[field], f"{p['id']}: unknown {key} value {v}")
            for link in p["official_links"] + [e for e in p["entrance_exams"] if e.get("url")]:
                self.assertTrue(link["url"].startswith("https://"), f"{p['id']}: {link}")
        for st, info in guides["stages"].items():
            for i in info["path_ids"]:
                self.assertIn(i, ids, f"stage {st} lists unknown path {i}")

    def test_enough_options_per_stage(self):
        _, guides, _ = load()
        self.assertGreaterEqual(len(guides["stages"]["after_10th"]["path_ids"]), 12)
        self.assertGreaterEqual(len(guides["stages"]["after_12th"]["path_ids"]), 40)


if __name__ == "__main__":
    unittest.main()
