package com.sakura.assistant

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.content.Intent
import android.graphics.Path
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.net.Uri
import android.provider.Settings
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Screen par kaam: search, tap, scroll, type. Har kaam ke saath do haath screen par dikhte hain.
 *
 * Suraksha:
 *  - Send / pay / buy / delete jaise button dabane se pehle HAMESHA Master se haan poochha jaata hai.
 *  - Password wale box me kabhi nahi likhti, aur unka text kabhi nahi padhti.
 *  - Screen par jo text dikhta hai wo sirf data hai, hukm nahi (server ko bhi aisa hi maanna chahiye).
 *  - Notification ke "Band karo" se ya stop_agent se kaam turant ruk jaata hai.
 */
object Agent {

    private class Stop : RuntimeException()

    @Volatile
    private var busy = false

    /** 1 = aaram se (haath dikhte hain), 0.45 = tez (seekhi hui recipe chalate waqt) */
    @Volatile
    private var tempo = 1f

    @Volatile
    private var cancelled = false

    fun cancel() {
        cancelled = true
    }

    /** Page har naye hukm par bulati hai: chal raha kaam (jaise auto_scroll) ruk jaata hai. */
    fun agentStart() {
        if (busy) cancelled = true
    }

    private fun ok() = JSONObject().put("ok", true)
    private fun fail(m: String) = JSONObject().put("ok", false).put("error", m)

    private val RISKY = Regex(
        "\\b(send|bhejo|pay|buy|order|delete|remove|confirm|transfer|submit|post|purchase|checkout|subscribe|uninstall|erase|reset|sign ?out|log ?out)\\b",
        RegexOption.IGNORE_CASE
    )

    // ---------- chalane ka dhaancha ----------
    private fun step() {
        if (cancelled) throw Stop()
    }

    private fun sleep(ms0: Long) {
        var left = if (ms0 > 0) maxOf(40L, (ms0 * tempo).toLong()) else 0L
        while (left > 0) {
            step()
            val s = minOf(left, 100L)
            Thread.sleep(s)
            left -= s
        }
    }

    private fun launch(h: Host, done: (JSONObject) -> Unit, early: JSONObject?, body: (AgentService) -> JSONObject) {
        val s = AgentService.instance
        if (s == null) {
            done(fail("Screen control ON nahi hai. Phone setup me 'Haath / screen control' ON karo.").put("needs_access", true))
            return
        }
        if (busy) {
            // naya hukm aaya: chal raha kaam (jaise auto_scroll) rok kar naya shuru karo
            cancelled = true
            Thread {
                var w = 0
                while (busy && w < 40) { Thread.sleep(100); w++ }
                if (busy) done(fail("Pehla kaam abhi chal raha hai"))
                else Handler(Looper.getMainLooper()).post { launch(h, done, early, body) }
            }.start()
            return
        }
        busy = true
        cancelled = false
        h.agentBusy(true)
        Thread {
            val r = try {
                body(s)
            } catch (e: Stop) {
                fail("Master ne rok diya").put("cancelled", true)
            } catch (e: Exception) {
                fail(e.message ?: "error")
            }
            s.handsRest()
            busy = false
            h.agentBusy(false)
            if (early == null) done(r)
        }.start()
        // lambi chalne wale kaam (auto_scroll): turant "shuru ho gaya" bata do, kaam peeche chalta rahe
        if (early != null) done(early)
    }

    /** Master se haan/nahi (worker thread se). */
    private fun ask(title: String, msg: String): Boolean {
        val host = Hosts.active ?: return false
        val latch = CountDownLatch(1)
        var yes = false
        Handler(Looper.getMainLooper()).post {
            host.confirm(title, msg, { yes = true; latch.countDown() }, { latch.countDown() })
        }
        latch.await(60, TimeUnit.SECONDS)
        return yes
    }

