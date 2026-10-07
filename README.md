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

## Monthly freshness check
`python check_freshness.py` lists schemes not verified for 30+ days, deadlines near/passed, and broken official links. Run it once a month, then fix in admin.html and press Verify.

## Auto-expiry
A scholarship whose deadline day has passed is switched off automatically (status EXPIRED). No deadline = never expires.
Reopen next year: Admin -> Edit -> new deadline -> Save (returns as NEEDS_REVIEW).

## Government notices (announcements)
Students see a "Latest notices" box (public, also before login) with admin-approved notices: all-India ones plus their state's.
- Add one by hand: admin.html -> Notices.
- Find new ones semi-automatically: `python check_notices.py` reads the portals listed in `data/sources.json` and saves new notice-looking links as DRAFTS. Nothing is shown to students until you read the official page and press Publish.
- Notices hide themselves after the "Hide after" date, or 90 days after publishing if no date is set.


## Email verification (OTP) and forgot password
Signup: name + phone (your login ID) + email -> Send OTP -> code arrives by email -> Verify -> choose password. Forgot password: phone + the email used at signup -> OTP by email -> new password.
Rules: 6-digit code, valid 10 minutes, 5 wrong tries per code, 30 s between sends, 5 sends per email per hour, a new code cancels the old one. Only a keyed hash of the code is stored. The code is never returned by the API, shown on screen or logged.
Codes are sent ONLY through Brevo. There is no test mode, no console provider and no switch to skip verification. If Brevo fails, the user sees "Unable to send verification email" and can retry.

Environment variables (Render -> Environment):
| Variable | Meaning |
|---|---|
| `EMAIL_PROVIDER` | must be `brevo` |
| `BREVO_API_KEY` | your Brevo API key (secret, never put it in code) |
| `EMAIL_FROM` | a sender address verified in Brevo |
| `EMAIL_FROM_NAME` | optional, default OpportunityHub |
| `JWT_SECRET` | required; also used to hash the codes |

Accounts created before this change by SMS/WhatsApp have no email on file, so they can still log in with phone + password but cannot use "Forgot password".
