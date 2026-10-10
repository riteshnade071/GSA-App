"""
Email OTP delivery through Brevo (HTTPS API). The ONLY way codes are sent.

Environment variables (Render -> Environment):
  EMAIL_PROVIDER    must be `brevo`
  BREVO_API_KEY     your Brevo API key (keep it secret, never put it in code)
  EMAIL_FROM        a sender address you verified in Brevo
  EMAIL_FROM_NAME   optional, default OpportunityHub

If anything is missing or Brevo refuses the mail, an error is raised and NO code is accepted or shown: there is no test mode.
"""
import json, os, urllib.request

OTP_MINUTES = 10
UA = {"User-Agent": "OpportunityHub/1.0"}


def send_email(to: str, code: str) -> None:
    if os.getenv("EMAIL_PROVIDER", "").lower() != "brevo":
        raise RuntimeError("EMAIL_PROVIDER is not set to 'brevo'")
    api_key, sender = os.getenv("BREVO_API_KEY", ""), os.getenv("EMAIL_FROM", "")
    if not api_key or not sender:
        raise RuntimeError("BREVO_API_KEY or EMAIL_FROM is not set")
    name = os.getenv("EMAIL_FROM_NAME", "OpportunityHub")
    subject = "OpportunityHub Email Verification"
    text = (f"Your OpportunityHub verification code is:\n\n{code}\n\nThis code expires in {OTP_MINUTES} minutes.\n\n"
            "If you did not request this verification code, please ignore this email.")
    base = os.getenv("BREVO_API_BASE", "https://api.brevo.com")
    html = ('<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:16px">'
            '<h2 style="color:#6B21A8;margin:0 0 12px">OpportunityHub</h2><p>Your verification code is:</p>'
            f'<p style="font-size:32px;letter-spacing:6px;font-weight:bold;margin:8px 0">{code}</p>'
            f'<p>This code expires in {OTP_MINUTES} minutes.</p>'
            '<p style="color:#666;font-size:12px">If you did not request this verification code, please ignore this email.</p></div>')
    payload = {"sender": {"name": name, "email": sender}, "to": [{"email": to}], "subject": subject, "textContent": text, "htmlContent": html}
    req = urllib.request.Request(f"{base}/v3/smtp/email", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json", **UA, "api-key": api_key})
    urllib.request.urlopen(req, timeout=15).read()


FREE_DOMAINS = {"gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "ymail.com", "outlook.com", "hotmail.com", "live.com",
                "icloud.com", "me.com", "rediffmail.com", "aol.com", "proton.me", "protonmail.com"}


def status() -> dict:
    """What is wrong with the email setup, in plain words (never includes the API key)."""
    sender = os.getenv("EMAIL_FROM", "")
    domain = sender.rsplit("@", 1)[-1].lower() if "@" in sender else ""
    problems = []
    if os.getenv("EMAIL_PROVIDER", "").lower() != "brevo":
        problems.append("EMAIL_PROVIDER is not set to 'brevo', so no verification email can be sent.")
    if not os.getenv("BREVO_API_KEY"):
        problems.append("BREVO_API_KEY is not set.")
    if not sender:
        problems.append("EMAIL_FROM is not set.")
    elif domain in FREE_DOMAINS:
        problems.append(f"EMAIL_FROM ({sender}) is a free address. Brevo cannot authenticate {domain}, so Gmail, Yahoo and Outlook will likely "
                        "reject these emails or put them in spam. Use an address on a domain you own and authenticate that domain in Brevo (Brevo code, DKIM, DMARC).")
    return {"provider": os.getenv("EMAIL_PROVIDER", ""), "sender": sender, "sender_domain": domain, "free_sender_domain": domain in FREE_DOMAINS,
            "ok": not problems, "problems": problems}