    // ---------- entry points ----------
    fun exec(h: Host, name: String, args: JSONObject, done: (JSONObject) -> Unit) {
        if (name == "stop_agent") {
            cancel()
            done(ok())
            return
        }
        if (name == "toggle_setting" && settingKey(args.optString("name")) == "flashlight") {
            done(try { flashlight(h, args.optString("state")) } catch (e: Exception) { fail(e.message ?: "flash nahi chali") })
            return
        }
        tempo = if (args.optBoolean("fast")) 0.45f else 1f
        val early = if (name == "auto_scroll") {
            ok().put("started", true).put("note", "scroll chal raha hai. Rukna ho to 'ruk jao' bolo")
        } else null
        launch(h, done, early) { s ->
            when (name) {
                "read_screen", "screen_read" -> ok().put("screen", snapshot(s, 45))
                "tap" -> tap(s, args)
                "go_back" -> pressKey(s, "back")
                "go_home" -> pressKey(s, "home")
                "type_text" -> typeText(s, args)
                "scroll" -> scroll(s, args)
                "auto_scroll" -> autoScroll(s, args)
                "press_key" -> pressKey(s, args.optString("key"))
                "close_app" -> closeApp(s, args.optString("app"))
                "analyze_chart" -> analyzeChart(h, s)
                "explore_chart" -> exploreChart(h, s, args)
                "toggle_setting" -> toggleSetting(s, args)
                else -> fail("ye kaam mujhe nahi aata: $name")
            }
        }
    }

    /** App pehle se khul chuki hoti hai (Tools.search). Yahan search box dhoondh kar likhna aur Enter. */
    fun search(h: Host, query: String, done: (JSONObject) -> Unit) {
        launch(h, done, null) { s ->
            waitForApp(s)
            var f = pickEdit(all(s))
            if (f == null) {
                val opener = all(s).firstOrNull {
                    it.isVisibleToUser && !it.isEditable && isSearchy(it) &&
                        (it.isClickable || clickableParent(it) != null)
                }
                if (opener != null) {
                    tapNode(s, opener)
                    sleep(1100)
                    f = pickEdit(all(s))
                }
            }
            if (f == null) return@launch fail("search box nahi mila. screen_read karke dekho")
            tapNode(s, f)
            sleep(500)
            val tgt = focusedInput(s) ?: f
            if (tgt.isPassword) return@launch fail("ye password box hai")
            typeInto(s, tgt, query)
            pressEnter(s, tgt)
            sleep(2000)
            ok().put("searched", query).put("screen", snapshot(s, 40))
        }
    }

    // ---------- screen padhna ----------
    private fun walk(n: AccessibilityNodeInfo?, out: MutableList<AccessibilityNodeInfo>, depth: Int) {
        if (n == null || out.size > 400 || depth > 40) return
        out.add(n)
        for (i in 0 until n.childCount) walk(n.getChild(i), out, depth + 1)
    }

    private fun all(s: AgentService): List<AccessibilityNodeInfo> {
        val l = ArrayList<AccessibilityNodeInfo>()
        walk(s.rootInActiveWindow, l, 0)
        return l
    }

    private fun label(n: AccessibilityNodeInfo): String {
        if (n.isPassword) return ""
        val t = n.text?.toString()
        if (!t.isNullOrBlank()) return t
        val c = n.contentDescription?.toString()
        if (!c.isNullOrBlank()) return c
        return n.hintText?.toString() ?: ""
    }

    private fun isSearchy(n: AccessibilityNodeInfo): Boolean {
        val t = (label(n) + " " + (n.hintText ?: "") + " " + (n.viewIdResourceName ?: "")).lowercase()
        return t.contains("search") || t.contains("khoj") || t.contains("खोज")
    }

    private fun pickEdit(l: List<AccessibilityNodeInfo>): AccessibilityNodeInfo? {
        val e = l.filter { it.isEditable && it.isVisibleToUser && !it.isPassword }
        return e.firstOrNull { isSearchy(it) } ?: e.firstOrNull()
    }

