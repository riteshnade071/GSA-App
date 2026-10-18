import io, unittest
from contextlib import redirect_stdout
from unittest import mock


class DbCase(unittest.TestCase):
    """Fresh database + a FAKE mailer that records (email, code). The fake exists only here, never in app/."""
    fail_delivery = False

    def setUp(self):
        from app import ratelimit
        from app.database import Base, engine, SessionLocal
        from app.models import core  # noqa: F401
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        ratelimit._hits.clear()
        self.db = SessionLocal()
        self.sent = []
        self.out = io.StringIO()

        def fake_send(to, code):
            self.sent.append((to, code))
            if self.fail_delivery:
                raise RuntimeError("simulated Brevo outage")
        self._patch = mock.patch("app.otp.mailer.send_email", side_effect=fake_send)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self.db.close()

    def age(self, email, purpose, seconds):
        """Pretend the newest code of this email+purpose was created `seconds` ago (moves created_at and expires_at back)."""
        from datetime import timedelta
        from app.models.core import OtpCode
        for r in self.db.query(OtpCode).filter(OtpCode.phone == email, OtpCode.purpose == purpose).all():
            r.created_at = r.created_at - timedelta(seconds=seconds)
            r.expires_at = r.expires_at - timedelta(seconds=seconds)
        self.db.commit()
