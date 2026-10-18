import contextlib, io, threading, unittest
from datetime import timedelta
from fastapi import HTTPException
from app import otp
from app.models.core import OtpCode
from tests.helpers import DbCase

EMAIL = "student@example.com"


class OtpEngine(DbCase):
    def issue(self, purpose="signup", email=EMAIL):
        otp.issue(self.db, email, purpose)
        return self.sent[-1][1]

    def test_code_is_six_digits_and_verifies_once(self):
        code = self.issue()
        self.assertRegex(code, r"^[0-9]{6}$")
        self.assertTrue(otp.check(self.db, EMAIL, "signup", code))
        self.assertFalse(otp.check(self.db, EMAIL, "signup", code))          # replay

    def test_only_a_hash_is_stored_and_timestamps_are_aware(self):
        code = self.issue()
        row = self.db.query(OtpCode).one()
        self.assertNotIn(code, [str(v) for v in (row.id, row.phone, row.purpose, row.code_hash, row.attempts)])
        self.assertEqual(len(row.code_hash), 64)
        self.assertIsNotNone(row.created_at.tzinfo)
        self.assertIsNotNone(row.expires_at.tzinfo)
        self.assertEqual(row.expires_at - row.created_at, timedelta(minutes=5))

    def test_wrong_code_fails_and_counts_an_attempt(self):
        code = self.issue()
        wrong = "000000" if code != "000000" else "111111"
        self.assertFalse(otp.check(self.db, EMAIL, "signup", wrong))
        self.assertEqual(self.db.query(OtpCode).one().attempts, 1)
        self.assertTrue(otp.check(self.db, EMAIL, "signup", code))

    def test_malformed_code_does_not_spend_an_attempt(self):
        self.issue()
        for bad in ("", "12345", "1234567", "abcdef", " "):
            self.assertFalse(otp.check(self.db, EMAIL, "signup", bad))
        self.assertEqual(self.db.query(OtpCode).one().attempts, 0)

    def test_expired_code_is_rejected(self):
        code = self.issue()
        self.age(EMAIL, "signup", 5 * 60 + 5)
        self.assertFalse(otp.check(self.db, EMAIL, "signup", code))

    def test_five_wrong_tries_lock_the_code_even_for_the_right_answer(self):
        code = self.issue()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertFalse(otp.check(self.db, EMAIL, "signup", wrong))
        self.assertFalse(otp.check(self.db, EMAIL, "signup", code))
        self.assertEqual(self.db.query(OtpCode).one().attempts, 5)

    def test_resend_cooldown_is_60_seconds(self):
        self.issue()
        with self.assertRaises(HTTPException) as cm:
            otp.issue(self.db, EMAIL, "signup")
        self.assertEqual(cm.exception.status_code, 429)
        self.assertEqual(len(self.sent), 1)                                   # nothing was emailed the second time
        self.age(EMAIL, "signup", 61)
        otp.issue(self.db, EMAIL, "signup")
        self.assertEqual(len(self.sent), 2)

    def test_new_code_cancels_the_previous_one(self):
        first = self.issue()
        self.age(EMAIL, "signup", 61)
        second = self.issue()
        if first == second:
            self.skipTest("the two random codes happened to be equal (1 in a million)")
        self.assertFalse(otp.check(self.db, EMAIL, "signup", first))
        self.assertTrue(otp.check(self.db, EMAIL, "signup", second))

    def test_hourly_limit_per_email(self):
        for _ in range(otp.MAX_PER_HOUR):
            self.issue()
            self.age(EMAIL, "signup", 61)
        with self.assertRaises(HTTPException) as cm:
            otp.issue(self.db, EMAIL, "signup")
        self.assertEqual(cm.exception.status_code, 429)

    def test_purposes_are_isolated(self):
        code_s, code_r = self.issue("signup"), self.issue("reset")
        if code_s == code_r:
            self.skipTest("the two random codes happened to be equal (1 in a million)")
        self.assertFalse(otp.check(self.db, EMAIL, "reset", code_s))          # a signup code cannot be used for a password reset
        self.assertFalse(otp.check(self.db, EMAIL, "signup", code_r))         # and the other way round
        self.assertFalse(otp.check(self.db, EMAIL, "add_email", code_s))
        self.assertTrue(otp.check(self.db, EMAIL, "signup", code_s))
        self.assertTrue(otp.check(self.db, EMAIL, "reset", code_r))

    def test_code_for_one_email_does_not_work_for_another(self):
        code = self.issue()
        self.assertFalse(otp.check(self.db, "other@example.com", "signup", code))

    def test_delivery_failure_cancels_the_new_code_and_never_leaks_it(self):
        DbCase.fail_delivery = True
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), self.assertRaises(HTTPException) as cm:
                otp.issue(self.db, EMAIL, "signup")
        finally:
            DbCase.fail_delivery = False
        self.assertEqual(cm.exception.status_code, 502)
        code = self.sent[-1][1]
        self.assertFalse(otp.check(self.db, EMAIL, "signup", code))           # the undelivered code is dead
        self.assertNotIn(code, buf.getvalue())                                # and it was not logged
        self.assertNotIn(code, str(cm.exception.detail))

    def test_delivery_failure_also_leaves_no_older_code_alive(self):
        old = self.issue()
        self.age(EMAIL, "signup", 61)
        DbCase.fail_delivery = True
        try:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(HTTPException):
                otp.issue(self.db, EMAIL, "signup")
        finally:
            DbCase.fail_delivery = False
        self.assertFalse(otp.check(self.db, EMAIL, "signup", old))

    def test_parallel_correct_requests_consume_the_code_exactly_once(self):
        from app.database import SessionLocal
        code = self.issue()
        results, barrier = [], threading.Barrier(8)

        def worker():
            s = SessionLocal()
            try:
                barrier.wait()
                results.append(otp.check(s, EMAIL, "signup", code))
            except Exception:
                results.append(False)       # e.g. SQLite "database is locked": counts as not consumed
            finally:
                s.close()
        threads = [threading.Thread(target=worker) for _ in range(8)]
        [t.start() for t in threads]; [t.join() for t in threads]
        self.assertEqual(results.count(True), 1)

    def test_parallel_wrong_guesses_cannot_exceed_five_tries(self):
        from app.database import SessionLocal
        code = self.issue()
        wrong = "000000" if code != "000000" else "111111"
        barrier = threading.Barrier(12)

        def worker():
            s = SessionLocal()
            try:
                barrier.wait(); otp.check(s, EMAIL, "signup", wrong)
            except Exception:
                pass
            finally:
                s.close()
        threads = [threading.Thread(target=worker) for _ in range(12)]
        [t.start() for t in threads]; [t.join() for t in threads]
        self.db.expire_all()
        self.assertLessEqual(self.db.query(OtpCode).one().attempts, otp.MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
