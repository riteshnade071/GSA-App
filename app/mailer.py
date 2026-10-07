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
    payload = {"sender": {"name": name, "email": sender}, "to": [{"email": to}], "subject": subject, "textContent": text}
    req = urllib.request.Request(f"{base}/v3/smtp/email", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json", **UA, "api-key": api_key})
    urllib.request.urlopen(req, timeout=15).read()
