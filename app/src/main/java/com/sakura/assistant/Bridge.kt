package com.sakura.assistant

import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Handler
import android.os.Looper
import android.webkit.JavascriptInterface
import org.json.JSONObject

/** Page ke JavaScript ko phone se jodta hai (window.Android). */
class Bridge(private val host: Host, private val voice: Voice) {
    private val main = Handler(Looper.getMainLooper())

    @JavascriptInterface
    fun startWake(): String = voice.startWake()

    @JavascriptInterface
    fun stopWake() = voice.stopWake()

    @JavascriptInterface
    fun resumeWake() = voice.resumeWake()

    @JavascriptInterface
    fun listenOnce() = voice.listenOnce()

    @JavascriptInterface
    fun pauseWake() = voice.pauseWake()

    /** Naya sunna: apna mic + server STT. Page onNativeAudio(wavBase64, ms) pati hai. */
    @JavascriptInterface
    fun trainWake() = voice.trainWake(5)

    @JavascriptInterface
    fun listenServer() = voice.listenServer()

    @JavascriptInterface
    fun sttResult(text: String): Boolean = voice.sttResult(text)

    @JavascriptInterface
    fun sttDone(got: Boolean) = voice.sttDone(got)

    /** Installed apps ke naam (JSON list), STT ko sahi shabd batane ke liye */
    @JavascriptInterface
    fun appNames(): String = org.json.JSONArray(AppNames.list(host.ctx)).toString()

    /** Naya hukm shuru: chal raha kaam (jaise auto_scroll) ruk jaye. */
    @JavascriptInterface
    fun agentStart() = Agent.agentStart()

    // App kholne ke baad overlay wali page kaam wahin se aage badhati hai
    @JavascriptInterface
    fun savePending(json: String) {
        prefs().edit().putString("pending", json).putLong("pending_t", System.currentTimeMillis()).apply()
    }

    @JavascriptInterface
    fun takePending(): String {
        val p = prefs()
        val j = p.getString("pending", "") ?: ""
        val t = p.getLong("pending_t", 0)
        p.edit().remove("pending").remove("pending_t").apply()
        return if (j.isNotEmpty() && System.currentTimeMillis() - t < 120000) j else ""
    }

    @JavascriptInterface
    fun clearPending() {
        prefs().edit().remove("pending").remove("pending_t").apply()
    }

    private fun prefs() = host.ctx.getSharedPreferences("sakura", android.content.Context.MODE_PRIVATE)

    @JavascriptInterface
    fun setLang(l: String) {
        voice.lang = "hi-IN"
    }

    @JavascriptInterface
    fun setup() {
        main.post { host.setup() }
    }

    @JavascriptInterface
    fun runTool(id: Int, name: String, args: String) {
        main.post { Tools.run(host, id, name, args) }
    }

    @JavascriptInterface
    fun overlayShow(show: Boolean) {
        main.post { host.overlayShow(show) }
    }

    @JavascriptInterface
    fun openOverlay() {
        main.post { host.openOverlay() }
    }

    @JavascriptInterface
    fun closeOverlay() {
        main.post { host.closeOverlay() }
    }

    @JavascriptInterface
    fun battery(): String {
        val i = host.ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = i?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = i?.getIntExtra(BatteryManager.EXTRA_SCALE, 100) ?: 100
        val status = i?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val charging = status == BatteryManager.BATTERY_STATUS_CHARGING ||
            status == BatteryManager.BATTERY_STATUS_FULL
        return JSONObject()
            .put("level", if (scale > 0) level * 100 / scale else -1)
            .put("charging", charging)
            .toString()
    }
}
