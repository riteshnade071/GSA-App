package com.sakura.assistant

import android.app.Notification
import android.app.RemoteInput
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.json.JSONArray
import org.json.JSONObject

/** WhatsApp ki notifications padhta hai aur unka reply-action yaad rakhta hai. */
class NotifService : NotificationListenerService() {

    class Item(val sender: String, val text: String, val time: Long, val action: Notification.Action?)

    companion object {
        private val items = ArrayList<Item>()

        fun unreadJson(): JSONObject {
            val arr = JSONArray()
            synchronized(items) {
                for (it in items.take(10)) {
                    arr.put(
                        JSONObject()
                            .put("from", it.sender)
                            .put("text", it.text.take(300))
                            .put("minutes_ago", (System.currentTimeMillis() - it.time) / 60000)
                            .put("can_reply", it.action != null)
                    )
                }
            }
            val r = JSONObject().put("ok", true).put("messages", arr)
            if (arr.length() == 0) r.put("note", "koi taaza message nahi (ya notification access nahi di)")
            return r
        }

        fun sendReply(ctx: Context, to: String, text: String): JSONObject {
            val item = synchronized(items) {
                items.firstOrNull { it.sender.contains(to, ignoreCase = true) && it.action != null }
            } ?: return JSONObject().put("ok", false)
                .put("error", "'$to' ki koi taaza WhatsApp notification nahi mili, to seedha reply nahi ho sakta")
            val act = item.action!!
            val inputs = act.remoteInputs
            val intent = Intent()
            val bundle = Bundle()
            for (ri in inputs) bundle.putCharSequence(ri.resultKey, text)
            RemoteInput.addResultsToIntent(inputs, intent, bundle)
            act.actionIntent.send(ctx, 0, intent)
            return JSONObject().put("ok", true).put("sent_to", item.sender)
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (sbn.packageName != "com.whatsapp" && sbn.packageName != "com.whatsapp.w4b") return
        val n = sbn.notification
        if ((n.flags and Notification.FLAG_GROUP_SUMMARY) != 0) return
        val ex = n.extras
        val title = ex.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: return
        val text = ex.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: return
        if (title == "WhatsApp" || Regex("^\\d+ (new )?messages?").containsMatchIn(text)) return

        val act = n.actions?.firstOrNull { it.remoteInputs != null && it.remoteInputs.isNotEmpty() }
        val now = System.currentTimeMillis()
        synchronized(items) {
            val last = items.firstOrNull()
            if (last != null && last.sender == title && last.text == text && now - last.time < 60_000) return
            items.add(0, Item(title, text, now, act))
            while (items.size > 30) items.removeAt(items.size - 1)
        }
        Hosts.active?.js(
            "window.onWhatsApp(" + JSONObject.quote(title) + "," + JSONObject.quote(text) + ")"
        )
    }
}
