from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parent / "Umiko-main"
checks = {
    "Android Credential Manager dependencies": "androidx.credentials:credentials:1.3.0" in (ROOT / "app/build.gradle.kts").read_text(),
    "Android Google sign-in bridge": "fun googleSignIn()" in (ROOT / "app/src/main/java/com/sakura/assistant/Bridge.kt").read_text(),
    "Android token returned to web account flow": "SakuraAuth.verifyCredential" in (ROOT / "app/src/main/java/com/sakura/assistant/MainActivity.kt").read_text(),
    "Google web client ID placeholder": "google_web_client_id" in (ROOT / "app/src/main/res/values/strings.xml").read_text(),
    "Backend Google ID token verification": "verify_oauth2_token" in (MAIN / "main.py").read_text(),
    "Verified Google email required": 'info.get("email_verified")' in (MAIN / "main.py").read_text(),
    "Local account-namespaced memory": "sakura_local_" in (MAIN / "index.html").read_text(),
    "Market journal account partitioning": "owner_id TEXT NOT NULL" in (MAIN / "market_engine.py").read_text(),
    "Setup documentation exists": (MAIN / "GOOGLE_SIGN_IN_SETUP.md").exists(),
}
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + " - " + name)
if not all(checks.values()):
    raise SystemExit(1)
print(f"{len(checks)}/{len(checks)} Google account checks passed")
