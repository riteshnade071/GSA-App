package com.sakura.assistant

import android.content.Context
import android.content.Intent

/** Phone me installed apps ke naam: awaaz pehchanne ko "ye shabd bol sakte hain" batane ke liye. */
object AppNames {
    @Volatile
    private var cache: List<String> = emptyList()
    private var at = 0L

    fun list(ctx: Context): List<String> {
        if (cache.isNotEmpty() && System.currentTimeMillis() - at < 600000) return cache
        val pm = ctx.packageManager
        val q = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val l = try {
            pm.queryIntentActivities(q, 0)
                .map { it.loadLabel(pm).toString().trim() }
                .filter { it.isNotEmpty() && it.length <= 30 }
                .distinct()
        } catch (e: Exception) { emptyList() }
        cache = l.sortedBy { it.length }.take(40)
        at = System.currentTimeMillis()
        return cache
    }
}
