package com.sakura.assistant

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.ZipInputStream

/**
 * Hindi small model ek baar internet se download hota hai (~42 MB), uske baad wake detection offline chalta hai.
 */
object ModelStore {
    private val MODELS = listOf(
        "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip"
    )

    // Separate folder prevents an older English model from being reused accidentally.
    fun isReady(ctx: Context): Boolean = File(ctx.filesDir, "vosk-hi/model/.ready").exists()

    /** Model ki dictionary (graph/words.txt) me se cand me jo shabd hain wo lautao. File na mile to khaali. */
    fun wordsIn(dir: File, cand: Set<String>): Set<String> {
        val f = listOf(File(dir, "graph/words.txt"), File(dir, "words.txt")).firstOrNull { it.exists() } ?: return emptySet()
        val found = HashSet<String>()
        try {
            f.bufferedReader().useLines { lines ->
                for (l in lines) {
                    val w = l.substringBefore(' ').lowercase()
                    if (w in cand) found.add(w)
                }
            }
        } catch (e: Exception) { /* jo mila utna */ }
        return found
    }

    fun ensure(ctx: Context, say: (String) -> Unit): File {
        val root = File(ctx.filesDir, "vosk-hi")
        val dir = File(root, "model")
        if (File(dir, ".ready").exists()) return dir
        root.mkdirs()
        var last: Exception? = null
        for (url in MODELS) {
            try {
                dir.deleteRecursively()
                download(url, root, dir, say)
                return dir
            } catch (e: Exception) {
                last = e
                say("हिंदी मॉडल डाउनलोड नहीं हुआ। इंटरनेट जाँचें।")
            }
        }
        throw last ?: RuntimeException("model nahi mila")
    }

    private fun download(url: String, root: File, dir: File, say: (String) -> Unit) {
        say("हिंदी वेक-वर्ड मॉडल डाउनलोड हो रहा है (लगभग 42 MB, सिर्फ़ एक बार)। इंटरनेट चालू रखें।")
        val zip = File(root, "model.zip")
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 20000
        c.readTimeout = 60000
        val total = c.contentLength.toLong()
        var done = 0L
        var lastPct = -1
        c.inputStream.use { inp ->
            zip.outputStream().use { out ->
                val buf = ByteArray(64 * 1024)
                while (true) {
                    val n = inp.read(buf)
                    if (n < 0) break
                    out.write(buf, 0, n)
                    done += n
                    if (total > 0) {
                        val pct = (done * 100 / total).toInt()
                        if (pct / 10 != lastPct / 10) {
                            lastPct = pct
                            say("Wake model download: $pct%")
                        }
                    }
                }
            }
        }
        say("Model khol rahi hu…")
        val base = dir.canonicalPath + File.separator
        ZipInputStream(zip.inputStream().buffered()).use { z ->
            while (true) {
                val e = z.nextEntry ?: break
                // pehla folder (vosk-model-small-...) hata do
                val rel = e.name.substringAfter('/', "")
                if (rel.isEmpty()) continue
                val f = File(dir, rel)
                if (!f.canonicalPath.startsWith(base)) continue // zip-slip se bachav
                if (e.isDirectory) f.mkdirs() else {
                    f.parentFile?.mkdirs()
                    f.outputStream().use { z.copyTo(it) }
                }
            }
        }
        zip.delete()
        File(dir, ".ready").writeText(url)
        say("हिंदी वेक-वर्ड तैयार। अब 'हे साकुरा' या 'साकुरा' बोलें।")
    }
}

/**
 * Hindi wake phrase "हे साकुरा" / "साकुरा" ko offline pehchanta hai. Mic.kt se cleaned audio frames milte hain.
 * Hindi Vosk model khule shabdon ko transcribe karta hai; WakeGrammar Devanagari output ko normalize karke
 * Sakura ke phonetic variants pehchanta hai. "Wake sikhao" se user ke accent ka recognized phrase bhi save hota hai.
 */
