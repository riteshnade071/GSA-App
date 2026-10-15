"""
Email OTP delivery. Three real providers, no test mode.

EMAIL_PROVIDER=brevo       Brevo HTTPS API (needs a sender on a domain you own, authenticated in Brevo)
  BREVO_API_KEY, EMAIL_FROM, EMAIL_FROM_NAME (optional)

EMAIL_PROVIDER=gmail_api   Gmail API over HTTPS (port 443). Works on Render's free plan. Mail goes out from your own Gmail.
  GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN (one-time OAuth setup), EMAIL_FROM = that Gmail address

EMAIL_PROVIDER=gmail       Gmail SMTP with an App Password (port 465). Render's FREE plan blocks SMTP ports, so use this
  only on a host/plan that allows outbound SMTP.   GMAIL_USER (or EMAIL_FROM), GMAIL_APP_PASSWORD

If anything is missing or the provider does not accept the mail, an error is raised and the new code is cancelled.
"""
import base64, json, os, smtplib, ssl, time, urllib.error, urllib.parse, urllib.request
from email.message import EmailMessage
from email.utils import formataddr

OTP_MINUTES = 5
UA = {"User-Agent": "OpportunityHub/1.0"}


def _content(code: str):
    subject = "Your OpportunityHub verification code"
    text = (f"Your OpportunityHub verification code is:\n\n{code}\n\n"
            f"This code is valid for {OTP_MINUTES} minutes and can be used only once.\n\n"
            "Do not share this code with anyone. OpportunityHub staff will never ask for it.\n\n"
            "If you did not request this code, you can safely ignore this email.")
    html = ('<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:16px">'
            '<h2 style="color:#6B21A8;margin:0 0 12px">OpportunityHub</h2><p>Your verification code is:</p>'
            f'<p style="font-size:32px;letter-spacing:6px;font-weight:bold;margin:8px 0">{code}</p>'
            f'<p>This code is valid for <b>{OTP_MINUTES} minutes</b> and can be used only once.</p>'
            '<p style="color:#B91C1C"><b>Do not share this code with anyone.</b> OpportunityHub staff will never ask for it.</p>'
            '<p style="color:#666;font-size:12px">If you did not request this code, you can safely ignore this email.</p></div>')
    return subject, text, html


def _mime(sender: str, name: str, to: str, code: str) -> EmailMessage:
    subject, text, html = _content(code)
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = formataddr((name, sender)), to, subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def send_email(to: str, code: str) -> None:
    provider = os.getenv("EMAIL_PROVIDER", "").lower()
    if provider == "brevo":
        return _send_brevo(to, code)
    if provider == "gmail_api":
        return _send_gmail_api(to, code)
    if provider == "gmail":
        return _send_gmail_smtp(to, code)
    raise RuntimeError("EMAIL_PROVIDER must be 'brevo', 'gmail_api' or 'gmail'")


