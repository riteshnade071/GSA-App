package com.sakura.assistant

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.sqrt
import kotlin.math.tanh

/**
 * Awaaz saaf karna (door se bolne par bhi). Phone ke mic se aayi 20 ms ki har frame par:
 *  1) High-pass (~100 Hz): pankhe/gadi ki gunj aur DC hatao.
 *  2) Shor ka star (noise floor) apne aap seekho.
 *  3) Auto gain: dheemi (door ki) awaaz ko 40 guna tak badhao, par sirf tab jab awaaz bol-chaal jaisi ho,
 *     taaki shor na badhe. Zor ki awaaz par gain turant kam.
 *  4) Soft limiter: clipping nahi.
 * Android se koi lena-dena nahi, isliye alag se jaanchi ja sakti hai.
 */
class Dsp {
    private var px = 0f
    private var py = 0f
    private val scratch = FloatArray(1024)

    /** Shor ka andaza (RMS) */
    var noise = 60f
        private set

    /** Abhi ka gain (x guna) */
    var gain = 6f
        private set

    /** Pichli frame bol-chaal jaisi thi? */
    var speech = false
        private set

    private var loudRun = 0

    /** frame ko jagah par hi saaf karta hai. Lautata hai: saaf karne se PEHLE ki (high-pass ke baad) RMS. */
    fun process(f: ShortArray, n: Int): Float {
        var sum = 0.0
        for (i in 0 until n) {
            val x = f[i].toFloat()
            val y = HP * (py + x - px)
            px = x
            py = y
            scratch[i] = y
            sum += (y * y).toDouble()
        }
        val rms = sqrt(sum / max(n, 1)).toFloat()

        // shor ka star: shaant frames me jaldi seekho, bol-chaal me bahut dheere upar
        noise = when {
            rms < noise * 1.3f -> noise * 0.94f + rms * 0.06f   // shaant: jaldi seekho
            rms < noise * 2f -> noise * 0.98f + rms * 0.02f     // thoda upar: dheere seekho (naya shor ho sakta hai)
            else -> noise * 1.0004f                              // bol-chaal: lagbhag na badlo
        }
        noise = noise.coerceIn(15f, 2500f)

        speech = rms > max(noise * 2f, 55f)
        // 5 second se lagatar "bol-chaal" ho to wo dar-asal naya shor hai (pankha/AC chala): shor ka star jaldi upar
        loudRun = if (speech) loudRun + 1 else 0
        if (loudRun > 250) noise = (noise * 1.01f).coerceAtMost(rms * 0.8f)
        if (speech) {
            val want = (TARGET / rms).coerceIn(1f, 40f)
            gain += (want - gain) * (if (want < gain) 0.5f else 0.25f) // girna tez, badhna thoda dheere
        } else {
            gain += (6f - gain) * 0.01f // shaanti me dheere normal par
        }
        for (i in 0 until n) {
            val v = scratch[i] * gain
            f[i] = (32767f * tanh(v / 32767f)).toInt().toShort()
        }
        return rms
    }

    companion object {
        private const val HP = 0.96f      // ~100 Hz par 16 kHz
        private const val TARGET = 3500f  // bol-chaal ki manchaahi RMS (lagbhag -20 dBFS)

        /** 16 kHz mono 16-bit WAV bana do */
        fun wav(pcm: ByteArray): ByteArray {
            val total = pcm.size + 36
            val h = ByteArray(44)
            fun i32(o: Int, v: Int) { for (k in 0..3) h[o + k] = ((v shr (8 * k)) and 0xFF).toByte() }
            fun i16(o: Int, v: Int) { h[o] = (v and 0xFF).toByte(); h[o + 1] = ((v shr 8) and 0xFF).toByte() }
            "RIFF".toByteArray().copyInto(h, 0)
            i32(4, total)
            "WAVEfmt ".toByteArray().copyInto(h, 8)
            i32(16, 16); i16(20, 1); i16(22, 1); i32(24, 16000); i32(28, 32000); i16(32, 2); i16(34, 16)
            "data".toByteArray().copyInto(h, 36)
            i32(40, pcm.size)
            return h + pcm
        }

        @Suppress("unused")
        fun peak(f: ShortArray, n: Int): Int {
            var m = 0
            for (i in 0 until n) m = max(m, abs(f[i].toInt()))
            return m
        }
    }
}
