# OpportunityHub
Run locally: `pip install -r requirements.txt && uvicorn app.main:app --reload`
Seed: `python seed_scholarships.py` (needs DATABASE_URL set, same as the app)
Render start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`  (set JWT_SECRET and DATABASE_URL)
Frontend: open frontend/index.html (API URL is set at the top of the <script>).
The new application_steps column is added automatically on startup.

## Seeding
1. `export DATABASE_URL=<your Neon connection string>`
2. `python seed_scholarships.py`      (3 central NSP schemes)
3. `python seed_maharashtra.py`       (Maharashtra state schemes)
Re-running is safe. Everything lands as NEEDS_REVIEW — open /frontend/admin.html, check each on the official site, press Verify.

## Auto-expiry
Any scholarship whose deadline day has passed is switched off automatically (status EXPIRED) on startup and on every browse/matches/admin request.
Deadline left empty = never expires (rolling schemes). To reopen next year: Admin -> Edit -> set the new deadline -> Save; it returns as NEEDS_REVIEW.
