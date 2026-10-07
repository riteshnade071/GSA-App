"""
WhatsApp OTP. Choose with WHATSAPP_PROVIDER:

  console (default)  prints the code in the server log. Testing only.
  twilio             uses the same TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN plus TWILIO_WHATSAPP_FROM (e.g. whatsapp:+14155238886).
                     Twilio's WhatsApp sandbox works for testing, but each tester must first join the sandbox.
  meta               WhatsApp Cloud API. Needs WHATSAPP_TOKEN, WHATSAPP_PHONE_ID and WHATSAPP_TEMPLATE (an APPROVED
                     "authentication" template with one {{1}} variable and a copy-code button). Optional: WHATSAPP_LANG (en),
                     WHATSAPP_API_VERSION (v21.0).
"""
import base64, json, os, urllib.parse, urllib.request
from app.sms import OTP_MINUTES

UA = {"User-Agent": "OpportunityHub/1.0"}


def send_whatsapp(phone: str, code: str) -> None:
    provider = os.getenv("WHATSAPP_PROVIDER", "console").lower()
    text = f"{code} is your OpportunityHub verification code. It is valid for {OTP_MINUTES} minutes. Do not share it with anyone."

    if provider == "console":
        print(f"[WhatsApp console] +91{phone}: {text}", flush=True)

    elif provider == "twilio":
        sid, token, sender = os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"], os.environ["TWILIO_WHATSAPP_FROM"]
        base = os.getenv("TWILIO_API_BASE", "https://api.twilio.com")
        body = urllib.parse.urlencode({"To": "whatsapp:+91" + phone, "From": sender, "Body": text}).encode()
        auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
        req = urllib.request.Request(f"{base}/2010-04-01/Accounts/{sid}/Messages.json", data=body, method="POST",
                                     headers={"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded", **UA})
        urllib.request.urlopen(req, timeout=15).read()

    elif provider == "meta":
        token, phone_id, template = os.environ["WHATSAPP_TOKEN"], os.environ["WHATSAPP_PHONE_ID"], os.environ["WHATSAPP_TEMPLATE"]
        base = os.getenv("WHATSAPP_API_BASE", "https://graph.facebook.com")
        version = os.getenv("WHATSAPP_API_VERSION", "v21.0")
        payload = {"messaging_product": "whatsapp", "to": "91" + phone, "type": "template",
                   "template": {"name": template, "language": {"code": os.getenv("WHATSAPP_LANG", "en")},
                                "components": [{"type": "body", "parameters": [{"type": "text", "text": code}]},
                                               {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": code}]}]}}
        req = urllib.request.Request(f"{base}/{version}/{phone_id}/messages", data=json.dumps(payload).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", **UA})
        urllib.request.urlopen(req, timeout=15).read()

    else:
        raise RuntimeError(f"Unknown WHATSAPP_PROVIDER '{provider}'")
