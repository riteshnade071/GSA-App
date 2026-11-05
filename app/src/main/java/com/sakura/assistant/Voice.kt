package com.sakura.assistant

import ai.picovoice.porcupine.PorcupineManager
import ai.picovoice.porcupine.PorcupineManagerCallback
import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import org.json.JSONArray

/**
 * Do hisse:
 * 1) Hindi wake word (Vosk): offline, phone par hi "हे साकुरा" / "साकुरा" sunta hai.
 * 2) Hukm sunna: Hindi-only server STT, zaroorat par Android hi-IN fallback.
 */
class Voice(private val ctx: Context, private val js: (String) -> Unit) {
    private val main = Handler(Looper.getMainLooper())
    private val prefs = ctx.getSharedPreferences("sakura", Context.MODE_PRIVATE)
    private val audio = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var pm: PorcupineManager? = null
    private var sr: SpeechRecognizer? = null
    private var resumeTask: Runnable? = null
    private var wakeWanted = false
    @Volatile
    private var vosk: VoskWake? = null
    private var mic: Mic? = null
    private var sttWatch: Runnable? = null

    private val micCb = object : Mic.Cb {
        override fun onWakeFrame(f: ShortArray, n: Int) {
            vosk?.feed(f, n)
        }

        override fun onUtterance(wav: ByteArray?, ms: Int, peak: Float, why: String) {
            main.post { gotUtterance(wav, ms, peak, why) }
        }

        override fun onState(msg: String) {
            status(msg)
        }
    }

    private fun mic(): Mic = mic ?: Mic(ctx, micCb).also { mic = it }
    private var listening = false

    @Volatile
    private var pausedUntil = 0L

    /** Wo bol rahi hai: apni awaaz na sune. Bolna khatam hone par page listenOnce/resumeWake bulati hai. */
    fun pauseWake() {
        pausedUntil = System.currentTimeMillis() + 60000
        main.post {
            cancelResume()
            pmStop()
        }
    }

    /** true: page stopWake() bole to bhi sunna band nahi hota (sirf "so jao" ya service band hone par). */
    @Volatile
    var keepOn = false

    /** "so jao" / "close" sunne par bulaya jaata hai */
    var onSleep: (() -> Unit)? = null

    private val SLEEP = Regex("^(साकुरा\\s*)?(सो जाओ|सो जा|बंद हो जाओ|चुप हो जाओ|अब आराम करो)[.!।]?$")

    /** Jaag raha hai ya nahi, har 15 second me dekhta hai; mic band mila to dobara chalu. */
    private val watch = object : Runnable {
        override fun run() {
            if (wakeWanted && !listening && System.currentTimeMillis() > pausedUntil && vosk != null) engineStart()
            main.postDelayed(this, 15000)
        }
    }

    /** Page ki status line me likho (Sun rahi hu / model download / jo sunai diya) */
    private fun status(m: String) {
        main.post { js("try{window.onNativeStatus(" + org.json.JSONObject.quote(m) + ")}catch(e){}") }
    }

    private fun startVosk(): String {
        wakeWanted = true
        main.post {
            if (vosk == null) vosk = VoskWake(ctx, { m -> status(m) }) { main.post { onWakeWord() } }
            vosk?.start()
            val m = mic()
            if (!m.start()) status("Mic nahi mil raha: permission ya kisi aur app ne le rakha hai")
            else if (!listening) m.mode = Mic.Mode.WAKE
            main.removeCallbacks(watch)
            main.postDelayed(watch, 15000)
        }
        return "ok"
    }

    private fun engineStart() {
        pausedUntil = 0L
        try { pm?.start() } catch (e: Exception) { /* chalu hi hoga */ }
        if (vosk != null) {
            vosk?.let { if (!it.running) it.start() }
            val m = mic()
            if (m.start() && !listening) m.mode = Mic.Mode.WAKE
        }
    }

    fun release() {
        main.post {
            main.removeCallbacks(watch)
            vosk?.release()
            vosk = null
            mic?.stop()
            mic = null
        }
    }

