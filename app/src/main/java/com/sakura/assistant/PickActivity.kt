package com.sakura.assistant

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle

/**
 * Master se photo chunwane ke liye chhoti transparent screen (overlay se bhi chalti hai).
 * Natija PickActivity.cb se wapas jaata hai: Uri ya null (Master ne back dabaya).
 */
class PickActivity : Activity() {

    companion object {
        @Volatile
        var cb: ((Uri?) -> Unit)? = null
    }

    private var delivered = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Android 13+ ka photo-picker (neeche se khulne wali photo list); na ho to purana document picker
        var started = false
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            try {
                startActivityForResult(Intent(android.provider.MediaStore.ACTION_PICK_IMAGES), 91)
                started = true
            } catch (e: Exception) { /* neeche document picker */ }
        }
        if (!started) {
            val i = Intent(Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("image/*")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            try {
                startActivityForResult(i, 91)
            } catch (e: Exception) {
                deliver(null)
                finish()
            }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val u = if (requestCode == 91 && resultCode == RESULT_OK) data?.data else null
        if (u != null) {
            try {
                contentResolver.takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            } catch (e: Exception) { /* sirf is session ke liye bhi chalega */ }
        }
        deliver(u)
        finish()
    }

    private fun deliver(u: Uri?) {
        if (delivered) return
        delivered = true
        val f = cb
        cb = null
        f?.invoke(u)
    }

    override fun onDestroy() {
        deliver(null)
        super.onDestroy()
    }
}
