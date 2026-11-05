package com.sakura.assistant

import java.text.Normalizer

/** Hindi-only wake matcher. User says: "हे साकुरा" or simply "साकुरा". */
object WakeGrammar {
    private val marks = Regex("\\p{M}+")
    private val nonLetters = Regex("[^\\p{L}\\s]")
    private val spaces = Regex("\\s+")

    /** Normalize Devanagari matras so साकुरा / सकुरा produce the same short key. */
    fun normalize(text: String): String = Normalizer.normalize(text.lowercase(), Normalizer.Form.NFD)
        .replace(marks, "")
        .replace(nonLetters, " ")
        .trim()
        .replace(spaces, " ")

    fun clean(p: String): String? {
        val t = normalize(p)
        if (t.isBlank() || t.contains("unk")) return null
        val n = t.split(" ").size
        return if (n <= 5 && t.length >= 2) t else null
    }

    /** Vosk Hindi output may be सकुरा, साकुरा, हे साकुरा, or split into two tokens. */
    fun isWakeHindi(text: String, learned: List<String> = emptyList()): Boolean {
        val t = normalize(text)
        if (t.isBlank()) return false
        if (learned.any { normalize(it) == t }) return true
        val tokens = t.split(" ").filter { it.isNotBlank() }
        if (tokens.size > 5) return false
        val wakeKey = "सकर" // matras removed from साकुरा / सकुरा
        if (tokens.any { it == wakeKey || (it.startsWith(wakeKey) && it.length <= 5) }) return true
        if (tokens.size <= 3 && tokens.joinToString("") == wakeKey) return true
        // ASR sometimes separates the three syllables: सा कु रा -> स क र
        if (tokens.size <= 4 && tokens.joinToString("") == wakeKey) return true
        return false
    }

    // Kept for compatibility with the recognizer's older grammar interface.
    fun candidateWords(user: List<String>): Set<String> =
        (listOf("हे", "सकुरा", "साकुरा", "सकर") + user.mapNotNull { clean(it) })
            .flatMap { it.split(" ") }.filter { it.isNotBlank() }.toSet()

    fun build(has: (String) -> Boolean, user: List<String>): List<String> = emptyList()

    fun isWake(text: String, phrases: Set<String>): Boolean = isWakeHindi(text)
}
