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


## Sending OTP from your own Gmail (no domain needed)
Set `EMAIL_PROVIDER=gmail_api` on Render, plus `EMAIL_FROM` (your Gmail), `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`.
It uses the Gmail API over HTTPS, so it works on Render's free plan (Render blocks SMTP ports 25/465/587 on free web services, so `EMAIL_PROVIDER=gmail` with an App Password only works on a paid plan or another host).
Gmail allows roughly 500 recipients per day for a normal account; every OTP is one mail. Per-user limits (60 s, 5/hour) and per-IP limits (`OTP_IP_LIMIT` 30, `VERIFY_IP_LIMIT` 100 per hour) stay far below that for normal use.
One-time token setup: Google Cloud Console -> new project -> enable Gmail API -> OAuth consent screen (External) -> **Publish app (In production)**, otherwise the refresh token dies after 7 days -> Credentials -> OAuth client ID (Web) with redirect URI `https://developers.google.com/oauthplayground` -> in OAuth Playground (gear icon: use your own credentials) authorize scope `https://www.googleapis.com/auth/gmail.send` -> exchange for tokens -> copy the refresh token.
Server log on failure: `[OTP] email delivery failed: RuntimeError Gmail ...` (`invalid_grant` = refresh token expired/revoked).

## Email verification (OTP) and forgot password
Signup: name + phone (your login ID) + email -> Send OTP -> code arrives by email -> Verify -> choose password. Forgot password: phone + the email used at signup -> OTP by email -> new password. Old accounts without an email can add one after login (purpose `add_email`).
Rules: 6-digit code from Python's `secrets`, valid **5 minutes**, single use, max **5** wrong tries per code, **60 s** between sends, 5 sends per email per hour, per-IP limits, a new code cancels every older one. Codes are tied to email + purpose (`signup`, `reset`, `add_email`), so a signup code can never reset a password. Only a keyed HMAC hash is stored, never the code, and the code is never returned by the API, shown on screen or logged. Attempt counting and "mark as used" are single conditional UPDATEs, so parallel requests cannot exceed 5 tries or use one code twice.
Signup/reset/add-email replies do not reveal whether an email already has an account (same reply and same throttling; no mail is sent in that case, so the page says "If this email can be used, a code is on its way").
Codes are sent ONLY through Brevo. There is no test mode, no console provider and no switch to skip verification. If Brevo does not accept the mail, the new code is cancelled and the user sees "Unable to send verification email".

**Production guard:** when `RENDER` or `APP_ENV=production` is set, the server refuses to start if `JWT_SECRET` is missing/default/shorter than 16 characters, `DATABASE_URL` is missing, `EMAIL_PROVIDER` is not `brevo`, `BREVO_API_BASE` is set, or any of `OTP_DEV_ECHO`, `OTP_BYPASS`, `OTP_TEST_MODE`, `SKIP_OTP`, `DISABLE_OTP`, `OTP_REQUIRED=false` is present (see `app/config_guard.py`).

Environment variables (Render -> Environment; placeholders in `.env.example`):
| Variable | Meaning |
|---|---|
| `DATABASE_URL` | required |
| `JWT_SECRET` | required, long random string; also keys the code hashes. Changing it logs everyone out |
| `EMAIL_PROVIDER` | must be `brevo` |
| `BREVO_API_KEY` | your Brevo API key (secret, never put it in code) |
| `EMAIL_FROM` | a sender address verified in Brevo |
| `EMAIL_FROM_NAME` | optional, default OpportunityHub |
| `OTP_IP_LIMIT` | optional, default 10: code requests per network address per hour |
| `VERIFY_IP_LIMIT` | optional, default 40: code checks per network address per hour |
| `LOGIN_FAIL_LIMIT` | optional, default 8: wrong passwords per network address + phone per 15 minutes |
| `APP_ENV` | optional; `production` turns the production guard on outside Render |

Database: **no migration needed.** The existing `otp_codes` table is reused (the `phone` column holds the target email). Timestamps are timezone-aware in Python and stored as UTC in the existing columns.

