# Sakura playback-triggered timers

The timer no longer starts merely because a supported app is opened. It starts
only after Sakura's Android Accessibility service can identify a likely active
player from its accessibility tree (typically a `Pause` / `Pause video` control).
A `Play` / `Resume` control pauses the accumulated playback timer.

| App | Accumulated detected playback time |
| --- | ---: |
| mPokket | 125 seconds |
| Instagram, YouTube, Facebook, Snapchat, TikTok | 120 seconds |
| Recognized ShareChat, Moj, Josh | 120 seconds |

When the accumulated detected playback time is reached, Sakura posts a local
notification. Opening an app, browsing its home screen, or sitting in the Earn
tab without a detected player control does not start the timer.

## Detection limitations

- This is best-effort accessibility detection, not direct access to the media
  player's internal playback state. Apps differ in what they expose.
- If an app hides its accessibility `Pause` / `Play` labels, Sakura may not be
  able to detect playback in that app. Some apps may expose ambiguous controls.
- A playback control can disappear when the player UI hides it; Sakura retains
  the last known state until another accessibility event reports a change.
- This update does not tap play, scroll, replay, click ads/reward controls, or
  automate views. It only times playback the user has started.
- Android Accessibility must be enabled for Sakura. Android 13+ notification
  permission must be allowed to see the completion alert.
