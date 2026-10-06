"""
SMS sending. Choose the provider with the SMS_PROVIDER environment variable:

  console  (default)  prints the code in the server log. For testing only: students never receive it.
  twilio              needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM
  msg91               needs MSG91_AUTHKEY, MSG91_TEMPLATE_ID (a DLT-approved OTP template using the OTP variable)

Sending SMS to Indian numbers needs a registered sender/template (DLT) with every provider.
Adding another provider = one more `elif` below.
"""
import base64, json, os, urllib.parse, urllib.request

OTP_MINUTES = 10


def send_sms(phone: str, code: str) -> None:
    provider = os.getenv("SMS_PROVIDER", "console").lower()
    text = f"{code} is your OpportunityHub verification code. It is valid for {OTP_MINUTES} minutes. Do not share it with anyone."

    if provider == "console":
        print(f"[SMS console] +91{phone}: {text}", flush=True)

    elif provider == "twilio":
        sid, token, sender = os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"], os.environ["TWILIO_FROM"]
        base = os.getenv("TWILIO_API_BASE", "https://api.twilio.com")
        body = urllib.parse.urlencode({"To": "+91" + phone, "From": sender, "Body": text}).encode()
        auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
        req = urllib.request.Request(f"{base}/2010-04-01/Accounts/{sid}/Messages.json", data=body, method="POST",
                                     headers={"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"})
        urllib.request.urlopen(req, timeout=15).read()

    elif provider == "msg91":
        key, template = os.environ["MSG91_AUTHKEY"], os.environ["MSG91_TEMPLATE_ID"]
        base = os.getenv("MSG91_API_BASE", "https://control.msg91.com")
        query = urllib.parse.urlencode({"template_id": template, "mobile": "91" + phone, "authkey": key, "otp": code})
        req = urllib.request.Request(f"{base}/api/v5/otp?{query}", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json", "authkey": key})
        reply = json.loads(urllib.request.urlopen(req, timeout=15).read() or b"{}")
        if reply.get("type") == "error":
            raise RuntimeError(reply.get("message", "MSG91 error"))

    else:
        raise RuntimeError(f"Unknown SMS_PROVIDER '{provider}'")
