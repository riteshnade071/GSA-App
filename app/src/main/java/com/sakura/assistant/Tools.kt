package com.sakura.assistant

import android.content.ContentUris
import android.content.Intent
import android.net.Uri
import android.provider.AlarmClock
import android.provider.ContactsContract
import android.provider.MediaStore
import android.provider.Settings
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Phone par kaam. Message bhejne / dial karne se pehle HAMESHA Master se haan poochha jaata hai
 * (chahe AI kuch bhi kahe). Bahar se aaye message ka text kabhi kaam ki tarah nahi chalta.
 */
object Tools {

    private fun ok() = JSONObject().put("ok", true)
    private fun fail(m: String) = JSONObject().put("ok", false).put("error", m)

    @Volatile
    private var handoffFlag = false

    private val names = java.util.concurrent.ConcurrentHashMap<Int, String>()

    private fun reply(h: Host, id: Int, r: JSONObject) {
        val tool = names.remove(id) ?: "tool"
        if (handoffFlag) {
            handoffFlag = false
            r.put("handoff", true)
        }
        // kaam fail ho to wajah screen par dikhao (taaki pata chale kya gadbad hai)
        if (!r.optBoolean("ok", true) && !r.has("sensitive") && !r.has("cancelled") && r.has("error")) {
            val why = r.optString("error")
            android.os.Handler(android.os.Looper.getMainLooper()).post {
                try { Toast.makeText(h.ctx, "⚠ $tool: $why", Toast.LENGTH_LONG).show() } catch (e: Exception) { /* ignore */ }
            }
        }
        h.js("window.onToolResult($id," + JSONObject.quote(r.toString()) + ")")
    }

    private fun start(h: Host, i: Intent) {
        if (h.beforeLaunch()) handoffFlag = true
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        // Overlay (service) se app kholna Android background se rok deta hai (chupchap fail).
        // Accessibility service ko ye roak nahi, isliye wahi kholti hai.
        val agent = AgentService.instance
        if (h.ctx !is android.app.Activity && agent != null) {
            try {
                agent.startActivity(i)
                return
            } catch (e: Exception) { /* seedha try karte hain */ }
        }
        h.ctx.startActivity(i)
    }