    private fun focusedInput(s: AgentService): AccessibilityNodeInfo? =
        s.rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)

    private fun clickableParent(n: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var p: AccessibilityNodeInfo? = n.parent
        var i = 0
        while (p != null && i < 6) {
            if (p.isClickable) return p
            p = p.parent
            i++
        }
        return null
    }

    private fun findByText(s: AgentService, text: String): AccessibilityNodeInfo? {
        val t = text.trim().lowercase()
        val l = all(s).filter { it.isVisibleToUser && label(it).lowercase().contains(t) }
        return l.sortedWith(
            compareBy<AccessibilityNodeInfo>(
                { label(it).lowercase() != t },
                { !(it.isClickable || clickableParent(it) != null) },
                { label(it).length }
            )
        ).firstOrNull()
    }

    private fun labelsAt(s: AgentService, x: Float, y: Float): String {
        val r = Rect()
        return all(s).filter {
            it.getBoundsInScreen(r)
            r.contains(x.toInt(), y.toInt())
        }.joinToString(" ") { label(it) }
    }

    private class Item(val id: Int, val kind: String, val label: String, val x: Int, val y: Int)

    @Volatile
    private var lastItems: List<Item> = emptyList()

    // Bank / UPI / password / OTP wali screen par main kuch nahi karti
    private val SENS_PKG = Regex(
        "phonepe|nbu\\.paisa|paytm|npci|bhim|\\.upi|bank|hdfc|icici|sbi|axisbank|kotak|pnb|yesbank|dreamplug|" +
            "mobikwik|freecharge|authenticator|keepass|bitwarden|lastpass|onepassword",
        RegexOption.IGNORE_CASE
    )
    private val SENS_TXT = Regex(
        "\\b(otp|cvv|upi pin|mpin|password|passcode|one time password)\\b",
        RegexOption.IGNORE_CASE
    )

    private fun isSensitive(s: AgentService, nodes: List<AccessibilityNodeInfo>): Boolean {
        val pkg = s.rootInActiveWindow?.packageName?.toString() ?: ""
        if (SENS_PKG.containsMatchIn(pkg)) return true
        return nodes.any { n ->
            n.isPassword || (n.isVisibleToUser && SENS_TXT.containsMatchIn(
                (n.text?.toString() ?: "") + " " + (n.contentDescription?.toString() ?: "") + " " +
                    (n.hintText?.toString() ?: "")
            ))
        }
    }

    /** Screen ki chhoti pehchaan: kya action ke baad screen badli? */
    private fun sig(s: AgentService): String =
        all(s).filter { it.isVisibleToUser }.map { label(it) }.filter { it.isNotBlank() }.take(60).joinToString("|")

    /** Screen ki list: har item "id|kind|label". id wahi hai jo tap / type_text ko do.
     *  before diya ho to "changed" bhi: action ke baad screen badli ya nahi (recipe ke liye bharosa). */
    private fun snapshot(s: AgentService, max: Int, before: String? = null): JSONObject {
        val nodes = all(s)
        val app = s.rootInActiveWindow?.packageName?.toString() ?: ""
        if (isSensitive(s, nodes)) {
            lastItems = emptyList()
            return JSONObject().put("app", app).put("sensitive", true)
        }
        class Cand(val kind: String, val label: String, val x: Int, val y: Int)
        val cands = ArrayList<Cand>()
        val bounds = Rect()
        for (n in nodes) {
            if (!n.isVisibleToUser) continue
            val lab = label(n).replace("|", "/").replace("\n", " ").take(40)
            val kind = when {
                n.isEditable -> "edit"
                n.isCheckable -> "switch"
                n.isClickable -> "button"
                else -> "text"
            }
            if (lab.isBlank() && kind != "edit") continue
            n.getBoundsInScreen(bounds)
            if (bounds.width() <= 0 || bounds.height() <= 0) continue
            if (cands.any { it.label == lab && Math.abs(it.x - bounds.centerX()) < 8 && Math.abs(it.y - bounds.centerY()) < 8 }) continue
            cands.add(Cand(kind, lab, bounds.centerX(), bounds.centerY()))
        }
        var pick: List<Cand> = cands
        if (cands.size > max) {
            val inter = cands.filter { it.kind != "text" }.take(max * 3 / 4)
            val texts = cands.filter { it.kind == "text" }.take(max - inter.size)
            pick = cands.filter { it in inter || it in texts }
        }
        val items = ArrayList<Item>()
        val arr = JSONArray()
        pick.forEachIndexed { i, c ->
            items.add(Item(i + 1, c.kind, c.label, c.x, c.y))
            arr.put("${i + 1}|${c.kind}|${c.label}")
        }
        lastItems = items
        val result = JSONObject().put("app", app).put("items", arr)
        if (before != null) result.put("changed", sig(s) != before)
        return result
    }

    private fun waitForApp(s: AgentService) {
        val end = System.currentTimeMillis() + 7000
        while (System.currentTimeMillis() < end) {
            val p = s.rootInActiveWindow?.packageName?.toString()
            if (p != null && p != s.packageName) break
            sleep(250)
        }
        sleep(1200)
    }

    // ---------- tap ----------
    private fun tapXY(s: AgentService, x0: Float, y0: Float): Boolean {
        step()
        val x = x0.coerceIn(1f, s.sw - 1f)
        val y = y0.coerceIn(1f, s.sh - 1f)
        s.handMove(true, x, y, (500 * tempo).toLong())
        sleep(560)
        s.handRipple(x, y)
        val ok = s.gesture(Path().apply { moveTo(x, y) }, 60)
        sleep(250)
        return ok
    }

    private fun tapNode(s: AgentService, n: AccessibilityNodeInfo): Boolean {
        val r = Rect()
        n.getBoundsInScreen(r)
        if (tapXY(s, r.exactCenterX(), r.exactCenterY())) return true
        return n.performAction(AccessibilityNodeInfo.ACTION_CLICK) ||
            clickableParent(n)?.performAction(AccessibilityNodeInfo.ACTION_CLICK) == true
    }

    private fun tap(s: AgentService, a: JSONObject): JSONObject {
        if (isSensitive(s, all(s))) return fail("sensitive screen").put("sensitive", true)
        val before = sig(s)
        if (a.has("id")) {
            val id = a.optInt("id", -1)
            val item = lastItems.firstOrNull { it.id == id } ?: return fail("id $id nahi mila. Pehle read_screen karo")
            if (RISKY.containsMatchIn(item.label) && !ask("Master, ye dabaun?", "'${item.label}'")) {
                return fail("Master ne mana kar diya")
            }
            tapXY(s, item.x.toFloat(), item.y.toFloat())
            sleep(900)
            return ok().put("tapped", item.label).put("screen", snapshot(s, 40, before))
        }
        val text = a.optString("text")
        if (text.isBlank()) {
            if (!a.has("x") || !a.has("y")) return fail("text ya x,y batao")
            val x = a.optDouble("x").toFloat()
            val y = a.optDouble("y").toFloat()
            val lab = labelsAt(s, x, y)
            if (RISKY.containsMatchIn(lab) && !ask("Master, ye dabaun?", lab.take(120))) {
                return fail("Master ne mana kar diya")
            }
            tapXY(s, x, y)
            sleep(700)
            return ok().put("screen", snapshot(s, 40, before))
        }
        val n = findByText(s, text) ?: return fail("'$text' screen par nahi dikha. screen_read karo ya scroll karo")
        val lab = label(n)
        if (RISKY.containsMatchIn(lab) && !ask("Master, ye dabaun?", "'$lab'")) {
            return fail("Master ne mana kar diya")
        }
        if (!tapNode(s, n)) return fail("click nahi ho paya")
        sleep(900)
        return ok().put("tapped", lab).put("screen", snapshot(s, 40, before))
    }

    // ---------- type ----------
    private fun setText(n: AccessibilityNodeInfo, t: String): Boolean {
        val b = Bundle()
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, t)
        return n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b)
    }

    private fun typeInto(s: AgentService, f0: AccessibilityNodeInfo, text: String) {
        s.handMove(false, s.sw * 0.28f, s.sh * 0.80f, 350)
        s.handMove(true, s.sw * 0.72f, s.sh * 0.80f, 350)
        sleep(450)
        var f = f0
        val slow = text.length <= 40
        s.handWobble(if (slow) text.length * 70L + 200 else 1500)
        if (slow) {
            for (i in 1..text.length) {
                step()
                f.refresh()
                if (!setText(f, text.substring(0, i))) {
                    f = focusedInput(s) ?: f
                    setText(f, text.substring(0, i))
                }
                Thread.sleep(70)
            }
        } else {
            f.refresh()
            if (!setText(f, text)) setText(focusedInput(s) ?: f, text)
        }
        sleep(300)
    }

    private fun typeText(s: AgentService, a: JSONObject): JSONObject {
        val t = a.optString("text")
        if (t.isEmpty()) return fail("kya likhna hai?")
        val nodes = all(s)
        if (isSensitive(s, nodes)) return fail("sensitive screen").put("sensitive", true)
        var f: AccessibilityNodeInfo? = null
        if (a.has("id")) {
            val id = a.optInt("id", -1)
            val item = lastItems.firstOrNull { it.id == id } ?: return fail("id $id nahi mila. Pehle read_screen karo")
            val r = Rect()
            f = nodes.filter { it.isEditable && it.isVisibleToUser }.minByOrNull {
                it.getBoundsInScreen(r)
                Math.abs(r.centerX() - item.x) + Math.abs(r.centerY() - item.y)
            }
            if (f == null) {
                tapXY(s, item.x.toFloat(), item.y.toFloat())
                sleep(500)
                f = focusedInput(s)
            }
        }
        if (f == null) f = focusedInput(s) ?: pickEdit(nodes)
        if (f == null) return fail("koi text box nahi mila. Pehle use tap karo")
        if (f.isPassword) return fail("password wale box me main nahi likhti").put("sensitive", true)
        if (!f.isFocused) {
            tapNode(s, f)
            sleep(500)
            f = focusedInput(s) ?: f
        }
        typeInto(s, f, t)
        if (a.optBoolean("enter")) pressEnter(s, f)
        sleep(1200)
        return ok().put("screen", snapshot(s, 40))
    }

    private fun pressEnter(s: AgentService, f: AccessibilityNodeInfo) {
        val x = s.sw * 0.9f
        val y = s.sh * 0.92f
        s.handMove(true, x, y, 450)
        sleep(500)
        s.handRipple(x, y)
        var sent = false
        if (Build.VERSION.SDK_INT >= 30) {
            val t = focusedInput(s) ?: f
            sent = t.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id)
        }
        if (!sent) {
            val names = setOf("search", "go", "खोजें")
            val b = all(s).firstOrNull {
                it.isVisibleToUser && it.isClickable && label(it).trim().lowercase() in names
            }
            if (b != null) tapNode(s, b)
        }
        sleep(300)
    }

    // ---------- scroll ----------
    private fun norm(sp: String): String = when (sp.trim().lowercase()) {
        "slow", "slowly", "dheere", "halka" -> "slow"
        "fast", "tez", "jaldi", "quick" -> "fast"
        else -> "medium"
    }

    /** Ek swipe: haath shuru ki jagah jaata hai, phir ungli ke saath-saath wahi lakeer kheenchta hai. */
    private fun swipe(s: AgentService, dir: String, dist: Float, dur: Long) {
        step()
        val w = s.sw.toFloat()
        val h = s.sh.toFloat()
        val cx = w / 2
        val cy = h / 2
        var x1 = cx
        var y1 = cy
        var x2 = cx
        var y2 = cy
        when (dir) {
            "up" -> { y1 = cy - h * dist / 2; y2 = cy + h * dist / 2 }
            "left" -> { x1 = cx - w * dist / 2; x2 = cx + w * dist / 2 }
            "right" -> { x1 = cx + w * dist / 2; x2 = cx - w * dist / 2 }
            else -> { y1 = cy + h * dist / 2; y2 = cy - h * dist / 2 } // down: ungli upar
        }
        s.handMove(true, x1, y1, (350 * tempo).toLong())
        sleep(400)
        s.handDrag(true, x2, y2, dur)
        s.gesture(Path().apply { moveTo(x1, y1); lineTo(x2, y2) }, dur)
        sleep(250)
    }

    private fun scroll(s: AgentService, a: JSONObject): JSONObject {
        if (isSensitive(s, all(s))) return fail("sensitive screen").put("sensitive", true)
        val before = sig(s)
        val dir = a.optString("direction", a.optString("dir", "down")).lowercase()
        val speed = norm(a.optString("speed", "medium"))
        val times = a.optInt("times", 1).coerceIn(1, 15)
        val dist: Float
        val dur: Long
        when (speed) {
            "slow" -> { dist = 0.22f; dur = 1400L }
            "fast" -> { dist = 0.55f; dur = 160L }
            else -> { dist = 0.35f; dur = 450L }
        }
        repeat(times) { swipe(s, dir, dist, dur) }
        sleep(500)
        return ok().put("scrolled", "$dir $speed x$times").put("screen", snapshot(s, 40, before))
    }

    /** Reels / shorts jaisi cheezon ke liye: har every_seconds par ek poora swipe, jab tak ruk jao na bolo. */
    private fun autoScroll(s: AgentService, a: JSONObject): JSONObject {
        val dir = a.optString("direction", a.optString("dir", "down")).lowercase()
        val speed = norm(a.optString("speed", "medium"))
        val every = a.optDouble("every_seconds", 5.0).coerceIn(1.0, 120.0)
        val count = a.optInt("count", 300).coerceIn(1, 300)
        val dur = when (speed) { "slow" -> 900L; "fast" -> 160L; else -> 400L }
        var moved = 0
        var unchanged = 0
        repeat(count) {
            step()
            val before = sig(s)
            swipe(s, dir, 0.45f, dur)
            sleep(350)
            val after = sig(s)
            if (after != before) {
                moved++
                unchanged = 0
            } else {
                unchanged++
            }
            // Accessibility text kabhi video content ke saath nahi badalta. Teen baar no-change
            // par success ka jhootha dawa na karo; caller ko verification limitation batao.
            if (unchanged >= 3) {
                return if (moved > 0) ok().put("done", moved).put("unverified_swipes", unchanged)
                    .put("note", "Kuch scroll hua, lekin aakhri swipes ka screen text se confirmation nahi mila")
                else fail("3 swipe ke baad screen content change confirm nahi hua. Reels viewer khula hai aur screen scrollable hai, ye verify karo.")
                    .put("unverified_swipes", unchanged)
            }
            sleep((every * 1000).toLong())
        }
        return if (moved > 0) ok().put("done", moved).put("note", "Accessibility screen content badla; scroll likely working")
            else fail("Swipe hua, par screen content change confirm nahi hua")
    }

    // ---------- trading chart ki tasveer ----------
    /** Chart ka screenshot (page use server ke vision AI ko bhejti hai). Bank/password/OTP wali screen par nahi. */
    private fun analyzeChart(h: Host, s: AgentService): JSONObject {
        if (Build.VERSION.SDK_INT < 30) return fail("Screenshot ke liye Android 11 ya naya chahiye")
        if (isSensitive(s, all(s))) return fail("sensitive screen").put("sensitive", true)
        val pkg = s.rootInActiveWindow?.packageName?.toString() ?: ""
        if (pkg.isEmpty() || pkg == s.packageName) return fail("Pehle TradingView ya trading app kholo, phir bolo")
        h.ghost(true)
        s.setHandsVisible(false)
        sleep(500)
        val b64 = try { s.screenshotJpegB64(1000) } finally {
            h.ghost(false)
            s.setHandsVisible(true)
        }
        if (b64 == null) {
            return fail("Screenshot nahi mila. Accessibility ek baar OFF karke dobara ON karo (screenshot ki ijazat naye version me judi hai)")
        }
        return ok().put("image", "data:image/jpeg;base64,$b64").put("app", pkg)
    }

    /** TradingView chart ko horizontal history me explore karke multiple independent views capture karta hai.
     *  Finger right swipe se chart ke older candles reveal hote hain; end me current view restore hota hai.
     */
    private fun exploreChart(h: Host, s: AgentService, a: JSONObject): JSONObject {
        if (Build.VERSION.SDK_INT < 30) return fail("Chart exploration screenshots ke liye Android 11 ya naya chahiye")
        if (isSensitive(s, all(s))) return fail("sensitive screen").put("sensitive", true)
        val pkg = s.rootInActiveWindow?.packageName?.toString() ?: ""
        if (pkg.isEmpty() || pkg == s.packageName) return fail("Pehle TradingView chart kholo")
        val count = a.optInt("sections", 4).coerceIn(2, 5)
        val images = JSONArray()
        var captured = 0
        var moved = 0
        var zoomApplied = false
        var zoomRestored = false
        var captureFailed = false
        h.ghost(true)
        s.setHandsVisible(false)
        try {
            sleep(700)
            // Pinch-out only inside the central candle plot: keep top controls and right price scale clear.
            // A modest 1.18x zoom makes candle bodies/wicks easier to inspect during historical pans.
            zoomApplied = s.pinchZoomAt(s.sw * 0.43f, s.sh * 0.47f, 1.18f, 520L)
            if (zoomApplied) sleep(650)

            fun capture(): Boolean {
                step()
                val b64 = s.screenshotJpegB64(1000) ?: return false
                images.put("data:image/jpeg;base64,$b64")
                captured++
                return true
            }
            if (!capture()) {
                captureFailed = true
            } else {
                repeat(count - 1) {
                    if (!captureFailed) {
                        step()
                        // Finger right drag reveals older candles; pinch zoom remains centered on candle plot.
                        swipe(s, "left", 0.48f, 760L)
                        moved++
                        sleep(650)
                        if (!capture()) captureFailed = true
                    }
                }
            }
        } finally {
            // Restore the current/latest viewport, then undo the temporary zoom if it was applied.
            repeat(moved) {
                step()
                swipe(s, "right", 0.48f, 760L)
                sleep(250)
            }
            if (zoomApplied) {
                zoomRestored = s.pinchZoomAt(s.sw * 0.43f, s.sh * 0.47f, 0.8475f, 520L)
                sleep(500)
            }
            h.ghost(false)
            s.setHandsVisible(true)
        }
        return if (captured >= 2) ok().put("images", images).put("sections_captured", captured)
            .put("historical_swipes", moved).put("app", pkg)
            .put("temporary_candle_zoom", zoomApplied)
            .put("zoom_restore_gesture_sent", zoomRestored)
            .put("note", if (zoomApplied && zoomRestored)
                "Candle plot par halka temporary zoom karke historical views capture kiye; latest view aur zoom restore gesture bheja"
            else if (zoomApplied)
                "Candle plot zoom karke historical views capture kiye; original zoom restore gesture confirm nahi hua"
            else
                "Historical views capture hue; device ne two-finger zoom gesture accept nahi kiya, isliye original zoom untouched raha")
        else fail(if (captureFailed) "Chart screenshot beech me capture nahi hua" else "Multiple chart views capture nahi ho paaye")
            .put("sections_captured", captured).put("historical_swipes", moved)
            .put("temporary_candle_zoom", zoomApplied).put("zoom_restore_gesture_sent", zoomRestored)
    }

    // ---------- app band karna ----------
    private fun closeApp(s: AgentService, name: String): JSONObject {
        val pm = s.packageManager
        val pkg: String
        val appName: String
        if (name.isBlank()) {
            val p = s.rootInActiveWindow?.packageName?.toString()
            if (p == null || p == s.packageName) return fail("abhi koi dusri app khuli nahi dikhi")
            pkg = p
            appName = try { pm.getApplicationLabel(pm.getApplicationInfo(p, 0)).toString() } catch (e: Exception) { p }
        } else {
            val q = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
            val m = pm.queryIntentActivities(q, 0).firstOrNull {
                it.loadLabel(pm).toString().contains(name.trim(), ignoreCase = true)
            } ?: return fail("app nahi mili: $name")
            pkg = m.activityInfo.packageName
            appName = m.loadLabel(pm).toString()
        }
        if (pkg == s.packageName) return fail("Main khud ko is tarah band nahi karti. 'so jao' bolo")
        // Settings -> App info -> Force stop (haath se dabate hain)
        s.startActivity(
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$pkg"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
        sleep(1600)
        val force = all(s).firstOrNull {
            val t = label(it).lowercase()
            it.isVisibleToUser && (t.contains("force stop") || t.contains("force-stop") ||
                t.contains("जबरन") || t.contains("ज़बरदस्ती") || t.contains("बलपूर्वक"))
        } ?: return fail("'Force stop' button nahi mila")
        val holder = if (force.isClickable) force else (clickableParent(force) ?: force)
        if (!holder.isEnabled) {
            s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
            return ok().put("closed", appName).put("note", "pehle se band thi")
        }
        tapNode(s, force)
        sleep(1000)
        val yes = setOf("ok", "force stop", "yes", "ठीक है", "ओके")
        val okBtn = all(s).firstOrNull {
            it.isVisibleToUser && it.isClickable && label(it).trim().lowercase() in yes
        }
        if (okBtn != null) {
            tapNode(s, okBtn)
            sleep(700)
        }
        s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
        return ok().put("closed", appName)
    }

    // ---------- net / bluetooth / flash wagairah ----------
    @Volatile
    private var torchOn = false

    private fun settingKey(n: String): String {
        val t = n.lowercase().replace("-", "").replace("_", " ").trim()
        return when {
            t.contains("flash") || t.contains("torch") -> "flashlight"
            t.contains("data") -> "mobile_data"
            t.contains("wifi") || t.contains("wi fi") || t == "net" || t.contains("internet") -> "wifi"
            t.contains("blue") -> "bluetooth"
            t.contains("air") || t.contains("flight") -> "airplane"
            t.contains("hotspot") -> "hotspot"
            t.contains("location") || t.contains("gps") -> "location"
            t.contains("disturb") || t.contains("dnd") -> "dnd"
            t.contains("rotat") -> "rotate"
            t.contains("saver") -> "battery_saver"
            else -> ""
        }
    }

    private val TILE = mapOf(
        "wifi" to listOf("wi-fi", "wifi", "internet", "वाई"),
        "mobile_data" to listOf("mobile data", "cellular data", "internet", "data"),
        "bluetooth" to listOf("bluetooth", "ब्लूटूथ"),
        "airplane" to listOf("airplane", "aeroplane", "flight", "फ़्लाइट"),
        "hotspot" to listOf("hotspot", "tethering"),
        "location" to listOf("location", "gps"),
        "dnd" to listOf("do not disturb", "dnd"),
        "rotate" to listOf("auto-rotate", "auto rotate", "rotation"),
        "battery_saver" to listOf("battery saver", "power saving")
    )

    private fun wantState(st: String): Boolean? = when (st.trim().lowercase()) {
        "on", "enable", "chalu", "start" -> true
        "off", "disable", "band", "stop" -> false
        else -> null
    }

    private fun flashlight(h: Host, state: String): JSONObject {
        val cm = h.ctx.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        val id = cm.cameraIdList.firstOrNull {
            cm.getCameraCharacteristics(it).get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
        } ?: return fail("is phone me flash nahi mila")
        val on = wantState(state) ?: !torchOn
        cm.setTorchMode(id, on)
        torchOn = on
        return ok().put("setting", "flashlight").put("state", if (on) "on" else "off")
    }

    private fun stateOf(vararg ns: AccessibilityNodeInfo): Boolean? {
        for (n in ns) if (n.isCheckable) return n.isChecked
        var t = ns.joinToString(" ") { label(it) }.lowercase()
        if (Build.VERSION.SDK_INT >= 30) t += " " + ns.joinToString(" ") { it.stateDescription?.toString() ?: "" }.lowercase()
        return when {
            Regex("\\boff\\b").containsMatchIn(t) || t.contains("बंद") -> false
            Regex("\\bon\\b").containsMatchIn(t) || t.contains("चालू") -> true
            else -> null
        }
    }

    private fun closePanel(s: AgentService, dialog: Boolean) {
        if (dialog) {
            s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
            sleep(400)
        }
        if (Build.VERSION.SDK_INT >= 31) s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_DISMISS_NOTIFICATION_SHADE)
        else s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
    }

    private fun findTile(s: AgentService, keys: List<String>): AccessibilityNodeInfo? =
        all(s).filter { n ->
            val t = label(n).lowercase()
            n.isVisibleToUser && keys.any { t.contains(it) } && (n.isClickable || clickableParent(n) != null)
        }.sortedWith(
            compareBy<AccessibilityNodeInfo>(
                { if (it.isClickable) 0 else 1 },
                { n -> keys.indexOfFirst { label(n).lowercase().contains(it) } },
                { label(it).length }
            )
        ).firstOrNull()

    /** Quick Settings kholkar wahan ka tile haath se dabana (Wi-Fi, mobile data, Bluetooth, airplane, hotspot...). */
    private fun toggleSetting(s: AgentService, a: JSONObject): JSONObject {
        val key = settingKey(a.optString("name"))
        val keys = TILE[key] ?: return fail("ye setting mujhe nahi aati: ${a.optString("name")}")
        val want = wantState(a.optString("state"))
        s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS)
        sleep(1300)
        var tile = findTile(s, keys)
        var tries = 0
        while (tile == null && tries < 2) { // tile agle page par ho sakta hai
            s.handMove(true, s.sw * 0.8f, s.sh * 0.2f, 300)
            sleep(350)
            s.handDrag(true, s.sw * 0.2f, s.sh * 0.2f, 350)
            s.gesture(Path().apply { moveTo(s.sw * 0.8f, s.sh * 0.2f); lineTo(s.sw * 0.2f, s.sh * 0.2f) }, 350)
            sleep(700)
            tile = findTile(s, keys)
            tries++
        }
        if (tile == null) {
            closePanel(s, false)
            return fail("Quick Settings me '$key' ka tile nahi mila. Use tiles me jodo (edit) ya Settings se karo")
        }
        val holder = if (tile.isClickable) tile else (clickableParent(tile) ?: tile)
        val now = stateOf(holder, tile)
        if (want != null && now == want) {
            closePanel(s, false)
            return ok().put("setting", key).put("state", if (want) "on" else "off").put("note", "pehle se waisa hi tha")
        }
        tapNode(s, tile)
        sleep(1000)
        // Kuch phones me tile panel kholta hai jisme switch hota hai (jaise Internet panel)
        val sw = all(s).firstOrNull { n ->
            val t = label(n).lowercase()
            n.isVisibleToUser && n.isCheckable && keys.any { t.contains(it) }
        }
        var dialog = false
        if (sw != null) {
            dialog = true
            if (want == null || sw.isChecked != want) tapNode(s, sw)
            sleep(700)
        }
        closePanel(s, dialog)
        return ok().put("setting", key).put("state", want?.let { if (it) "on" else "off" } ?: "toggled")
    }

    // ---------- keys ----------
    private fun pressKey(s: AgentService, key: String): JSONObject {
        val done = when (key.lowercase()) {
            "back" -> s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
            "home" -> s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
            "recents" -> s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS)
            "notifications" -> s.performGlobalAction(AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS)
            "enter" -> {
                val f = focusedInput(s)
                if (f != null) { pressEnter(s, f); true } else false
            }
            else -> return fail("key: back / home / recents / notifications / enter")
        }
        sleep(700)
        return if (done) ok().put("screen", snapshot(s, 40)) else fail("ho nahi paya")
    }
}
