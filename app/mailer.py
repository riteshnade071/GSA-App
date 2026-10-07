"""
Email OTP. Choose with EMAIL_PROVIDER:

  console (default)  prints the code in the server log. Testing only.
  brevo              HTTPS API. BREVO_API_KEY + EMAIL_FROM (a sender address you verified in Brevo).
  resend             HTTPS API. RESEND_API_KEY + EMAIL_FROM (needs a verified domain; Resend's test sender only reaches your own address).
  smtp               SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, EMAIL_FROM. NOTE: Render's FREE plan blocks SMTP ports
                     25/465/587, so on Render free use brevo or resend.
Optional for all: EMAIL_FROM_NAME (default OpportunityHub).
"""
import json, os, smtplib, urllib.request
from email.message import EmailMessage
from app.sms import OTP_MINUTES

UA = {"User-Agent": "OpportunityHub/1.0"}


def send_email(to: str, code: str) -> None:
    provider = os.getenv("EMAIL_PROVIDER", "console").lower()
    name, sender = os.getenv("EMAIL_FROM_NAME", "OpportunityHub"), os.getenv("EMAIL_FROM", "")
    subject = "Your OpportunityHub verification code"
    text = (f"Your OpportunityHub verification code is {code}.\n\nIt is valid for {OTP_MINUTES} minutes. Do not share it with anyone.\n"
            "If you did not ask for this code, you can ignore this email.")

    def post(url, payload, headers):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Accept": "application/json", **UA, **headers})
        urllib.request.urlopen(req, timeout=15).read()

    if provider == "console":
        print(f"[Email console] to {to}: {subject} | {text}", flush=True)

    elif provider == "brevo":
        base = os.getenv("BREVO_API_BASE", "https://api.brevo.com")
        post(f"{base}/v3/smtp/email", {"sender": {"name": name, "email": sender}, "to": [{"email": to}], "subject": subject, "textContent": text},
             {"api-key": os.environ["BREVO_API_KEY"]})

    elif provider == "resend":
        base = os.getenv("RESEND_API_BASE", "https://api.resend.com")
        post(f"{base}/emails", {"from": f"{name} <{sender}>", "to": [to], "subject": subject, "text": text},
             {"Authorization": "Bearer " + os.environ["RESEND_API_KEY"]})

    elif provider == "smtp":
        msg = EmailMessage(); msg["From"], msg["To"], msg["Subject"] = f"{name} <{sender}>", to, subject; msg.set_content(text)
        host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
        with (smtplib.SMTP_SSL(host, port, timeout=15) if port == 465 else smtplib.SMTP(host, port, timeout=15)) as smtp:
            if port != 465 and os.getenv("SMTP_STARTTLS", "true").lower() != "false":
                smtp.starttls()
            if os.getenv("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(msg)

    else:
        raise RuntimeError(f"Unknown EMAIL_PROVIDER '{provider}'")
