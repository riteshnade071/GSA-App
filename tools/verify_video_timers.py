from pathlib import Path

root = Path(__file__).resolve().parents[1]
timer = (root / "app/src/main/java/com/sakura/assistant/AppVideoTimer.kt").read_text(encoding="utf-8")
service = (root / "app/src/main/java/com/sakura/assistant/AgentService.kt").read_text(encoding="utf-8")
manifest = (root / "app/src/main/res/xml/agent_config.xml").read_text(encoding="utf-8")

checks = {
    "mPokket timer is 125 seconds": "MPOKKET_MS = 125_000L" in timer,
    "short-video timer is 120 seconds": "SHORT_VIDEO_MS = 120_000L" in timer,
    "Instagram package is recognized": "com.instagram.android" in timer,
    "YouTube package is recognized": "com.google.android.youtube" in timer,
    "Facebook package is recognized": "com.facebook.katana" in timer,
    "Snapchat package is recognized": "com.snapchat.android" in timer,
    "foreground package selection does not start a timer": "onForegroundPackage" in timer and "startedAt = SystemClock" not in timer,
    "playback state starts and pauses timer": "fun onPlaybackState" in timer and "if (playing)" in timer and "isPlaying = false" in timer,
    "accessibility tree playback probe exists": "object VideoPlaybackProbe" in timer and "detectPlaybackState(rootInActiveWindow)" in service,
    "content-change events are handled": "TYPE_WINDOW_CONTENT_CHANGED" in service,
    "scroll and click events are enabled": "typeViewScrolled|typeViewClicked" in manifest,
    "timer completion notification is sent": "manager.notify(NOTIFICATION_ID, notification)" in timer,
    "timer does not dispatch gestures or auto-scroll": "dispatchGesture" not in timer and "autoScroll" not in timer,
}

for name, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL'}: {name}")
if not all(checks.values()):
    raise SystemExit(1)
print(f"\n{len(checks)} checks passed.")
