package com.sakura.assistant

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Base64
import android.view.Display
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.animation.DecelerateInterpolator
import android.view.animation.LinearInterpolator
import java.io.ByteArrayOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.math.PI
import kotlin.math.sin

/**
 * Screen control: dusri app ki screen padhna, tap, scroll, type.
 * Saath me do "haath" screen par dikhte hain (HandsView) jo wahi karte hain jo ho raha hai.
 * Master ko Settings -> Accessibility me ek baar ON karna padta hai.
 */
class AgentService : AccessibilityService() {

    companion object {
        @Volatile
        var instance: AgentService? = null
    }

    private val main = Handler(Looper.getMainLooper())
    private var hands: HandsView? = null
    private var appVideoTimer: AppVideoTimer? = null
    private val removeHands = Runnable { dropHands() }

    val sw: Int get() = resources.displayMetrics.widthPixels
    val sh: Int get() = resources.displayMetrics.heightPixels

    override fun onServiceConnected() {
        instance = this
        appVideoTimer = AppVideoTimer(this, main)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event ?: return
        val pkg = event.packageName?.toString()
            ?: rootInActiveWindow?.packageName?.toString()
            ?: return

        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            // App open hone se timer start nahi hota; sirf target app select hoti hai.
            appVideoTimer?.onForegroundPackage(pkg)
        }

        val timer = appVideoTimer ?: return
        if (!timer.isSupportedPackage(pkg)) return
        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED ||
            event.eventType == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED ||
            event.eventType == AccessibilityEvent.TYPE_VIEW_SCROLLED ||
            event.eventType == AccessibilityEvent.TYPE_VIEW_CLICKED) {
            val state = VideoPlaybackProbe.detectPlaybackState(rootInActiveWindow)
            timer.onPlaybackState(pkg, state)
        }
    }

    override fun onInterrupt() {}

    override fun onUnbind(intent: Intent?): Boolean {
        instance = null
        appVideoTimer?.stop()
        appVideoTimer = null
        main.post { dropHands() }
        return super.onUnbind(intent)
    }

    // ---------- haath ----------
    private fun wm() = getSystemService(Context.WINDOW_SERVICE) as WindowManager

    private fun ensureHands(): HandsView {
        main.removeCallbacks(removeHands)
        hands?.let { return it }
        val v = HandsView(this, sw, sh)
        val p = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        )
        wm().addView(v, p)
        hands = v
        return v
    }

    private fun dropHands() {
        main.removeCallbacks(removeHands)
        hands?.let {
            try { wm().removeView(it) } catch (e: Exception) { /* pehle hi hat chuka */ }
        }
        hands = null
    }

    /** ease=true: tezi se pahunch kar dheere ruke (jaane ke liye). false: seedhi lakeer (swipe ke liye). */
    fun handMove(right: Boolean, x: Float, y: Float, ms: Long) {
        main.post { ensureHands().moveTo(right, x, y, ms, true) }
    }

    fun handDrag(right: Boolean, x: Float, y: Float, ms: Long) {
        main.post { ensureHands().moveTo(right, x, y, ms, false) }
    }

    fun handRipple(x: Float, y: Float) {
        main.post { ensureHands().ripple(x, y) }
    }

    fun handWobble(ms: Long) {
        main.post { ensureHands().wobble(ms) }
    }

    /** Screenshot lete waqt haath tasveer me na aayein */
    fun setHandsVisible(v: Boolean) {
        main.post { hands?.visibility = if (v) View.VISIBLE else View.INVISIBLE }
    }

    /** Poori screen ki tasveer (JPEG, base64). Android 11+ chahiye. Worker thread se bulao. */
    fun screenshotJpegB64(maxW: Int): String? {
        if (Build.VERSION.SDK_INT < 30) return null
        val latch = CountDownLatch(1)
        var out: String? = null
        takeScreenshot(Display.DEFAULT_DISPLAY, mainExecutor, object : TakeScreenshotCallback {
            override fun onSuccess(result: ScreenshotResult) {
                val hb = result.hardwareBuffer
                try {
                    val hw = Bitmap.wrapHardwareBuffer(hb, result.colorSpace)
                    val soft = hw?.copy(Bitmap.Config.ARGB_8888, false)
                    hw?.recycle()
                    if (soft != null) {
                        val w = if (soft.width > maxW) maxW else soft.width
                        val h = soft.height * w / soft.width
                        val sc = if (w != soft.width) Bitmap.createScaledBitmap(soft, w, h, true) else soft
                        val bos = ByteArrayOutputStream()
                        sc.compress(Bitmap.CompressFormat.JPEG, 70, bos)
                        out = Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP)
                    }
                } catch (e: Exception) {
                    /* out null rahega */
                } finally {
                    try { hb.close() } catch (e: Exception) { /* ignore */ }
                    latch.countDown()
                }
            }

            override fun onFailure(errorCode: Int) {
                latch.countDown()
            }
        })
        latch.await(6, TimeUnit.SECONDS)
        return out
    }

    fun handsRest() {
        main.post {
            hands?.rest()
            main.removeCallbacks(removeHands)
            main.postDelayed(removeHands, 1500)
        }
    }

    // ---------- gesture (sirf worker thread se bulao) ----------
    fun gesture(path: Path, durMs: Long): Boolean {
        val latch = CountDownLatch(1)
        var ok = false
        val g = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, durMs.coerceAtLeast(1)))
            .build()
        val started = dispatchGesture(g, object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                ok = true
                latch.countDown()
            }

            override fun onCancelled(gestureDescription: GestureDescription?) {
                latch.countDown()
            }
        }, null)
        if (!started) return false
        latch.await(durMs + 2000, TimeUnit.MILLISECONDS)
        return ok
    }

    /** Two-finger pinch around the candle plot. scale > 1 spreads fingers (zoom in);
     * scale < 1 brings them together (zoom out). Both strokes start simultaneously. */
    fun pinchZoomAt(centerX: Float, centerY: Float, scale: Float, durationMs: Long = 520L): Boolean {
        if (Build.VERSION.SDK_INT < 24) return false
        val safeScale = scale.coerceIn(0.80f, 1.30f)
        val density = resources.displayMetrics.density
        val startOffset = 34f * density
        val endOffset = startOffset * safeScale
        val left = Path().apply {
            moveTo(centerX - startOffset, centerY)
            lineTo(centerX - endOffset, centerY)
        }
        val right = Path().apply {
            moveTo(centerX + startOffset, centerY)
            lineTo(centerX + endOffset, centerY)
        }
        val latch = CountDownLatch(1)
        var completed = false
        val builder = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(left, 0, durationMs.coerceAtLeast(1)))
            .addStroke(GestureDescription.StrokeDescription(right, 0, durationMs.coerceAtLeast(1)))
        val started = dispatchGesture(builder.build(), object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                completed = true
                latch.countDown()
            }
            override fun onCancelled(gestureDescription: GestureDescription?) {
                latch.countDown()
            }
        }, null)
        if (!started) return false
        latch.await(durationMs + 2000, TimeUnit.MILLISECONDS)
        return completed
    }
}

