package com.sakura.assistant

import android.content.ClipData
import android.content.Intent
import android.net.Uri
import org.json.JSONObject

/**
 * Free/manual photo handoff. Sakura never presses Send or claims an edit completed.
 * The user chooses a free tier/provider account, sends the prompt themselves, saves
 * the generated image, then imports it back with import_edited_photo.
 */
object AiHandoff {
    private data class Provider(val label: String, val pkg: String)
    private val providers = listOf(
        Provider("ChatGPT", "com.openai.chatgpt"),
        Provider("Gemini", "com.google.android.apps.bard"),
        Provider("Claude", "com.anthropic.claude")
    )

    private fun ok() = JSONObject().put("ok", true)
    private fun fail(message: String) = JSONObject().put("ok", false).put("error", message)

    fun run(h: Host, args: JSONObject, launcher: (Intent) -> Unit, done: (JSONObject) -> Unit) {
        val kind = args.optString("kind", "edit")
        val uriText = args.optString("uri").trim()
        val prompt = args.optString("prompt").trim()
        if (uriText.isBlank()) { done(fail("Photo nahi mili. Pehle pick_photo chalao.")); return }
        if (prompt.isBlank()) { done(fail("Edit prompt khaali hai.")); return }
        val uri = Uri.parse(uriText)
        if (uri.scheme != "content") { done(fail("Sirf Gallery/Photo Picker ki content URI supported hai.")); return }

        val installed = providers.filter { h.ctx.packageManager.getLaunchIntentForPackage(it.pkg) != null }
        if (installed.isEmpty()) {
            done(fail("ChatGPT, Gemini ya Claude app nahi mili. Inmein se koi app install karke dobara try karo."))
            return
        }
        val message = if (kind == "pdf")
            "Create a clean, professional PDF from the attached image. $prompt Return a downloadable PDF."
        else prompt
        val chooser = Intent(Intent.ACTION_SEND).apply {
            type = "image/*"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_TEXT, message)
            clipData = ClipData.newUri(h.ctx.contentResolver, "Sakura source photo", uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        val labels = installed.joinToString(" / ") { it.label }
        h.confirm(
            "Free AI app mein photo bhejun?",
            "Available apps: $labels\n\nSakura sirf app kholegi aur photo + prompt share karegi. SEND aap khud dabayenge. AI app mein edit complete hone ke baad image ko save/share karke Sakura mein import karna hoga. Sakura result banne ka daawa nahi karegi.",
            {
                Thread {
                    try {
                        launcher(Intent.createChooser(chooser, "Photo edit karne ke liye app chunein"))
                        done(ok().put("handoff", true).put("sent", false)
                            .put("providers", labels)
                            .put("note", "AI app chooser khul gaya. App chuno, prompt check karo aur Send khud dabao. Edit hone ke baad edited image save karke Sakura mein 'import edited photo' bolo."))
                    } catch (e: Exception) {
                        done(fail("AI app nahi khul paayi: ${e.message ?: "unknown error"}"))
                    }
                }.start()
            },
            { done(fail("Master ne photo share karna cancel kiya.")) }
        )
    }
}
