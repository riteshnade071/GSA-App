from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = (ROOT / "app/src/main/java/com/sakura/assistant/Tools.kt").read_text(encoding="utf-8")
HANDOFF = (ROOT / "app/src/main/java/com/sakura/assistant/AiHandoff.kt").read_text(encoding="utf-8")
COMPARE = (ROOT / "app/src/main/java/com/sakura/assistant/PhotoCompareActivity.kt").read_text(encoding="utf-8")
MANIFEST = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")

checks = {
    "manual share chooser": "Intent.createChooser(chooser" in HANDOFF,
    "no accessibility auto-send": "findSend(" not in HANDOFF and "performAction" not in HANDOFF,
    "explicit user confirmation": "h.confirm(" in HANDOFF,
    "edited photo import tool": '"import_edited_photo"' in TOOLS,
    "Gallery Pictures/Sakura save path": '"Pictures/Sakura"' in TOOLS,
    "before-after comparison tool": '"compare_photos"' in TOOLS,
    "offline comparison activity": "PhotoCompareActivity" in COMPARE,
    "comparison activity registered": 'android:name=".PhotoCompareActivity"' in MANIFEST,
}
for label, passed in checks.items():
    print(("PASS" if passed else "FAIL") + " - " + label)
if not all(checks.values()):
    raise SystemExit(1)
print(f"All {len(checks)} photo workflow checks passed.")
