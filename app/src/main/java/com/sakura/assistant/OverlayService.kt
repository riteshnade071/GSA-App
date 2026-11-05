package com.sakura.assistant

import android.app.AlertDialog
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.view.ContextThemeWrapper
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient

/** Dusri apps ke upar girl ko dikhata hai. Naam sunne par bada hota hai, warna chhupa rehta hai. */
class OverlayService : Service(), Host {

    companion object {
        @Volatile
        var running = false

        // Girl ka chhota roop: asli centimetre me (phone ki screen par naap ke). Chhota/bada karna ho to sirf ye do badlo.
        const val MINI_W_CM = 1.8f
        const val MINI_H_CM = 4.0f

        // Page ka apna camera (fitCamera) chhoti window me poora badan dikhata hai; bas "poora badan" mode pakka karo.
        private const val CAM_MINI = "try{viewMode=0;fitCamera()}catch(e){}"
    }

    private var mini = false
    private var busy = false
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun cm(v: Float) = (v / 2.54f * resources.displayMetrics.ydpi).toInt()
    private var wakeLock: android.os.PowerManager.WakeLock? = null

    /** "so jao" / "close": sunna band, jab tak Master app dobara na khole. */
    private fun sleepNow() {
        getSharedPreferences("sakura", MODE_PRIVATE).edit().putBoolean("sleeping", true).apply()
        Agent.cancel()
        try {
            android.media.ToneGenerator(android.media.AudioManager.STREAM_NOTIFICATION, 80)
                .startTone(android.media.ToneGenerator.TONE_PROP_NACK, 300)
        } catch (e: Exception) { /* ignore */ }
        android.widget.Toast.makeText(this, "Sakura so gayi. App khologe to jaag jaayegi", android.widget.Toast.LENGTH_LONG).show()
        stopSelf()
    }

    private lateinit var wm: WindowManager
    private lateinit var lp: WindowManager.LayoutParams
    private lateinit var voice: Voice
    private var web: WebView? = null
    private var baseUrl = ""
    private var loaded = false
    private val main = Handler(Looper.getMainLooper())

    override val ctx: Context get() = this

    override fun onBind(intent: Intent?): IBinder? = null

    override fun js(code: String) {
        main.post { web?.evaluateJavascript(code, null) }
    }

    override fun confirm(title: String, msg: String, yes: () -> Unit, no: () -> Unit) {
        main.post {
            val themed = ContextThemeWrapper(this, android.R.style.Theme_Material_Light_Dialog_Alert)
            val d = AlertDialog.Builder(themed)
                .setTitle(title)
                .setMessage(msg)
                .setPositiveButton("Haan") { _, _ -> yes() }
                .setNegativeButton("Nahi") { _, _ -> no() }
                .setOnCancelListener { no() }
                .create()
            d.window?.setType(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY)
            d.show()
        }
    }

    private fun applyTouch() {
        val w = web ?: return
        val blocked = !mini || busy
        lp.flags = if (blocked) lp.flags or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
        else lp.flags and WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE.inv()
        try { wm.updateViewLayout(w, lp) } catch (e: Exception) { /* view hat chuka */ }
    }

    override fun ghost(on: Boolean) {
        main.post { web?.alpha = if (on) 0f else 1f }
    }

    override fun agentBusy(b: Boolean) {
        main.post { busy = b; applyTouch() }
    }

    override fun overlayShow(show: Boolean) {
        main.post {
            val w = web ?: return@post
            if (show) {
                mini = true
                lp.width = cm(MINI_W_CM)
                lp.height = cm(MINI_H_CM)
                // page abhi load ho rahi ho sakti hai, isliye camera kai baar set karte hain
                for (d in longArrayOf(300, 1500, 3500, 7000)) {
                    main.postDelayed({ if (mini) js(CAM_MINI) }, d)
                }
            } else {
                mini = false
                lp.width = 1
                lp.height = 1
            }
            wm.updateViewLayout(w, lp)
            applyTouch()
        }
    }

