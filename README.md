# OpportunityHub
Run locally: `pip install -r requirements.txt && uvicorn app.main:app --reload`
Seed: `python seed_scholarships.py` (needs DATABASE_URL set, same as the app)
Render start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`  (set JWT_SECRET and DATABASE_URL)
Frontend: open frontend/index.html (API URL is set at the top of the <script>).
The new application_steps column is added automatically on startup.
