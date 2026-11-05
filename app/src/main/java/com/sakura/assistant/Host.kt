package com.sakura.assistant

import android.content.Context

/** Page (WebView) ko chalane wali jagah: MainActivity ya OverlayService. */
interface Host {
    val ctx: Context
    fun js(code: String)
    fun confirm(title: String, msg: String, yes: () -> Unit, no: () -> Unit)
    fun setup() {}
    fun overlayShow(show: Boolean) {}
    fun openOverlay() {}
    fun closeOverlay() {}

    /** Haath kaam kar rahe hain: overlay ki girl touch se hat jaye (taaki tap uske neeche na atke). */
    fun agentBusy(b: Boolean) {}

    /** Screenshot ke waqt Sakura ki chhoti window chhup jaye (chart na dhake) */
    fun ghost(on: Boolean) {}

    /** Dusri app kholne se pehle. true = girl overlay me chali gayi (screen par bani rahegi). */
    fun beforeLaunch(): Boolean = false
}

object Hosts {
    @Volatile
    var active: Host? = null
}