    fun run(h: Host, id: Int, name: String, argsJson: String) {
        val args = try { JSONObject(argsJson) } catch (e: Exception) { JSONObject() }
        names[id] = name
        if (name == "stop_agent") AiHandoff.cancel()
        try { Toast.makeText(h.ctx, "Sakura: $name", Toast.LENGTH_SHORT).show() } catch (e: Exception) {}
        try {
            when (name) {
                "pick_photo" -> {
                    PickActivity.cb = { u ->
                        reply(h, id, if (u == null) fail("photo nahi chuni")
                        else ok().put("uri", u.toString()).put("name", displayName(h, u)))
                    }
                    start(h, Intent(h.ctx, PickActivity::class.java))
                }
                "ai_create" -> {
                    val launcher: (Intent) -> Unit = { i ->
                        val latch = java.util.concurrent.CountDownLatch(1)
                        var err: Exception? = null
                        android.os.Handler(android.os.Looper.getMainLooper()).post {
                            try { start(h, i) } catch (e: Exception) { err = e } finally { latch.countDown() }
                        }
                        latch.await(5, java.util.concurrent.TimeUnit.SECONDS)
                        err?.let { throw it }
                    }
                    AiHandoff.run(h, args, launcher) { r ->
                        android.os.Handler(android.os.Looper.getMainLooper()).post { reply(h, id, r) }
                    }
                }
                "import_edited_photo" -> {
                    PickActivity.cb = { u ->
                        if (u == null) reply(h, id, fail("Edited photo select nahi hui"))
                        else Thread {
                            val result = saveEditedPhoto(h, u)
                            android.os.Handler(android.os.Looper.getMainLooper()).post { reply(h, id, result) }
                        }.start()
                    }
                    start(h, Intent(h.ctx, PickActivity::class.java))
                }
                "compare_photos" -> {
                    PickActivity.cb = { before ->
                        if (before == null) reply(h, id, fail("Original photo select nahi hui"))
                        else {
                            PickActivity.cb = { after ->
                                if (after == null) reply(h, id, fail("Edited photo select nahi hui"))
                                else {
                                    val i = Intent(h.ctx, PhotoCompareActivity::class.java)
                                        .putExtra("before", before.toString())
                                        .putExtra("after", after.toString())
                                    start(h, i)
                                    reply(h, id, ok().put("opened", true).put("before", before.toString()).put("after", after.toString()))
                                }
                            }
                            start(h, Intent(h.ctx, PickActivity::class.java))
                        }
                    }
                    start(h, Intent(h.ctx, PickActivity::class.java))
                }
                "find_photos" -> reply(h, id, findPhotos(h, args))
                "find_files" -> reply(h, id, findFiles(h, args))
                "open_media" -> reply(h, id, openMedia(h, args.optString("uri")))
                "open_app" -> reply(h, id, openApp(h, args.optString("name")))
                "open_url" -> reply(h, id, openUrl(h, args.optString("url")))
                "set_alarm" -> reply(h, id, setAlarm(h, args))
                "read_screen", "screen_read", "tap", "type_text", "scroll", "go_back", "go_home",
                "press_key", "stop_agent", "close_app", "toggle_setting", "auto_scroll", "analyze_chart", "explore_chart" -> {
                    if ((name == "analyze_chart" || name == "explore_chart") && h.ctx is android.app.Activity) {
                        reply(h, id, fail("Pehle TradingView ya trading app kholo, phir overlay se bolo: chart analyze karo"))
                        return
                    }
                    // Sakura app ke andar se ye kaam aaye to pehle overlay me chali jaye (dusri app ke upar)
                    if (name == "close_app" || name == "toggle_setting" || name == "auto_scroll" || name == "explore_chart") {
                        if (h.beforeLaunch()) handoffFlag = true
                    }
                    Agent.exec(h, name, args) { res -> reply(h, id, res) }
                }
                "whatsapp_unread" -> reply(h, id, NotifService.unreadJson())
                "dial" -> {
                    val who = args.optString("contact")
                    val num = number(h, who)
                    if (num == null) reply(h, id, fail("number nahi mila: $who"))
                    else confirm(h, id, "Dial karun?", "$who ($num)") {
                        start(h, Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(num))))
                        ok()
                    }
                }
                "whatsapp_send" -> {
                    val who = args.optString("contact")
                    val text = args.optString("text")
                    val num = number(h, who)
                    if (num == null || text.isBlank()) reply(h, id, fail("number ya message nahi mila"))
                    else confirm(h, id, "WhatsApp chat kholun?", "To: $who\n\n$text\n\n(Bhejne ke liye WhatsApp me Send aap dabaoge)") {
                        val url = "https://wa.me/${waDigits(num)}?text=" + URLEncoder.encode(text, "UTF-8")
                        start(h, Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                        ok()
                    }
                }
                "whatsapp_reply" -> {
                    val to = args.optString("to")
                    val text = args.optString("text")
                    if (to.isBlank() || text.isBlank()) reply(h, id, fail("kisko ya kya bhejna hai, nahi mila"))
                    else confirm(h, id, "WhatsApp reply bhejun?", "To: $to\n\n$text") {
                        NotifService.sendReply(h.ctx, to, text)
                    }
                }
                else -> reply(h, id, fail("ye kaam mujhe nahi aata: $name"))
            }
        } catch (e: Exception) {
            reply(h, id, fail(e.message ?: "error"))
        }
    }

    private fun confirm(h: Host, id: Int, title: String, msg: String, action: () -> JSONObject) {
        h.confirm(
            title, msg,
            { reply(h, id, try { action() } catch (e: Exception) { fail(e.message ?: "error") }) },
            { reply(h, id, fail("Master ne mana kar diya")) }
        )
    }

    /** Copy an AI-app result into Pictures/Sakura so it is visible in Gallery. */
    private fun saveEditedPhoto(h: Host, source: Uri): JSONObject {
        val resolver = h.ctx.contentResolver
        val mime = resolver.getType(source) ?: "image/jpeg"
        val ext = android.webkit.MimeTypeMap.getSingleton().getExtensionFromMimeType(mime) ?: "jpg"
        val name = "Sakura_Edit_" + java.text.SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date()) + "." + ext
        return try {
            val values = android.content.ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, name)
                put(MediaStore.Images.Media.MIME_TYPE, mime)
                if (android.os.Build.VERSION.SDK_INT >= 29) {
                    put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/Sakura")
                    put(MediaStore.Images.Media.IS_PENDING, 1)
                }
            }
            val target = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                ?: return fail("Gallery mein file create nahi hui")
            try {
                val input = resolver.openInputStream(source) ?: throw java.io.IOException("Selected image read nahi hui")
                input.use { src ->
                    val output = resolver.openOutputStream(target, "w") ?: throw java.io.IOException("Gallery file write nahi hui")
                    output.use { dst -> src.copyTo(dst) }
                }
                if (android.os.Build.VERSION.SDK_INT >= 29) {
                    val ready = android.content.ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) }
                    resolver.update(target, ready, null, null)
                }
                ok().put("uri", target.toString()).put("name", name)
                    .put("saved_to", "Pictures/Sakura").put("note", "Edited photo Gallery ke Pictures/Sakura album mein save ho gayi.")
            } catch (e: Exception) {
                resolver.delete(target, null, null)
                throw e
            }
        } catch (e: Exception) {
            fail("Edited photo save nahi hui: ${e.message ?: "unknown error"}")
        }
    }

    // ---------- tareekh ----------
    private fun day(s: String, endOfDay: Boolean, dflt: Long): Long {
        if (s.isBlank()) return dflt
        val d = try { SimpleDateFormat("yyyy-MM-dd", Locale.US).parse(s) } catch (e: Exception) { null } ?: return dflt
        return d.time + (if (endOfDay) 86_400_000L else 0L)
    }

    // ---------- photos ----------
    private fun findPhotos(h: Host, args: JSONObject): JSONObject {
        val perm = if (android.os.Build.VERSION.SDK_INT >= 33) android.Manifest.permission.READ_MEDIA_IMAGES
        else android.Manifest.permission.READ_EXTERNAL_STORAGE
        if (h.ctx.checkSelfPermission(perm) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            return fail("Photos ki permission band hai. Phone Settings > Apps > Sakura > Permissions > Photos me 'Allow all' karo")
                .put("needs_permission", true)
        }
        val from = day(args.optString("from"), false, 0L)
        val toStr = args.optString("to").ifBlank { args.optString("from") }
        val to = day(toStr, true, 4_102_444_800_000L)
        val base = MediaStore.Images.Media.EXTERNAL_CONTENT_URI
        val dt = MediaStore.Images.Media.DATE_TAKEN
        val da = MediaStore.Images.Media.DATE_ADDED
        val bk = MediaStore.Images.Media.BUCKET_DISPLAY_NAME
        val proj = arrayOf(MediaStore.Images.Media._ID, MediaStore.Images.Media.DISPLAY_NAME, dt, da, bk)
        // Gallery ke SAARE albums (Camera, WhatsApp, Screenshots...) me ek saath dhoondhta hai; album diya ho to sirf wahi
        val album = args.optString("album").trim()
        // DATE_TAKEN kai photos (WhatsApp, screenshot) me NULL ya 0 hota hai: tab DATE_ADDED se milate hain
        var sel = "(($dt > 0 AND $dt >= ? AND $dt < ?) OR (($dt IS NULL OR $dt <= 0) AND $da >= ? AND $da < ?))"
        var sa = arrayOf(from.toString(), to.toString(), (from / 1000).toString(), (to / 1000).toString())
        if (album.isNotEmpty()) {
            sel += " AND $bk LIKE ?"
            sa += "%$album%"
        }
        val out = JSONArray()
        var total = 0
        val fmt = SimpleDateFormat("dd MMM yyyy HH:mm", Locale.getDefault())
        h.ctx.contentResolver.query(base, proj, sel, sa, "$dt DESC")?.use { c ->
            total = c.count
            while (c.moveToNext() && out.length() < 8) {
                val taken = if (!c.isNull(2) && c.getLong(2) > 0) c.getLong(2) else c.getLong(3) * 1000
                out.put(
                    JSONObject()
                        .put("uri", ContentUris.withAppendedId(base, c.getLong(0)).toString())
                        .put("name", c.getString(1))
                        .put("date", fmt.format(Date(taken)))
                        .put("album", c.getString(4) ?: "")
                )
            }
        }
        val r = ok().put("total", total).put("shown", out)
            .put("range", args.optString("from") + " se " + toStr)
        if (total == 0) r.put("note", "is tareekh me koi photo nahi mili. Tareekh/saal sahi thi? Master se poochho")
        return r
    }

    private fun displayName(h: Host, u: Uri): String {
        return try {
            h.ctx.contentResolver.query(u, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)
                ?.use { c -> if (c.moveToFirst()) c.getString(0) else null } ?: "photo"
        } catch (e: Exception) { "photo" }
    }

    // ---------- files ----------
    private fun findFiles(h: Host, args: JSONObject): JSONObject {
        val q = args.optString("query")
        if (q.isBlank()) return fail("kya dhoondna hai?")
        val base = MediaStore.Files.getContentUri("external")
        val proj = arrayOf(
            MediaStore.Files.FileColumns._ID,
            MediaStore.Files.FileColumns.DISPLAY_NAME,
            MediaStore.Files.FileColumns.DATE_MODIFIED,
            MediaStore.Files.FileColumns.SIZE
        )
        val out = JSONArray()
        var total = 0
        val fmt = SimpleDateFormat("dd MMM yyyy", Locale.getDefault())
        h.ctx.contentResolver.query(
            base, proj, MediaStore.Files.FileColumns.DISPLAY_NAME + " LIKE ?", arrayOf("%$q%"),
            MediaStore.Files.FileColumns.DATE_MODIFIED + " DESC"
        )?.use { c ->
            total = c.count
            while (c.moveToNext() && out.length() < 8) {
                out.put(
                    JSONObject()
                        .put("uri", ContentUris.withAppendedId(base, c.getLong(0)).toString())
                        .put("name", c.getString(1))
                        .put("date", fmt.format(Date(c.getLong(2) * 1000)))
                        .put("size_kb", c.getLong(3) / 1024)
                )
            }
        }
        val r = ok().put("total", total).put("shown", out)
        if (total == 0) r.put("note", "kuch nahi mila. 'All files access' di hai?")
        return r
    }

    private fun openMedia(h: Host, uriStr: String): JSONObject {
        if (uriStr.isBlank()) return fail("uri nahi mila")
        val u = Uri.parse(uriStr)
        val i = Intent(Intent.ACTION_VIEW)
            .setDataAndType(u, h.ctx.contentResolver.getType(u) ?: "*/*")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        start(h, i)
        return ok()
    }

    // ---------- apps / url / alarm ----------
    private val CATS = mapOf(
        "gallery" to Intent.CATEGORY_APP_GALLERY,
        "photos" to Intent.CATEGORY_APP_GALLERY,
        "photo" to Intent.CATEGORY_APP_GALLERY,
        "album" to Intent.CATEGORY_APP_GALLERY,
        "calculator" to Intent.CATEGORY_APP_CALCULATOR,
        "browser" to Intent.CATEGORY_APP_BROWSER,
        "contacts" to Intent.CATEGORY_APP_CONTACTS,
        "messages" to Intent.CATEGORY_APP_MESSAGING,
        "sms" to Intent.CATEGORY_APP_MESSAGING,
        "maps" to Intent.CATEGORY_APP_MAPS,
        "music" to Intent.CATEGORY_APP_MUSIC,
        "email" to Intent.CATEGORY_APP_EMAIL,
        "calendar" to Intent.CATEGORY_APP_CALENDAR
    )

    private fun openApp(h: Host, name0: String): JSONObject {
        val name = AppMatch.canon(name0.trim())
        val n = name.lowercase()
        if (n.isEmpty()) return fail("kaun si app?")
        for ((k, cat) in CATS) {
            if (n.contains(k)) {
                try {
                    start(h, Intent(Intent.ACTION_MAIN).addCategory(cat))
                    return ok().put("opened", k)
                } catch (e: Exception) { /* label se dhoondhenge */ }
            }
        }
        if (n.contains("camera")) {
            try {
                start(h, Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA))
                return ok().put("opened", "camera")
            } catch (e: Exception) { /* label se dhoondhenge */ }
        }
        if (n.contains("setting")) {
            start(h, Intent(Settings.ACTION_SETTINGS))
            return ok().put("opened", "settings")
        }
        // naam jaisa bhi bola ho (Hindi, galat spelling) awaaz ke hisaab se sabse milti app dhoondo
        val pm = h.ctx.packageManager
        val res = AppMatch.find(pm, name, h.ctx.packageName)
        val best = res.best
        if (best == null) {
            val r = fail("app nahi mili: $name0")
            if (res.candidates.isNotEmpty()) {
                val arr = JSONArray()
                res.candidates.forEach { arr.put(it) }
                r.put("candidates", arr)
            }
            return r
        }
        val li = pm.getLaunchIntentForPackage(best.pkg) ?: return fail("app khul nahi saki")
        start(h, li)
        return ok().put("opened", best.label)
    }

    private fun openUrl(h: Host, url: String): JSONObject {
        if (!(url.startsWith("https://") || url.startsWith("http://"))) return fail("sirf http/https link")
        start(h, Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        return ok()
    }

    private fun setAlarm(h: Host, args: JSONObject): JSONObject {
        val i = Intent(AlarmClock.ACTION_SET_ALARM)
            .putExtra(AlarmClock.EXTRA_HOUR, args.optInt("hour", 7))
            .putExtra(AlarmClock.EXTRA_MINUTES, args.optInt("minute", 0))
            .putExtra(AlarmClock.EXTRA_MESSAGE, args.optString("label", "Sakura"))
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true)
        start(h, i)
        return ok()
    }

    // ---------- contacts ----------
    private fun number(h: Host, who: String): String? {
        if (who.isBlank()) return null
        if (who.count { it.isDigit() } >= 7) return who.filter { it.isDigit() || it == '+' }
        val p = ContactsContract.CommonDataKinds.Phone.CONTENT_URI
        h.ctx.contentResolver.query(
            p, arrayOf(ContactsContract.CommonDataKinds.Phone.NUMBER),
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " LIKE ?", arrayOf("%$who%"), null
        )?.use { c -> if (c.moveToFirst()) return c.getString(0) }
        return null
    }

    /** wa.me ko country code ke saath digits chahiye. 10 digit ho to India (91) maan lete hain. */
    private fun waDigits(num: String): String {
        val d = num.filter { it.isDigit() }
        return if (d.length == 10) "91$d" else d
    }
}
