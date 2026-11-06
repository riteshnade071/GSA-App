from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
main = (ROOT / "app/src/main/java/com/sakura/assistant/MainActivity.kt").read_text(encoding="utf-8")
workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
checks = {
    "release cleartext policy is parameterized": '${usesCleartextTraffic}' in manifest,
    "release disables cleartext": 'manifestPlaceholders["usesCleartextTraffic"] = "false"' in gradle,
    "debug allows local cleartext": 'manifestPlaceholders["usesCleartextTraffic"] = "true"' in gradle,
    "release signing uses private Gradle properties": "SAKURA_RELEASE_STORE_PASSWORD" in gradle,
    "default server URL uses HTTPS": 'u = "https://$u"' in main,
    "CI has signed AAB workflow": "bundleRelease" in workflow and "SAKURA_RELEASE_KEYSTORE_BASE64" in workflow,
    "keystore ignored": "*.keystore" in ignore and "*.jks" in ignore,
    "debug keystore is not committed": not (ROOT / "app/sakura-debug.keystore").exists(),
}
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + " - " + name)
if not all(checks.values()):
    raise SystemExit(1)
print(f"{sum(checks.values())}/{len(checks)} commercial baseline checks passed")
