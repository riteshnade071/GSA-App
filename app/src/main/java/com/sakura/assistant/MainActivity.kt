package com.sakura.assistant

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.webkit.JsPromptResult
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.Toast

class MainActivity : Activity(), Host {

    lateinit var web: WebView
    private lateinit var voice: Voice
    private var dialogOpen = false
    private var fileCb: ValueCallback<Array<Uri>>? = null

    private val prefs get() = getSharedPreferences("sakura", MODE_PRIVATE)

    override val ctx: Context get() = this

    override fun js(code: String) {
        runOnUiThread { web.evaluateJavascript(code, null) }
    }

    override fun confirm(title: String, msg: String, yes: () -> Unit, no: () -> Unit) {
        AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(msg)
            .setPositiveButton("Haan") { _, _ -> yes() }
            .setNegativeButton("Nahi") { _, _ -> no() }
            .setOnCancelListener { no() }
            .show()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Hosts.active = this
        web = WebView(this)
        setContentView(web)
        voice = Voice(this) { code -> js(code) }

        val s = web.settings
        s.javaScriptEnabled = true
        s.domStorageEnabled = true
        s.mediaPlaybackRequiresUserGesture = false

        web.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest?) {
                request?.let { r -> runOnUiThread { r.grant(r.resources) } }
            }

            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                this@MainActivity.fileCb?.onReceiveValue(null)
                this@MainActivity.fileCb = filePathCallback
                val i = Intent(Intent.ACTION_GET_CONTENT)
                i.addCategory(Intent.CATEGORY_OPENABLE)
                i.type = "*/*"
                return try {
                    startActivityForResult(Intent.createChooser(i, "VRM file chuno"), 77)
                    true
                } catch (e: Exception) {
                    this@MainActivity.fileCb = null
                    false
                }
            }

            override fun onJsPrompt(
                view: WebView?, url: String?, message: String?,
                defaultValue: String?, result: JsPromptResult?
            ): Boolean {
                val et = EditText(this@MainActivity)
                AlertDialog.Builder(this@MainActivity)
                    .setTitle(message ?: "")
                    .setView(et)
                    .setPositiveButton("OK") { _, _ -> result?.confirm(et.text.toString()) }
                    .setNegativeButton("Cancel") { _, _ -> result?.cancel() }
                    .setOnCancelListener { result?.cancel() }
                    .show()
                return true
            }
        }
        web.webViewClient = object : WebViewClient() {
            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                if (request?.isForMainFrame == true) askServer("Server nahi mila. Address check karo")
            }
        }
        web.addJavascriptInterface(Bridge(this, voice), "Android")

        val perms = ArrayList<String>()
        perms.add(Manifest.permission.RECORD_AUDIO)
        perms.add(Manifest.permission.READ_CONTACTS)
        if (Build.VERSION.SDK_INT >= 33) {
            perms.add(Manifest.permission.READ_MEDIA_IMAGES)
            perms.add(Manifest.permission.READ_MEDIA_VIDEO)
            perms.add(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            perms.add(Manifest.permission.READ_EXTERNAL_STORAGE)
            if (Build.VERSION.SDK_INT <= 28) perms.add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        }
        requestPermissions(perms.toTypedArray(), 1)

        val url = prefs.getString("url", "") ?: ""
        if (url.isEmpty()) askServer("Server ka address daalo") else web.loadUrl(url)
    }

    override fun onResume() {
        super.onResume()
        Hosts.active = this
        prefs.edit().putBoolean("sleeping", false).apply()
        if (OverlayService.running) stopService(Intent(this, OverlayService::class.java))
        if (!prefs.getBoolean("status_v4", false)) {
            // naya APK install: permissions reset ho jaati hain, isliye ek baar check dikhao
            window.decorView.postDelayed({
                if (!dialogOpen && !isFinishing) {
                    prefs.edit().putBoolean("status_v4", true).apply()
                    showStatus()
                }
            }, 3500)
        }
        // overlay band hone par app ka mic wapas chalu karo
        js("try{if(typeof micOn!=='undefined'&&micOn)Android.startWake()}catch(e){}")
    }

    override fun onPause() {
        super.onPause()
        startBackgroundListening()
    }

    /** App se bahar (ya screen band) hote hi Sakura background me "Hey Sakura" sunti rahe. */
    private fun startBackgroundListening() {
        if (isFinishing) return
        if (!prefs.getBoolean("always_on", true) || prefs.getBoolean("sleeping", false)) return
        if (!Settings.canDrawOverlays(this)) return
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return
        if (OverlayService.running) return
        if ((prefs.getString("url", "") ?: "").isEmpty()) return
        voice.stopWake()
        try {
            startForegroundService(Intent(this, OverlayService::class.java))
        } catch (e: Exception) { /* background me shuru karne ki ijaazat nahi mili */ }
    }

    /** Master ki apni awaaz se "Hey Sakura" sikhana (door/accent ke hisaab se) */
    private fun startWakeTraining() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "Pehle mic ki permission do", Toast.LENGTH_LONG).show()
            return
        }
        AlertDialog.Builder(this)
            .setTitle("Wake sikhao")
            .setMessage("Shaant jagah par, jitni door se tum aam taur par bologe utni door se.\n\n" +
                "5 baar 'Hey Sakura' bolo. Har baar bolkar 1-2 second ruko. Screen par likha aayega ki kya suna.\n\n" +
                "Pehli baar ho to model utarne me thodi der lag sakti hai (internet ON rakho).")
            .setPositiveButton("Shuru") { _, _ -> voice.trainWake(5) }
            .setNegativeButton("Band", null)
            .show()
    }

    private class Row(val name: String, val ok: Boolean, val fix: () -> Unit)

    /** Kya-kya ON hai. Naya APK install karne par permissions reset hoti hain, yahan ek nazar me dikhta hai. */
    private fun showStatus() {
        val pkgUri = Uri.parse("package:$packageName")
        val power = getSystemService(POWER_SERVICE) as PowerManager
        val listeners = Settings.Secure.getString(contentResolver, "enabled_notification_listeners") ?: ""
        val rows = listOf(
            Row("Mic permission", checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, pkgUri))
            },
            Row("Dusri apps ke upar dikhna (Overlay) - iske bina Sakura screen par nahi aati", Settings.canDrawOverlays(this)) {
                startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, pkgUri))
            },
            Row("Haath / screen control (Accessibility)", AgentService.instance != null) {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            },
            Row("Battery optimization hati (hamesha sunne ke liye)", power.isIgnoringBatteryOptimizations(packageName)) {
                startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, pkgUri))
            },
            Row("WhatsApp notification access", listeners.contains(packageName)) {
                startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            },
            Row("हिंदी वेक-वर्ड मॉडल डाउनलोड हुआ", ModelStore.isReady(this)) {
                Toast.makeText(this, "Mic ON hote hi internet se apne aap utarta hai. Internet ON rakho", Toast.LENGTH_LONG).show()
                voice.startWake()
            },
            Row("Server ka address set hai", (prefs.getString("url", "") ?: "").isNotEmpty()) {
                askServer("Server ka address")
            }
        )
        val msg = rows.joinToString("\n\n") { (if (it.ok) "✅ " else "❌ ") + it.name }
        val first = rows.firstOrNull { !it.ok }
        val b = AlertDialog.Builder(this)
            .setTitle(if (first == null) "Sab ON hai ✅" else "Sakura status")
            .setMessage(msg + if (first != null) "\n\nAccessibility ON na ho paye (grey ho): Settings > Apps > Sakura > teen dot > 'Allow restricted settings', phir dobara." else "")
            .setNegativeButton("Band", null)
        if (first != null) b.setPositiveButton("Pehla theek karo") { _, _ -> first.fix() }
        b.show()
    }

    private fun askServer(title: String) {
        if (dialogOpen) return
        dialogOpen = true
        val et = EditText(this)
        et.hint = "https://sakura-xxxx.onrender.com"
        et.setText(prefs.getString("url", ""))
        AlertDialog.Builder(this)
            .setTitle(title)
            .setView(et)
            .setCancelable(false)
            .setPositiveButton("Save") { _, _ ->
                dialogOpen = false
                var u = et.text.toString().trim()
                if (u.isNotEmpty()) {
                    if (!u.startsWith("http")) u = "http://$u"
                    prefs.edit().putString("url", u).apply()
                    web.loadUrl(u)
                }
            }
            .show()
    }

    private fun askKey() {
        val et = EditText(this)
        et.hint = "Picovoice AccessKey"
        et.setText(prefs.getString("pv_key", ""))
        AlertDialog.Builder(this)
            .setTitle("Picovoice AccessKey")
            .setView(et)
            .setPositiveButton("Save") { _, _ ->
                prefs.edit().putString("pv_key", et.text.toString().trim()).apply()
                Toast.makeText(this, "Save ho gaya. Page me mic button dobara dabao", Toast.LENGTH_LONG).show()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    override fun setup() {
        val items = arrayOf(
            "WhatsApp notification access (zaroori)",
            "All files access (files dhoondne ke liye)",
            "Dusri apps ke upar dikhne ki permission (Overlay)",
            "Screen par aao (Overlay mode shuru)",
            "Server ka address badlo",
            "Haath / screen control (Accessibility) ON karo",
            "Battery optimization hatao (hamesha sunne ke liye zaroori)",
            "Wake test ON/OFF (Hindi me jo sunai de wo dikhao)",
            "Background me hamesha sunna ON/OFF",
            "Status check: kya-kya ON hai, kya baaki hai",
            "Wake sikhao: 'साकुरा' 5 baar bolo (aur sahi sunegi)",
            "Sikha hua wake mitao"
        )
        AlertDialog.Builder(this)
            .setTitle("Phone setup")
            .setItems(items) { _, which ->
                when (which) {
                    0 -> startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                    1 -> if (Build.VERSION.SDK_INT >= 30) {
                        startActivity(
                            Intent(
                                Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                                Uri.parse("package:$packageName")
                            )
                        )
                    }
                    2 -> startActivity(
                        Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
                    )
                    3 -> openOverlay()
                    4 -> askServer("Server ka address")
                    5 -> startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                    6 -> startActivity(
                        Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName"))
                    )
                    7 -> {
                        val v = !prefs.getBoolean("wake_debug", false)
                        prefs.edit().putBoolean("wake_debug", v).apply()
                        Toast.makeText(this, if (v) "Wake test ON: Hindi me jo sunai dega wo likha aayega" else "Wake test OFF", Toast.LENGTH_LONG).show()
                    }
                    8 -> {
                        val v = !prefs.getBoolean("always_on", true)
                        prefs.edit().putBoolean("always_on", v).apply()
                        Toast.makeText(this, if (v) "Background me sunna ON" else "Background me sunna OFF", Toast.LENGTH_LONG).show()
                    }
                    9 -> showStatus()
                    10 -> startWakeTraining()
                    11 -> {
                        voice.clearWakeTraining()
                        Toast.makeText(this, "Sikha hua wake mita diya", Toast.LENGTH_LONG).show()
                    }
                }
            }
            .show()
    }

    /** App kholne se pehle girl ko overlay me bhej do, taaki wo us app ke upar bani rahe aur sunti rahe. */
    override fun beforeLaunch(): Boolean {
        if (!Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Screen par aane ke liye Phone setup me Overlay permission do", Toast.LENGTH_LONG).show()
            return false
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return false
        voice.stopWake()
        startForegroundService(Intent(this, OverlayService::class.java).putExtra("show", true))
        return true
    }

    override fun openOverlay() {
        if (!Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "'Dusri apps ke upar dikhao' permission ON karo, phir dobara dabao", Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
            return
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "Pehle Mic ki permission do", Toast.LENGTH_LONG).show()
            return
        }
        voice.stopWake()
        startForegroundService(Intent(this, OverlayService::class.java))
        moveTaskToBack(true)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (requestCode == 77) {
            val r = if (resultCode == RESULT_OK && data != null)
                WebChromeClient.FileChooserParams.parseResult(resultCode, data) else null
            fileCb?.onReceiveValue(r)
            fileCb = null
            return
        }
        super.onActivityResult(requestCode, resultCode, data)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        voice.stopWake()
        voice.release()
        if (Hosts.active === this) Hosts.active = null
        super.onDestroy()
    }
}
