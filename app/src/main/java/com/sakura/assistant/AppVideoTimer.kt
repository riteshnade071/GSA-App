package com.sakura.assistant

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.SystemClock
import android.view.accessibility.AccessibilityNodeInfo
import java.util.ArrayDeque

/**
 * Playback-triggered timer. Merely opening an app does NOT start the timer.
 * Accessibility text/content descriptions are used as a best-effort signal
 * that a player exposes a Pause control (playing) or Play control (paused).
 * No taps, swipes, auto-scroll, replay, or reward actions are performed.
 */
class AppVideoTimer(
    private val context: Context,
    private val main: Handler
) {
    companion object {
        private const val CHANNEL_ID = "sakura_app_video_timer"
        private const val NOTIFICATION_ID = 5201
        private const val MPOKKET_MS = 125_000L
        private const val SHORT_VIDEO_MS = 120_000L
    }

    private data class Target(val label: String, val durationMs: Long)

    private var activePackage: String? = null
    private var activeTarget: Target? = null
    private var accumulatedMs = 0L
    private var playingSince = 0L
    private var isPlaying = false
    private var notified = false

    private val finishRunnable = Runnable { checkFinish() }

    fun isSupportedPackage(packageName: String?): Boolean =
        matchTarget(packageName?.lowercase()?.trim().orEmpty()) != null

    /** Call when Android reports a foreground package change. Does not start a timer. */
    fun onForegroundPackage(packageName: String?) {
        val pkg = packageName?.lowercase()?.trim().orEmpty()
        if (pkg == activePackage) return
        stop()
        val target = matchTarget(pkg) ?: return
        activePackage = pkg
        activeTarget = target
    }

    /**
     * Feed a best-effort playback state from the current accessibility tree.
     * null means the app exposes no reliable signal; in that case we do nothing.
     */
    fun onPlaybackState(packageName: String?, playing: Boolean?) {
        val pkg = packageName?.lowercase()?.trim().orEmpty()
        if (pkg != activePackage || activeTarget == null || notified || playing == null) return
        if (playing == isPlaying) return

        if (playing) {
            isPlaying = true
            playingSince = SystemClock.elapsedRealtime()
            scheduleRemaining()
        } else {
            if (isPlaying) {
                accumulatedMs += (SystemClock.elapsedRealtime() - playingSince).coerceAtLeast(0L)
            }
            isPlaying = false
            playingSince = 0L
            main.removeCallbacks(finishRunnable)
        }
    }

    fun stop() {
        main.removeCallbacks(finishRunnable)
        activePackage = null
        activeTarget = null
        accumulatedMs = 0L
        playingSince = 0L
        isPlaying = false
        notified = false
    }

    private fun elapsedPlayingMs(): Long =
        accumulatedMs + if (isPlaying) (SystemClock.elapsedRealtime() - playingSince).coerceAtLeast(0L) else 0L

    private fun scheduleRemaining() {
        val target = activeTarget ?: return
        val remaining = target.durationMs - elapsedPlayingMs()
        if (remaining <= 0L) {
            checkFinish()
        } else {
            main.removeCallbacks(finishRunnable)
            main.postDelayed(finishRunnable, remaining)
        }
    }

    private fun checkFinish() {
        val target = activeTarget ?: return
        if (!isPlaying || notified) return
        val remaining = target.durationMs - elapsedPlayingMs()
        if (remaining > 0L) {
            main.postDelayed(finishRunnable, remaining)
            return
        }
        notified = true
        showFinished(target)
    }

    private fun matchTarget(pkg: String): Target? {
        if (pkg.isBlank()) return null
        val appLabel = try {
            context.packageManager.getApplicationInfo(pkg, 0)
                .loadLabel(context.packageManager).toString().lowercase()
        } catch (_: Exception) {
            ""
        }
        if (pkg.contains("mpokket") || appLabel.contains("mpokket")) {
            return Target("mPokket Earn", MPOKKET_MS)
        }
        return when {
            pkg == "com.instagram.android" || appLabel == "instagram" -> Target("Instagram", SHORT_VIDEO_MS)
            pkg == "com.google.android.youtube" || appLabel == "youtube" -> Target("YouTube", SHORT_VIDEO_MS)
            pkg == "com.facebook.katana" || appLabel == "facebook" -> Target("Facebook", SHORT_VIDEO_MS)
            pkg == "com.snapchat.android" || appLabel == "snapchat" -> Target("Snapchat", SHORT_VIDEO_MS)
            pkg.contains("musically") || appLabel.contains("tiktok") -> Target("TikTok", SHORT_VIDEO_MS)
            pkg.contains("sharechat") || pkg.contains("moj") || pkg.contains("josh") ||
                appLabel.contains("sharechat") || appLabel == "moj" || appLabel.contains("josh") ->
                Target("Short-video app", SHORT_VIDEO_MS)
            else -> null
        }
    }

    private fun showFinished(target: Target) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Sakura video timers", NotificationManager.IMPORTANCE_DEFAULT).apply {
                    description = "Timer starts only after playback is detected"
                }
            )
        }
        val seconds = target.durationMs / 1000L
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(context, CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(context)
        }
        val notification = builder
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle("${target.label}: playback timer complete")
            .setContentText("$seconds seconds ka detected playback time poora hua.")
            .setAutoCancel(true)
            .setCategory(Notification.CATEGORY_STATUS)
            .build()
        try {
            manager.notify(NOTIFICATION_ID, notification)
        } catch (_: SecurityException) {
            // Android 13+ notification permission deny ho to app crash nahi karna.
        }
    }

}

/** Best-effort player-state detection from Android accessibility semantics. */
object VideoPlaybackProbe {
    /**
     * Heuristic only: media players commonly expose a Pause action while
     * playing and a Play/Resume action while paused. Some apps hide these
     * nodes, so null is a valid (undetectable) result.
     */
    fun detectPlaybackState(root: AccessibilityNodeInfo?): Boolean? {
            if (root == null) return null
            var sawPause = false
            var sawPlay = false
            val stack = ArrayDeque<AccessibilityNodeInfo>()
            stack.add(root)
            var visited = 0
            while (stack.isNotEmpty() && visited < 350) {
                val node = stack.removeLast()
                visited++
                val label = buildString {
                    append(node.contentDescription?.toString().orEmpty())
                    append(' ')
                    append(node.text?.toString().orEmpty())
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                        append(' ')
                        append(node.stateDescription?.toString().orEmpty())
                    }
                }.lowercase().trim()
                if (label.isNotEmpty()) {
                    if (label == "pause" || label.contains("pause video") || label.contains("pause playback") ||
                        label.contains("video pause") || label.contains("वीडियो रोकें") || label.contains("रोकें")) {
                        sawPause = true
                    }
                    if (label == "play" || label == "resume" || label.contains("play video") ||
                        label.contains("resume playback") || label.contains("वीडियो चलाएं")) {
                        sawPlay = true
                    }
                }
                for (i in 0 until node.childCount) {
                    node.getChild(i)?.let { stack.add(it) }
                }
            }
            return when {
                sawPause && !sawPlay -> true
                sawPlay && !sawPause -> false
                else -> null
            }
        }
    }