def _send_brevo(to: str, code: str) -> None:
    api_key, sender = os.getenv("BREVO_API_KEY", ""), os.getenv("EMAIL_FROM", "")
    if not api_key or not sender:
        raise RuntimeError("BREVO_API_KEY or EMAIL_FROM is not set")
    name = os.getenv("EMAIL_FROM_NAME", "OpportunityHub")
    subject, text, html = _content(code)
    base = os.getenv("BREVO_API_BASE", "https://api.brevo.com")
    payload = {"sender": {"name": name, "email": sender}, "to": [{"email": to}], "subject": subject, "textContent": text, "htmlContent": html}
    req = urllib.request.Request(f"{base}/v3/smtp/email", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json", **UA, "api-key": api_key})
    with urllib.request.urlopen(req, timeout=15) as resp:     # HTTP errors (4xx/5xx) raise here
        if not 200 <= resp.status < 300:
            raise RuntimeError(f"Brevo answered HTTP {resp.status}")
        resp.read()


# ---- Gmail API (HTTPS) ----
_token = {"value": "", "exp": 0.0}


def _http_error_reason(e) -> str:
    """Short, secret-free description of a Google HTTP error (status + Google's own error word)."""
    try:
        body = json.loads(e.read().decode("utf-8", "ignore"))
        err = body.get("error")
        word = err.get("status") if isinstance(err, dict) else err
        return f"HTTP {e.code} {word or ''}".strip()
    except Exception:
        return f"HTTP {getattr(e, 'code', '?')}"


def _gmail_access_token() -> str:
    if _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    cid, secret, refresh = (os.getenv(k, "") for k in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"))
    if not (cid and secret and refresh):
        raise RuntimeError("GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET or GMAIL_REFRESH_TOKEN is not set")
    data = urllib.parse.urlencode({"client_id": cid, "client_secret": secret, "refresh_token": refresh, "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            tok = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gmail token refresh failed: {_http_error_reason(e)} (invalid_grant = refresh token expired or revoked)")
    _token["value"], _token["exp"] = tok["access_token"], time.time() + int(tok.get("expires_in", 3600))
    return _token["value"]


def _send_gmail_api(to: str, code: str) -> None:
    sender = os.getenv("EMAIL_FROM", "")
    if not sender:
        raise RuntimeError("EMAIL_FROM is not set")
    msg = _mime(sender, os.getenv("EMAIL_FROM_NAME", "OpportunityHub"), to, code)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    for attempt in (1, 2):                      # a second try only if the cached access token was refused
        req = urllib.request.Request("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                                     data=json.dumps({"raw": raw}).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **UA, "Authorization": f"Bearer {_gmail_access_token()}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            return
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 1:
                _token["value"], _token["exp"] = "", 0.0
                continue
            raise RuntimeError(f"Gmail API refused the mail: {_http_error_reason(e)}")


# ---- Gmail SMTP (App Password). Blocked on Render's free plan. ----
def _send_gmail_smtp(to: str, code: str) -> None:
    user = os.getenv("GMAIL_USER", "") or os.getenv("EMAIL_FROM", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not user or not password:
        raise RuntimeError("GMAIL_USER (or EMAIL_FROM) or GMAIL_APP_PASSWORD is not set")
    msg = _mime(user, os.getenv("EMAIL_FROM_NAME", "OpportunityHub"), to, code)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15, context=ssl.create_default_context()) as s:
            s.login(user, password)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError("Gmail SMTP login failed (use a 16-character App Password, not the normal password)")
    except (OSError, smtplib.SMTPException) as e:
        raise RuntimeError(f"Gmail SMTP failed: {type(e).__name__} (Render's free plan blocks SMTP ports; use EMAIL_PROVIDER=gmail_api)")


FREE_DOMAINS = {"gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "ymail.com", "outlook.com", "hotmail.com", "live.com",
                "icloud.com", "me.com", "rediffmail.com", "aol.com", "proton.me", "protonmail.com"}


def status() -> dict:
    """What is wrong with the email setup, in plain words (never includes secrets)."""
    provider = os.getenv("EMAIL_PROVIDER", "").lower()
    sender = os.getenv("EMAIL_FROM", "") or (os.getenv("GMAIL_USER", "") if provider == "gmail" else "")
    domain = sender.rsplit("@", 1)[-1].lower() if "@" in sender else ""
    problems = []
    if provider not in ("brevo", "gmail_api", "gmail"):
        problems.append("EMAIL_PROVIDER is not set to 'brevo', 'gmail_api' or 'gmail', so no verification email can be sent.")
    elif provider == "brevo":
        if not os.getenv("BREVO_API_KEY"):
            problems.append("BREVO_API_KEY is not set.")
        if not sender:
            problems.append("EMAIL_FROM is not set.")
        elif domain in FREE_DOMAINS:
            problems.append(f"EMAIL_FROM ({sender}) is a free address. Brevo cannot authenticate {domain}, so Gmail, Yahoo and Outlook will likely "
                            "reject these emails or put them in spam. Use an address on a domain you own and authenticate that domain in Brevo "
                            "(Brevo code, DKIM, DMARC), or switch to EMAIL_PROVIDER=gmail_api.")
    elif provider == "gmail_api":
        for k in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "EMAIL_FROM"):
            if not os.getenv(k):
                problems.append(f"{k} is not set.")
    else:
        if not sender:
            problems.append("GMAIL_USER (or EMAIL_FROM) is not set.")
        if not os.getenv("GMAIL_APP_PASSWORD"):
            problems.append("GMAIL_APP_PASSWORD is not set.")
        if os.getenv("RENDER"):
            problems.append("EMAIL_PROVIDER=gmail uses SMTP, which Render's free plan blocks. Use EMAIL_PROVIDER=gmail_api (HTTPS) instead.")
    return {"provider": provider, "sender": sender, "sender_domain": domain, "free_sender_domain": domain in FREE_DOMAINS and provider == "brevo",
            "ok": not problems, "problems": problems}