    @Volatile
    var lang = "hi-IN"

    /** "ok" ya wajah ("no_key", "no_ppn", "no_perm", "error:...") */
    fun startWake(): String {
        if (ctx.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return "no_perm"
        // Hindi wake recognition is the default. The old English Porcupine keyword is
        // available only if the user explicitly opts in through the advanced preference.
        if (!prefs.getBoolean("use_english_porcupine_wake", false)) return startVosk()
        val key = prefs.getString("pv_key", "") ?: ""
        if (key.isBlank()) return startVosk()
        val hasPpn = try { ctx.assets.list("")?.contains("sakura.ppn") == true } catch (e: Exception) { false }
        if (!hasPpn) return startVosk()
        return try {
            if (pm == null) {
                pm = PorcupineManager.Builder()
                    .setAccessKey(key)
                    .setKeywordPath("sakura.ppn")
                    .setSensitivity(0.65f)
                    .build(ctx, PorcupineManagerCallback { _ -> main.post { onWakeWord() } })
            }
            wakeWanted = true
            pm?.start()
            "ok"
        } catch (e: Exception) {
            wakeWanted = false
            pm = null
            "error:" + (e.message ?: e.javaClass.simpleName)
        }
    }

    fun stopWake() {
        if (keepOn) return
        forceStop()
    }

    fun forceStop() {
        main.post {
            wakeWanted = false
            listening = false
            cancelResume()
            main.removeCallbacks(watch)
            pmStop()
            vosk?.stop()
            mic?.stop()
            cancelSttWatch()
            sr?.destroy()
            sr = null
        }
    }

    fun resumeWake() {
        main.post {
            cancelResume()
            if (wakeWanted) engineStart()
        }
    }

    fun listenOnce() {
        main.post {
            cancelResume()
            pmStop()
            listening = true
            mic?.stop() // Google recognizer ko mic chahiye
            quietBeep(900)
            main.postDelayed({ startRecognizer() }, 200)
        }
    }

    /**
     * Naya tareeka: apna mic (shor kam, awaaz tez) se ek hukm record karke page ko WAV deta hai,
     * page use server (Whisper/Gemini) se text banati hai. Ant me page sttDone() bulati hai.
     */
    /** "Wake sikhao": Master 5 baar "Hey Sakura" bolenge, apni awaaz se phrase list banti hai. */
    fun trainWake(count: Int) {
        main.post {
            if (vosk == null) vosk = VoskWake(ctx, { m -> status(m) }) { main.post { onWakeWord() } }
            wakeWanted = true
            cancelResume()
            pausedUntil = 0L
            val m = mic()
            if (!m.start()) {
                status("Mic nahi mil raha: permission ya kisi aur app ne le rakha hai")
                return@post
            }
            m.mode = Mic.Mode.WAKE
            vosk?.train(count) { engineStart() }
        }
    }

    fun clearWakeTraining() {
        main.post {
            vosk?.clearTraining()
            engineStart()
        }
    }

    fun listenServer() {
        main.post {
            cancelResume()
            pmStop()
            listening = true
            val m = mic()
            if (!m.start()) {
                status("Mic nahi mil raha: permission ya kisi aur app ne le rakha hai")
                finish(false)
                return@post
            }
            m.capture(6000, 12000)
            // mic khule hi na ya awaaz na aaye to page hamesha intezaar na kare
            cancelSttWatch()
            val t = Runnable {
                status("Mic se awaaz nahi aayi")
                finish(false)
            }
            sttWatch = t
            main.postDelayed(t, 20000)
        }
    }

    private fun gotUtterance(wav: ByteArray?, ms: Int, peak: Float, why: String) {
        if (wav == null) {
            if (why == "bahut chhoti awaaz" || peak < 140f) status("Awaaz bahut dheemi thi, thoda paas aake bolo")
            finish(false)
            return
        }
        val b64 = android.util.Base64.encodeToString(wav, android.util.Base64.NO_WRAP)
        status("Samajh rahi hu…")
        cancelSttWatch()
        js("window.onNativeAudio('$b64',$ms)")
        val t = Runnable { finish(false) } // page ne 30 second me jawab na diya
        sttWatch = t
        main.postDelayed(t, 30000)
    }

    private fun cancelSttWatch() {
        sttWatch?.let { main.removeCallbacks(it) }
        sttWatch = null
    }

    /** Page ne text banaya: "so jao" jaisa hukm ho to yahin sula do (true). */
    fun sttResult(text: String): Boolean {
        if (onSleep != null && SLEEP.matches(text.trim().lowercase())) {
            main.post {
                cancelSttWatch()
                listening = false
                onSleep?.invoke()
            }
            return true
        }
        return false
    }

    fun sttDone(got: Boolean) {
        main.post {
            cancelSttWatch()
            finish(got)
        }
    }

    private fun onWakeWord() {
        pmStop()
        js("window.onWake()")
        // page ne sunna shuru na kiya to bhi 25 second baad mic wapas chalu
        scheduleResume(25000)
    }

    private fun pmStop() {
        try { pm?.stop() } catch (e: Exception) { /* pehle hi ruka hua */ }
        vosk?.pause()
        mic?.let { if (it.mode == Mic.Mode.WAKE) it.mode = Mic.Mode.IDLE }
    }

    private fun cancelResume() {
        resumeTask?.let { main.removeCallbacks(it) }
        resumeTask = null
    }

    private fun scheduleResume(ms: Long) {
        cancelResume()
        val t = Runnable { if (wakeWanted) engineStart() }
        resumeTask = t
        main.postDelayed(t, ms)
    }

    private fun finish(got: Boolean) {
        listening = false
        js("window.onListenEnd($got)")
        scheduleResume(1800)
    }

    /** Recognizer ki beep ke dauraan kuch der awaaz band (apni awaaz par asar nahi, wo tab nahi bol rahi hoti). */
    private fun quietBeep(ms: Long) {
        val streams = intArrayOf(AudioManager.STREAM_MUSIC, AudioManager.STREAM_NOTIFICATION, AudioManager.STREAM_SYSTEM)
        try { for (s in streams) audio.adjustStreamVolume(s, AudioManager.ADJUST_MUTE, 0) } catch (e: Exception) { /* DND me mana ho sakta hai */ }
        main.postDelayed({
            try { for (s in streams) audio.adjustStreamVolume(s, AudioManager.ADJUST_UNMUTE, 0) } catch (e: Exception) { /* ignore */ }
        }, ms)
    }

    private fun startRecognizer() {
        if (!SpeechRecognizer.isRecognitionAvailable(ctx)) {
            js("window.onNativeStatus('Is phone par speech recognition nahi mili')")
            finish(false)
            return
        }
        sr?.destroy()
        val r = SpeechRecognizer.createSpeechRecognizer(ctx)
        sr = r
        r.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                quietBeep(900)
                val list = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (list != null && list.isNotEmpty()) {
                    if (list.any { SLEEP.matches(it.trim().lowercase()) } && onSleep != null) {
                        listening = false
                        onSleep?.invoke()
                        return
                    }
                    js("window.onNativeSpeech(" + JSONArray(list).toString() + ")")
                    finish(true)
                } else {
                    finish(false)
                }
            }

            override fun onError(error: Int) {
                finish(false)
            }

            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hi-IN")
        i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
        // thoda zyada ruk-kar sune (beech ki saans par na kate) aur app ke naam pehchane
        i.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1600L)
        i.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1300L)
        i.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 400L)
        if (Build.VERSION.SDK_INT >= 33) {
            val bias = ArrayList<String>(AppNames.list(ctx))
            bias.addAll(listOf("साकुरा", "खोलो", "बंद करो", "विश्लेषण", "चार्ट", "ट्रेडिंगव्यू"))
            i.putStringArrayListExtra(RecognizerIntent.EXTRA_BIASING_STRINGS, bias)
        }
        r.startListening(i)
    }
}
