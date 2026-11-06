package com.sakura.assistant

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AudioEffect
import android.media.audiofx.NoiseSuppressor
import android.os.Process
import java.io.ByteArrayOutputStream

/**
 * Sakura ka EK hi mic. Pehle wake word ek jagah (Vosk) aur hukm doosri jagah (Google recognizer) sunte the:
 * beech me mic chhoot-ta tha, awaaz dabti thi, aur door ki baat nahi pakadti thi.
 *
 * Ab ek hi AudioRecord:
 *  - WAKE: saaf ki hui awaaz Vosk ko ("Hey Sakura" phone par hi pakda jaata hai)
 *  - CAPTURE: ek hukm record (bolna shuru hone se 0.3 s pehle se, khatam hone par 0.8 s chup), WAV bana kar server ko
 *  - IDLE: awaaz fenk do (jab wo khud bol rahi ho, taaki apni awaaz na sune)
 * Har frame Dsp se guzarti hai (door ki awaaz tez, shor kam).
 */
class Mic(private val ctx: Context, private val cb: Cb) {

    interface Cb {
        /** WAKE me saaf ki hui frame */
        fun onWakeFrame(f: ShortArray, n: Int)

        /** CAPTURE khatam. wav null = kuch nahi bola / sirf shor (why me wajah). */
        fun onUtterance(wav: ByteArray?, ms: Int, peak: Float, why: String)

        /** Chhota status ("Bolo…", "Awaaz dheemi hai") */
        fun onState(msg: String)
    }

    enum class Mode { IDLE, WAKE, CAPTURE }

    @Volatile
    var mode = Mode.IDLE

    @Volatile
    private var running = false

    /** Har start par naya number: purana (rukta hua) thread nayi thread se na takraye */
    @Volatile
    private var gen = 0
    private var thread: Thread? = null
    private val fx = ArrayList<AudioEffect>()

    // capture ki sthiti (sirf mic thread chhoota hai; capture() sirf flag rakhta hai)
    @Volatile
    private var waitFrames = 300
    @Volatile
    private var maxFrames = 600
    @Volatile
    private var pendingReset = false
    private val pre = ArrayDeque<ShortArray>()
    private var out = ByteArrayOutputStream()
    private var started = false
    private var frames = 0
    private var speechFrames = 0
    private var silenceRun = 0
    private var peak = 0f
    private val recent = IntArray(8)
    private var ri = 0

    fun alive(): Boolean = running && thread?.isAlive == true

    fun start(): Boolean {
        if (alive()) return true
        if (ctx.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return false
        running = true
        val my = ++gen
        thread = Thread({ loop(my) }, "sakura-mic").also { it.start() }
        return true
    }

    fun stop() {
        running = false
        gen++
        mode = Mode.IDLE
    }

    /** Ek hukm sunna: bolna shuru hone ka waitMs tak intezaar, phir bolna khatam hone tak (maxMs se zyada nahi). */
    fun capture(waitMs: Int = 6000, maxMs: Int = 12000) {
        waitFrames = waitMs / 20
        maxFrames = maxMs / 20
        pendingReset = true
        mode = Mode.CAPTURE
    }

    private fun open(): AudioRecord? {
        val rate = 16000
        val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (min <= 0) return null
        for (src in intArrayOf(MediaRecorder.AudioSource.VOICE_RECOGNITION, MediaRecorder.AudioSource.MIC)) {
            try {
                val r = AudioRecord(src, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(min, 3200) * 4)
                if (r.state == AudioRecord.STATE_INITIALIZED) {
                    attachFx(r.audioSessionId)
                    return r
                }
                r.release()
            } catch (e: Exception) { /* agla source */ }
        }
        return null
    }

    /** Phone ka shor hatana aur apni speaker ki goonj hatana (jahan ho). Gain hum khud sambhalte hain. */
    private fun attachFx(sid: Int) {
        try {
            if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(sid)?.let { it.setEnabled(true); fx.add(it) }
        } catch (e: Exception) { /* ignore */ }
        try {
            if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(sid)?.let { it.setEnabled(true); fx.add(it) }
        } catch (e: Exception) { /* ignore */ }
    }

    private fun loop(my: Int) {
        Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_AUDIO)
        val rec = open()
        if (rec == null) {
            if (gen == my) running = false
            cb.onState("Mic khul nahi paaya (shayad kisi aur app ne mic le rakha hai)")
            return
        }
        val dsp = Dsp()
        val buf = ShortArray(320) // 20 ms
        try {
            rec.startRecording()
            while (running && gen == my) {
                val n = rec.read(buf, 0, buf.size)
                if (n < 0) break
                if (n == 0) continue
                when (mode) {
                    Mode.IDLE -> { /* awaaz fenk do */ }
                    Mode.WAKE -> {
                        dsp.process(buf, n)
                        cb.onWakeFrame(buf, n)
                    }
                    Mode.CAPTURE -> capFrame(dsp, buf, n)
                }
            }
        } catch (e: Exception) {
            cb.onState("Mic error: " + (e.message ?: e.javaClass.simpleName))
        } finally {
            try { rec.stop() } catch (e: Exception) { /* ignore */ }
            rec.release()
            for (e in fx) try { e.release() } catch (x: Exception) { /* ignore */ }
            fx.clear()
            if (gen == my) running = false
        }
    }

    private fun capFrame(dsp: Dsp, buf: ShortArray, n: Int) {
        if (pendingReset) {
            pendingReset = false
            pre.clear()
            out = ByteArrayOutputStream()
            started = false
            frames = 0
            speechFrames = 0
            silenceRun = 0
            peak = 0f
            recent.fill(0)
            ri = 0
            cb.onState("🎙 Bolo…")
        }
        val rms = dsp.process(buf, n)
        frames++
        if (rms > peak) peak = rms
        val sp = dsp.speech
        val f = buf.copyOf(n)
        if (!started) {
            pre.addLast(f)
            if (pre.size > 15) pre.removeFirst() // 0.3 s pehle ki awaaz bhi rakho (shuruaat na kate)
            recent[ri] = if (sp) 1 else 0
            ri = (ri + 1) % recent.size
            if (recent.sum() >= 5) { // pichle 8 me se 5 frame bol-chaal: bolna shuru
                started = true
                speechFrames = recent.sum()
                for (p in pre) write(p)
                pre.clear()
                cb.onState("🎙 Sun rahi hu…")
            } else if (frames >= waitFrames) {
                finish(false, "kuch nahi bola")
            }
        } else {
            write(f)
            if (sp) { speechFrames++; silenceRun = 0 } else silenceRun++
            val endSilence = if (speechFrames > 150) 50 else 40 // lambi baat me 1.0 s, chhote hukm me 0.8 s
            if (silenceRun >= endSilence || frames >= maxFrames) finish(true, "")
        }
    }

    private fun write(f: ShortArray) {
        val b = ByteArray(f.size * 2)
        for (i in f.indices) {
            b[2 * i] = (f[i].toInt() and 0xFF).toByte()
            b[2 * i + 1] = ((f[i].toInt() shr 8) and 0xFF).toByte()
        }
        out.write(b, 0, b.size)
    }

    private fun finish(data: Boolean, why: String) {
        mode = Mode.IDLE // pehle band, taaki agli frame na aaye
        val ms = speechFrames * 20
        val tooShort = data && speechFrames < 12
        val wav = if (data && !tooShort) Dsp.wav(out.toByteArray()) else null
        val reason = if (tooShort) "bahut chhoti awaaz" else why
        cb.onUtterance(wav, ms, peak, reason)
    }
}
