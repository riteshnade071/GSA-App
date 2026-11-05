# Sakura feature updates

## Instagram Reels
The backend agent instructions now require a real navigation sequence: launch Instagram, inspect its accessibility tree, open the Reels tab, verify the viewer, then start auto-scroll. If the Reels tab cannot be identified, Sakura must report that instead of claiming success. Android swipes are performed through the existing AccessibilityService. Instagram UI labels/layout can change, so the exact tab detection still needs testing on the target phone.

## WhatsApp notifications
Only WhatsApp / WhatsApp Business notifications are accepted (existing package filter). Notification text is cleaned of emoji code points and formatting joiners before it is stored or spoken. Messages remain local to the phone and are not sent to the cloud chat endpoint.

## Avatar overlay
The mini overlay remains 4 cm tall and is widened from 1.8 cm to 2.4 cm for better full-body visibility. Existing drag handling lets the user move the overlay around the screen. The new VRM should be framed using the existing full-body camera fit.

## Deep chart analysis
The chart prompt now requests structured analysis: market structure, levels, candle context, visible indicators, bullish/bearish/neutral scenarios, invalidation, confidence, and missing information. It explicitly forbids inventing unreadable values or pretending to have multi-timeframe data from a single screenshot. The spoken summary is kept short while the on-screen text is detailed.

## Important testing
This source update is not a claim that an APK has been built or tested on a Vivo device. Rebuild the Android app with GitHub Actions and test Instagram navigation, WhatsApp notification speech, overlay dragging, and chart screenshots on-device.

## 2026-11 project refresh
- Improved auto-scroll reporting: accessibility-tree changes are checked after swipes; repeated unconfirmed swipes no longer return an unconditional success claim.
- Android APK still needs a GitHub Actions build and Vivo device validation before release.

## TradingView candle-area zoom during historical exploration
- `explore_chart` now sends a modest two-finger pinch-out centered in the candle plot before taking the current and older-history screenshots.
- It pans the chart horizontally while keeping the temporary zoom, then reverses the historical pans and sends the inverse pinch gesture to restore the prior zoom.
- The result reports whether the zoom-in and zoom-restore gestures were accepted. Android Accessibility can confirm gesture dispatch, but cannot guarantee TradingView applied the exact visual scale; verify on the Vivo V27.
- The zoom is deliberately temporary and does not alter chart indicators or trade controls. If TradingView's plot geometry differs, the center point may need device-specific adjustment.


## App-specific foreground timers (2026-11-03)

- mPokket app foreground: 125-second timer.
- Instagram, YouTube, Facebook, Snapchat, TikTok, and recognized Moj/Josh/ShareChat apps: 120-second timer.
- Completion is shown as an Android notification.
- This is an app-foreground timer, not proof that a video is playing or has ended. It does not auto-scroll or interact with rewards. See `SAKURA_VIDEO_TIMERS.md`.


## Playback-triggered video timers (v8)

- Opening mPokket/Instagram/YouTube/Facebook etc. no longer starts a timer.
- Sakura waits for an accessibility player signal (Pause/Play labels) and then
  counts accumulated detected playback time: mPokket 125 seconds; supported
  short-video apps 120 seconds.
- A detected Pause control pauses the timer; a detected Play/Resume control
  resumes it.
- No auto-scroll, auto-replay, ad interaction, or reward interaction is added.
- Detection is best-effort because apps may hide player controls from Android
  Accessibility; real-device validation is required.


## Photo edit / PDF via AI apps (2026-11-04)
See `SAKURA_AI_HANDOFF.md`. New tools `pick_photo`, `ai_create`; `find_photos` now returns album names and accepts `album`. Not compiled or device-tested yet.

## Photo Studio v1 (free manual handoff)
- Replaced accessibility-based Send-button guessing with an explicit Android share chooser; Sakura never auto-sends prompts.
- Added `import_edited_photo`: user selects the finished image and Sakura copies it to Gallery `Pictures/Sakura`.
- Added `compare_photos`: select original then edited image for an offline before/after viewer.
- Added prompt guidance for background removal, object removal, identity-preserving retouching and HD enhancement.
- Free provider quotas and image export remain provider-controlled; Sakura reports handoff separately from completed edits.
- See `SAKURA_PHOTO_STUDIO.md`.
