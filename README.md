# OpportunityHub
Run locally: `pip install -r requirements.txt && uvicorn app.main:app --reload`
Render: build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, env: DATABASE_URL, JWT_SECRET, PYTHON_VERSION=3.12.8
Frontend: frontend/index.html (students) and frontend/admin.html. Set `const API` at the top of each <script> to your Render URL.

## Scholarship data (the only thing you ever need to touch for new schemes)
All data lives in `data/*.json`, one file per scope (central.json, maharashtra.json ...). Shared English+Hindi apply-steps are in `data/steps.json`.
Add a state = add `data/<state>.json` in the same format. No code change, no redeploy.

    set "DATABASE_URL=<neon link>"
    python seed_all.py             # inserts new schemes, fills blanks, never overwrites admin edits
    python seed_all.py --update    # makes the database match the JSON files; any scheme whose content changed goes back to NEEDS_REVIEW

Everything lands as NEEDS_REVIEW. Check each on the official site, then press Verify in admin.html.

## Auto-expiry
A scholarship whose deadline day has passed is switched off automatically (status EXPIRED). No deadline = never expires.
Reopen next year: Admin -> Edit -> new deadline -> Save (returns as NEEDS_REVIEW).