class VoskWake(
    private val ctx: Context,
    private val onStatus: (String) -> Unit,
    private val onHeard: () -> Unit
) {

    companion object {
        private val HEY = setOf("हे", "अरे", "सुनो")

        /** Sirf awaaz ke consonant: sakura -> skr, secure -> skr, she cura -> skr */
        fun skeleton(w: String): String {
            val sb = StringBuilder()
            for (ch in w.lowercase()) {
                val c = when (ch) {
                    's', 'z', 'x' -> 's'
                    'k', 'c', 'q', 'g' -> 'k'
                    'r' -> 'r'
                    else -> null
                } ?: continue
                if (sb.isEmpty() || sb[sb.length - 1] != c) sb.append(c)
            }
            return sb.toString()
        }

        /** Hindi Vosk output: सकुरा / साकुरा / हे साकुरा. */
        fun matchesWake(text: String): Boolean = WakeGrammar.isWakeHindi(text)

    }

    private val main = Handler(Looper.getMainLooper())
    private val lock = Any()
    private var model: Model? = null
    private var modelDir: File? = null
    private var rec: Recognizer? = null

    /** grammar wale phrases (null = khula tareeka) */
    private var phrases: Set<String>? = null
    private var grammarVer = 0
    private var recVer = -1
    private var wanted = false
    private var loading = false

    @Volatile
    private var active = false

    @Volatile
    private var fired = false
    private var lastShown = ""
    private var lastShownAt = 0L

    // wake sikhana
    @Volatile
    private var training = false
    private var trainRec: Recognizer? = null
    private var trainLeft = 0
    private var trainTotal = 0
    private val trainHeard = ArrayList<String>()
    private var trainDone: ((List<String>) -> Unit)? = null
    private var pendingTrain = 0
    private var pendingDone: ((List<String>) -> Unit)? = null

    /** Sun raha hai (mic frames le raha hai) */
    val running: Boolean get() = active

    /** Model taiyaar hai? (nahi to download ho raha hai) */
    val ready: Boolean get() = model != null

    private fun toast(m: String) {
        main.post { Toast.makeText(ctx, m, Toast.LENGTH_LONG).show() }
    }

    private fun say(m: String) {
        onStatus(m)
        toast(m)
    }

    private fun prefs() = ctx.getSharedPreferences("sakura", Context.MODE_PRIVATE)
    private fun debug() = prefs().getBoolean("wake_debug", false)

    private fun userPhrases(): List<String> {
        val raw = prefs().getString("wake_user_phrases", "") ?: ""
        return try {
            val a = JSONArray(raw)
            (0 until a.length()).map { a.getString(it) }
        } catch (e: Exception) { emptyList() }
    }

    /** Model ki dictionary dekhkar wahi phrases jo Vosk samajh sakta hai. null = khula tareeka. */
    private fun computePhrases(dir: File): Set<String>? {
        // Hindi small-model vocabulary may not contain the invented name Sakura.
        // Use open Hindi recognition and a strict local phonetic matcher instead of
        // forcing the recognizer to substitute unrelated dictionary words.
        return null
    }

    /** main thread se bulao */
    fun start() {
        wanted = true
        if (active) return
        val m = model
        if (m == null) load() else begin(m)
    }

    fun pause() {
        active = false
    }

    fun stop() {
        wanted = false
        active = false
    }

    fun release() {
        stop()
        training = false
        synchronized(lock) {
            try { rec?.close() } catch (e: Exception) { /* ignore */ }
            try { trainRec?.close() } catch (e: Exception) { /* ignore */ }
            rec = null
            trainRec = null
        }
        try { model?.close() } catch (e: Exception) { /* ignore */ }
        model = null
    }

    private fun load() {
        if (loading) return
        loading = true
        Thread {
            try {
                val dir = ModelStore.ensure(ctx) { say(it) }
                val m = Model(dir.absolutePath)
                val ph = computePhrases(dir)
                main.post {
                    model = m
                    modelDir = dir
                    phrases = ph
                    grammarVer++
                    loading = false
                    onStatus("हिंदी वेक-वर्ड तैयार है। 'हे साकुरा' या 'साकुरा' बोलें।")
                    if (pendingTrain > 0) {
                        val c = pendingTrain
                        pendingTrain = 0
                        startTrain(m, c, pendingDone ?: { _ -> })
                        pendingDone = null
                    } else if (wanted) begin(m)
                }
            } catch (e: Exception) {
                loading = false
                say("हिंदी वेक-वर्ड मॉडल नहीं मिला (इंटरनेट जाँचें): " + (e.message ?: e.javaClass.simpleName))
                main.postDelayed({ if (wanted) start() }, 30000)
            }
        }.start()
    }

    private fun makeRecognizer(m: Model): Recognizer {
        val ph = phrases
        return if (ph != null) Recognizer(m, 16000.0f, JSONArray(ph.toList() + "[unk]").toString())
        else Recognizer(m, 16000.0f)
    }

    private fun begin(m: Model) {
        try {
            synchronized(lock) {
                val r = rec
                if (r == null || recVer != grammarVer) {
                    try { r?.close() } catch (e: Exception) { /* ignore */ }
                    rec = makeRecognizer(m)
                    recVer = grammarVer
                } else r.reset()
            }
            fired = false
            active = true
            onStatus("सुन रही हूँ। 'हे साकुरा' या 'साकुरा' बोलें।")
        } catch (e: Exception) {
            active = false
            say("Wake engine shuru nahi hua: " + (e.message ?: e.javaClass.simpleName))
        }
    }

    // ---------- mic se frame ----------
    private val acc = ShortArray(1600) // 100 ms: Vosk ko har 20 ms par nahi, batch me do (battery)
    private var accN = 0

    /** Mic thread se: saaf ki hui frame. Bahut halka kaam, 100 ms jama karke Vosk ko dena. */
    fun feed(pcm: ShortArray, n: Int) {
        val tr = training
        if (!tr && (!active || fired)) {
            accN = 0
            return
        }
        var i = 0
        while (i < n) {
            val c = minOf(n - i, acc.size - accN)
            System.arraycopy(pcm, i, acc, accN, c)
            accN += c
            i += c
            if (accN == acc.size) {
                accN = 0
                if (tr) recognizeTrain(acc, acc.size) else recognize(acc, acc.size)
            }
        }
    }

    private fun recognize(pcm: ShortArray, n: Int) {
        var json: String? = null
        synchronized(lock) {
            val r = rec ?: return
            json = try {
                if (r.acceptWaveForm(pcm, n)) r.result else r.partialResult
            } catch (e: Exception) { null }
        }
        check(json)
    }

    private fun check(h: String?) {
        if (h == null) return
        val o = try { JSONObject(h) } catch (e: Exception) { return }
        val t = o.optString("partial").ifEmpty { o.optString("text") }.lowercase().trim()
        if (t.isBlank()) return
        val now = System.currentTimeMillis()
        if (t != lastShown && now - lastShownAt > 400) {
            lastShown = t
            lastShownAt = now
            onStatus("Wake sun raha: " + t.takeLast(50))
            if (debug()) toast("sunai diya: $t")
        }
        val ph = phrases
        val hit = if (ph != null) WakeGrammar.isWake(t, ph) else WakeGrammar.isWakeHindi(t, userPhrases())
        if (!fired && hit) {
            fired = true
            active = false
            main.post { onHeard() }
        }
    }

    // ---------- wake sikhana ----------
    /** Master 'count' baar "Hey Sakura" bolenge; jo Vosk ne likha wo phrase list me jud jaata hai. main thread se. */
    fun train(count: Int, done: (List<String>) -> Unit) {
        wanted = true
        val m = model
        if (m == null) {
            pendingTrain = count
            pendingDone = done
            load()
            say("Wake model taiyaar ho raha hai, ho jaate hi sikhana apne aap shuru hoga")
            return
        }
        startTrain(m, count, done)
    }

    private fun startTrain(m: Model, count: Int, done: (List<String>) -> Unit) {
        try {
            synchronized(lock) {
                try { trainRec?.close() } catch (e: Exception) { /* ignore */ }
                trainRec = Recognizer(m, 16000.0f) // khule shabd: jo sunai de wahi likhta hai
            }
        } catch (e: Exception) {
            say("Sikhana shuru nahi hua: " + (e.message ?: e.javaClass.simpleName))
            return
        }
        trainHeard.clear()
        trainLeft = count
        trainTotal = count
        trainDone = done
        active = false
        accN = 0
        training = true
        say("अब बोलें: हे साकुरा (1/$count)। हर बार बोलकर 1-2 सेकंड रुकें।")
        main.postDelayed({ if (training) endTrain() }, 70000) // 70 second me jitna mila utna
    }

    private fun recognizeTrain(pcm: ShortArray, n: Int) {
        var text: String? = null
        synchronized(lock) {
            val r = trainRec ?: return
            try {
                if (r.acceptWaveForm(pcm, n)) text = JSONObject(r.result).optString("text")
            } catch (e: Exception) { /* agli baar */ }
        }
        val t = text ?: return
        main.post { onTrainText(t) }
    }

    private fun onTrainText(raw: String) {
        if (!training) return
        val c = WakeGrammar.clean(raw) ?: return // khaali ya bekaar awaaz: ginti nahi
        if (c.split(" ").size > 4) return        // lamba vaakya: Hey Sakura nahi
        trainHeard.add(c)
        trainLeft--
        val got = trainTotal - trainLeft
        say("Suna: \"$c\"  ($got/$trainTotal)" + if (trainLeft > 0) ". Phir bolo" else "")
        if (trainLeft <= 0) endTrain()
    }

    private fun endTrain() {
        if (!training) return
        training = false
        synchronized(lock) {
            try { trainRec?.close() } catch (e: Exception) { /* ignore */ }
            trainRec = null
        }
        val heard = trainHeard.distinct()
        if (heard.isNotEmpty()) {
            val all = (userPhrases() + heard).distinct().takeLast(12)
            prefs().edit().putString("wake_user_phrases", JSONArray(all).toString()).apply()
            regrammar()
            say("आवाज़ का नमूना मिल गया: " + heard.joinToString(" | ") + ". अब 'साकुरा' बोलकर जाँचें।")
        } else {
            say("आवाज़ साफ़ नहीं मिली। शांत जगह पर थोड़ा पास आकर फिर बोलें।")
        }
        val d = trainDone
        trainDone = null
        d?.invoke(heard)
    }

    /** Sikha hua mita kar sirf default phrases */
    fun clearTraining() {
        prefs().edit().remove("wake_user_phrases").apply()
        regrammar()
        say("Sikha hua wake mita diya")
    }

    private fun regrammar() {
        val dir = modelDir ?: return
        phrases = computePhrases(dir)
        grammarVer++
        active = false // begin() naya recognizer banayega
    }
}