Brevo free plan: about 300 emails per day in total (check Brevo's pricing page, it can change). Every OTP is one email, so roughly 300 verifications a day at most. Beyond that Brevo stops sending and users see the delivery-error message.

Tests (no real email is sent; a fake mailer exists only inside `tests/`):
    pip install -r requirements-dev.txt
    python -m unittest discover -v

Accounts created before this change have no email on file. After they log in, the page shows an "Add your email" box (code by email, then saved), and from then on "Forgot password" works for them.

## Getting codes into Gmail inboxes
Brevo cannot authenticate a free sender such as @gmail.com, so it replaces the sender and Gmail/Yahoo/Outlook are likely to reject the mail or send it to spam.
Use `EMAIL_FROM` on a domain you own (e.g. no-reply@yourdomain.in) and authenticate that domain in Brevo: Brevo code + DKIM + DMARC (Brevo -> Senders, Domains & Dedicated IPs -> Domains).
The server prints `[EMAIL SETUP WARNING]` at start-up and admin.html shows a red box when the setup looks wrong.

## Security behaviour
- Password reset signs out every earlier login of that account.
- Rate limits (in memory, per server process, reset on restart): code requests per IP, code checks per IP, wrong passwords. The per-email limits (60 s cooldown, 5 per hour) are stored in the database and survive restarts.
- Private answers (profile, matches, saved list, auth) are sent with `Cache-Control: no-store`.
- The page wipes all of the previous account's data on logout and before every login, and ignores answers that arrive late for a previous account.


---

## Farmers and Career Guidance sections (added)

Two public sections (no login needed) now sit next to Scholarships, behind a small nav bar at the top of `index.html`:
`#farmers` and `#careers` also work as direct links (e.g. `https://your-site/#farmers`). Login, OTP and registration are untouched.

### Files added
- Backend: `app/routers/farmers.py`, `app/routers/careers.py`, `app/services/career_service.py`
- Frontend: `frontend/sections.css`, `frontend/farmers.js`, `frontend/careers.js` (**upload these next to `index.html`**)
- Data: `data/farmers/*.json`, `data/careers/*.json`
- Scripts: `seed_farmers.py`, `check_new_sections.py`

### Files edited (all changes are additive)
`app/main.py` (2 routers), `app/models/core.py` + `app/migrate.py` (4 new optional columns on `opportunities`: `sub_category`, `eligibility_text`, `tags`, `source_checked_on`), `app/schemas/schemas.py` (4 optional fields), `app/routers/opportunities.py` and `app/services/eligibility_service.py` (student lists skip farmer schemes; admin edit only changes fields it receives), `frontend/index.html` (nav + 2 containers + script tags), `frontend/admin.html` (farmer fields in the form).

### Farmer schemes
Farmer schemes are rows of the existing `opportunities` table with `category = farmer_scheme`, so admin.html, Verify, Archive and `check_freshness.py` work for them.
1. Add or edit entries in `data/farmers/*.json` (one file per state is fine; format is described at the top of `seed_farmers.py`).
2. `python seed_farmers.py` adds new ones; `python seed_farmers.py --update` pushes edits (changed schemes go back to NEEDS_REVIEW).
3. Open admin.html, check the official link, press **Verify**. The site then shows "Verified <date>"; until then it shows "Official source checked <date> · awaiting final review".
`data/farmers/_queue.md` lists schemes still to research. Nothing in it is shown on the site.

### Career guidance
All content is in `data/careers/` (`paths_*.json`, `guides.json`, `questionnaire.json`). Edit a file and redeploy; no code change. Recommendations are a transparent score (stage, stream, interests, skills, goal, budget) with the reasons shown to the student. Fees are deliberately not listed: they are not verified here, so each path points to the official admission site.

### Checks
`python check_new_sections.py` (structure) and `python check_new_sections.py --urls` (opens every official link; run it on your own computer).

### One thing to check on your side
`frontend/index.html` has `const API = "https://gsa-app.onrender.com"`. Make sure that is your live backend; the new sections use the same `API` value.