/** Do haath: baayein haath (✋) aur daayein haath (👆). Screen par sirf kaam ke waqt dikhte hain. */
class HandsView(ctx: Context, private val sw: Int, private val sh: Int) : View(ctx) {

    private val d = ctx.resources.displayMetrics.density
    private val glyph = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = 58f * d
        textAlign = Paint.Align.CENTER
    }
    private val ring = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 3f * d
        color = 0xFFFF4F8B.toInt()
    }
    private var lx = sw * 0.25f
    private var ly = sh + 90f * d
    private var rx = sw * 0.75f
    private var ry = sh + 90f * d
    private var lAnim: ValueAnimator? = null
    private var rAnim: ValueAnimator? = null
    private var wob = 0f
    private var ripX = 0f
    private var ripY = 0f
    private var ripT = -1f
    private val loc = IntArray(2)

    fun moveTo(right: Boolean, x: Float, y: Float, ms: Long, ease: Boolean) {
        val fx = if (right) rx else lx
        val fy = if (right) ry else ly
        (if (right) rAnim else lAnim)?.cancel()
        val a = ValueAnimator.ofFloat(0f, 1f)
        a.duration = ms
        a.interpolator = if (ease) DecelerateInterpolator() else LinearInterpolator()
        a.addUpdateListener {
            val t = it.animatedValue as Float
            val nx = fx + (x - fx) * t
            val ny = fy + (y - fy) * t
            if (right) { rx = nx; ry = ny } else { lx = nx; ly = ny }
            invalidate()
        }
        if (right) rAnim = a else lAnim = a
        a.start()
    }

    fun ripple(x: Float, y: Float) {
        ripX = x
        ripY = y
        val a = ValueAnimator.ofFloat(0f, 1f)
        a.duration = 380
        a.addUpdateListener { ripT = it.animatedValue as Float; invalidate() }
        a.addListener(object : AnimatorListenerAdapter() {
            override fun onAnimationEnd(animation: Animator) {
                ripT = -1f
                invalidate()
            }
        })
        a.start()
    }

    /** Type karte waqt dono haath halke se hilte hain. */
    fun wobble(ms: Long) {
        val a = ValueAnimator.ofFloat(0f, 1f)
        a.duration = ms
        a.addUpdateListener {
            val f = it.animatedValue as Float
            wob = (sin((f * ms / 110f * 2 * PI)) * 7f * d).toFloat()
            invalidate()
        }
        a.addListener(object : AnimatorListenerAdapter() {
            override fun onAnimationEnd(animation: Animator) {
                wob = 0f
                invalidate()
            }
        })
        a.start()
    }

    fun rest() {
        moveTo(false, sw * 0.25f, sh + 90f * d, 450, true)
        moveTo(true, sw * 0.75f, sh + 90f * d, 450, true)
    }

    override fun onDraw(c: Canvas) {
        getLocationOnScreen(loc)
        val ox = loc[0].toFloat()
        val oy = loc[1].toFloat()
        val base = glyph.textSize * 0.85f
        c.drawText("\u270B", lx - ox, ly - oy + base + wob, glyph)
        c.drawText("\uD83D\uDC46", rx - ox, ry - oy + base - wob, glyph)
        if (ripT in 0f..1f) {
            ring.alpha = ((1f - ripT) * 255).toInt()
            c.drawCircle(ripX - ox, ripY - oy, 8f * d + 34f * d * ripT, ring)
        }
    }
}