    override fun closeOverlay() {
        val i = Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        startActivity(i)
        stopSelf()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "STOP") {
            Agent.cancel()
            stopSelf()
            return START_NOT_STICKY
        }
        val show = intent?.getBooleanExtra("show", false) == true
        val sep = if (baseUrl.contains("?")) "&" else "?"
        if (!loaded && web != null) {
            loaded = true
            web?.loadUrl(baseUrl + sep + "overlay=1" + (if (show) "&show=1" else ""))
        } else if (show && web != null && !mini) {
            // Service chhupi hui sun rahi thi, ab screen par aana hai: page dobara kholo (show=1)
            // taaki wo jaagkar apna adhoora kaam wahin se aage badhaye
            web?.loadUrl(baseUrl + sep + "overlay=1&show=1")
        }
        return START_STICKY
    }

    override fun onCreate() {
        super.onCreate()
        running = true
        Hosts.active = this

        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("sakura", "Sakura", NotificationManager.IMPORTANCE_LOW))
        val stop = PendingIntent.getService(
            this, 1, Intent(this, OverlayService::class.java).setAction("STOP"),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        @Suppress("DEPRECATION")
        val n = Notification.Builder(this, "sakura")
            .setContentTitle("Sakura sun rahi hai")
            .setContentText("'Hey Sakura' bolo. Rokne ke liye 'so jao'")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .addAction(0, "Band karo", stop)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 30) {
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(1, n)
        }

        val base = getSharedPreferences("sakura", MODE_PRIVATE).getString("url", "") ?: ""
        if (base.isEmpty()) {
            stopSelf()
            return
        }

        wm = getSystemService(WINDOW_SERVICE) as WindowManager
        val wv = WebView(this)
        wv.setBackgroundColor(Color.TRANSPARENT)
        val s = wv.settings
        s.javaScriptEnabled = true
        s.domStorageEnabled = true
        s.mediaPlaybackRequiresUserGesture = false
        wv.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest?) {
                request?.let { r -> main.post { r.grant(r.resources) } }
            }
        }
        wv.webViewClient = WebViewClient()
        voice = Voice(this) { code -> js(code) }
        voice.keepOn = true
        voice.onSleep = { sleepNow() }
        wv.addJavascriptInterface(Bridge(this, voice), "Android")

        // Chhoti girl ko ungli se kahin bhi khiska sakte ho
        var lastX = 0f
        var lastY = 0f
        var dragging = false
        var downX = 0f
        var downY = 0f
        wv.setOnTouchListener(View.OnTouchListener { _, e ->
            if (!mini) {
                false
            } else {
                when (e.actionMasked) {
                    MotionEvent.ACTION_DOWN -> {
                        lastX = e.rawX; lastY = e.rawY
                        downX = e.rawX; downY = e.rawY
                        dragging = false
                        false // pehle page ko do: uske chhote buttons dab sakein
                    }
                    MotionEvent.ACTION_MOVE -> {
                        if (!dragging && Math.hypot((e.rawX - downX).toDouble(), (e.rawY - downY).toDouble()) > dp(10)) {
                            dragging = true
                            // page ko bata do ki ye tap nahi, drag hai
                            val c = MotionEvent.obtain(e)
                            c.action = MotionEvent.ACTION_CANCEL
                            wv.onTouchEvent(c)
                            c.recycle()
                        }
                        if (dragging) {
                            val dm = resources.displayMetrics
                            lp.x = (lp.x - (e.rawX - lastX).toInt()).coerceIn(0, maxOf(0, dm.widthPixels - lp.width))
                            lp.y = (lp.y - (e.rawY - lastY).toInt()).coerceIn(0, maxOf(0, dm.heightPixels - lp.height))
                            lastX = e.rawX
                            lastY = e.rawY
                            try { wm.updateViewLayout(wv, lp) } catch (ex: Exception) { }
                        }
                        dragging
                    }
                    else -> dragging
                }
            }
        })

        lp = WindowManager.LayoutParams(
            1, 1,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
            PixelFormat.TRANSLUCENT
        )
        lp.gravity = Gravity.BOTTOM or Gravity.END
        lp.x = dp(6)
        lp.y = dp(110)
        wm.addView(wv, lp)
        web = wv
        baseUrl = base

        // Screen band hone par bhi CPU na soye, warna mic ruk jaata hai
        val pmgr = getSystemService(POWER_SERVICE) as android.os.PowerManager
        wakeLock = pmgr.newWakeLock(android.os.PowerManager.PARTIAL_WAKE_LOCK, "sakura:listen").apply {
            setReferenceCounted(false)
            acquire()
        }
        voice.startWake()
    }

    override fun onDestroy() {
        running = false
        if (::voice.isInitialized) {
            voice.keepOn = false
            voice.stopWake()
            voice.release()
        }
        try { wakeLock?.let { if (it.isHeld) it.release() } } catch (e: Exception) { /* ignore */ }
        try {
            web?.let { wm.removeView(it); it.destroy() }
        } catch (e: Exception) { /* pehle hi hat chuka ho sakta hai */ }
        web = null
        if (Hosts.active === this) Hosts.active = null
        super.onDestroy()
    }
}
