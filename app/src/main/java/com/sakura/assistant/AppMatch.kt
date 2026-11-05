package com.sakura.assistant

import android.content.Intent
import android.content.pm.PackageManager

/**
 * App ka naam jaisa bhi bola ho (Hindi, Hinglish, galat spelling, galat suna hua) use sahi app se milata hai.
 * Tareeka: naam ko "awaaz ki chaabi" (consonant classes) me badalte hain aur installed apps ki chaabi se milate hain.
 * Jaise: व्हाट्सएप, whatsap, vatsapp, WhatsApp  ->  sab "ftsp".
 */
object AppMatch {

    class Hit(val label: String, val pkg: String, val score: Double)

    class Result(val best: Hit?, val candidates: List<String>)

    // Devanagari me jo shabd seedhe English naam se jude hain (category wale)
    private val HINDI = listOf(
        "गैलरी" to "gallery", "गैलेरी" to "gallery", "फोटोज" to "gallery", "फोटो" to "gallery", "फ़ोटो" to "gallery",
        "कैमरा" to "camera", "सेटिंग" to "settings", "कैलकुलेटर" to "calculator", "कॉन्टैक्ट" to "contacts",
        "मैसेज" to "messages", "मैप" to "maps", "नक्शा" to "maps", "ब्राउज़र" to "browser", "ब्राउजर" to "browser",
        // awaaz se na milne wale (G = "जी")
        "जीमेल" to "gmail", "जी मेल" to "gmail", "जीपे" to "google pay", "जी पे" to "google pay", "गूगल पे" to "google pay"
    )

    // Chhote roop
    private val SHORT = mapOf(
        "gpay" to "google pay", "g pay" to "google pay", "yt" to "youtube", "fb" to "facebook",
        "wa" to "whatsapp", "insta" to "instagram", "gmail" to "gmail"
    )

    /** Devanagari category shabd ho to English me badlo, warna jaisa hai waisa. */
    fun canon(name: String): String {
        for ((h, e) in HINDI) if (name.contains(h)) return e
        return SHORT[name.trim().lowercase()] ?: name
    }

    private val DEV = mapOf(
        'क' to "k", 'ख' to "k", 'ग' to "g", 'घ' to "g", 'ङ' to "n",
        'च' to "k", 'छ' to "k", 'ज' to "j", 'झ' to "j", 'ञ' to "n",
        'ट' to "t", 'ठ' to "t", 'ड' to "d", 'ढ' to "d", 'ण' to "n",
        'त' to "t", 'थ' to "t", 'द' to "d", 'ध' to "d", 'न' to "n",
        'प' to "p", 'फ' to "f", 'ब' to "b", 'भ' to "b", 'म' to "m",
        'र' to "r", 'ल' to "l", 'व' to "v", 'श' to "s", 'ष' to "s", 'स' to "s",
        'ं' to "n", 'ँ' to "n"
        // य, ह, matra, halant: sirf swar jaise, chaabi me nahi aate
    )

    /** Devanagari -> kaccha Roman (sirf consonant kaafi hain). Latin akshar jaise ke waise. */
    fun roman(s: String): String {
        val sb = StringBuilder()
        for (ch in s) {
            val m = DEV[ch]
            if (m != null) sb.append(m)
            else if (ch.code in 0x0900..0x097F) { /* matra / halant / vowel: chhodo */ }
            else sb.append(ch)
        }
        return sb.toString()
    }

    /** Awaaz ki chaabi: milti-julti awaazein ek hi class me, swar hata do, dohre akshar ek. */
    fun key(s: String): String {
        val sb = StringBuilder()
        var i = 0
        val t = roman(s).lowercase()
        while (i < t.length) {
            val c = t[i]
            var k: Char? = null
            when (c) {
                'p', 'b' -> k = 'P'
                'f', 'v', 'w' -> k = 'F'
                't', 'd' -> k = 'T'
                'k', 'g', 'q' -> k = 'K'
                'c' -> k = if (i + 1 < t.length && t[i + 1] in "eiy") 'S' else 'K' // "face" = s, "chrome" = k
                's', 'z', 'x', 'j' -> k = 'S'
                'm' -> k = 'M'
                'n' -> k = 'N'
                'l' -> k = 'L'
                'r' -> k = 'R'
                else -> {}
            }
            // "ph" ek f hai
            if (c == 'p' && i + 1 < t.length && t[i + 1] == 'h') { k = 'F'; i++ }
            if (k != null && (sb.isEmpty() || sb[sb.length - 1] != k)) sb.append(k)
            i++
        }
        return sb.toString()
    }

    private fun plain(s: String) = roman(s).lowercase().filter { it.isLetterOrDigit() }

    private fun lev(a: String, b: String): Int {
        val d = Array(a.length + 1) { IntArray(b.length + 1) }
        for (i in 0..a.length) d[i][0] = i
        for (j in 0..b.length) d[0][j] = j
        for (i in 1..a.length) for (j in 1..b.length) {
            d[i][j] = minOf(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + if (a[i - 1] == b[j - 1]) 0 else 1)
        }
        return d[a.length][b.length]
    }

    private fun score(qPlain: String, qKey: String, dev: Boolean, label: String): Double {
        val lp = plain(label)
        if (lp.isEmpty()) return 0.0
        if (lp == qPlain) return 1.0
        if (qPlain.length >= 3 && lp.contains(qPlain)) return 0.95
        var best = 0.0
        val words = label.lowercase().split(Regex("[^\\p{L}\\p{N}]+")).filter { it.isNotEmpty() }
        for (cand in listOf(label) + words) {
            val k = key(cand)
            if (k.isEmpty() || qKey.isEmpty()) continue
            val longest = maxOf(k.length, qKey.length)
            val sim = if (k == qKey) 1.0 else 1.0 - lev(k, qKey).toDouble() / longest
            // bahut chhoti chaabi me galti ki gunjaish nahi
            // bahut chhoti chaabi: Roman me bharosa nahi (blah ~ play), Devanagari me barabar chalega
            val s = when {
                longest <= 2 && !dev -> 0.0
                longest <= 3 && k != qKey -> 0.0
                else -> sim * 0.95
            }
            if (s > best) best = s
        }
        return best
    }

    fun find(pm: PackageManager, name: String, selfPkg: String): Result {
        val dev = name.any { it.code in 0x0900..0x097F }
        val qPlain = plain(name)
        val qKey = key(name)
        if (qKey.isEmpty() && qPlain.isEmpty()) return Result(null, emptyList())
        val q = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val hits = ArrayList<Hit>()
        val seen = HashSet<String>()
        for (ri in pm.queryIntentActivities(q, 0)) {
            val pkg = ri.activityInfo.packageName
            if (pkg == selfPkg || !seen.add(pkg)) continue
            val label = ri.loadLabel(pm).toString()
            var sc = score(qPlain, qKey, dev, label)
            // label alag bhasha me ho to package ke naam se bhi dekho (com.whatsapp -> whatsapp)
            val last = pkg.substringAfterLast('.')
            if (sc < 0.9) sc = maxOf(sc, score(qPlain, qKey, dev, last) * 0.92)
            if (sc > 0.0) hits.add(Hit(label, pkg, sc))
        }
        // barabar score par chhota naam pehle ("WhatsApp" "WhatsApp Business" se pehle)
        hits.sortWith(compareByDescending<Hit> { it.score }.thenBy { it.label.length })
        val cands = hits.filter { it.score >= 0.5 }.take(4).map { it.label }
        val top = hits.firstOrNull()
        return Result(if (top != null && top.score >= 0.78) top else null, cands)
    }
}
