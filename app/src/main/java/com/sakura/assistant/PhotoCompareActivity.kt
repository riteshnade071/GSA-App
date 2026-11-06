package com.sakura.assistant

import android.app.Activity
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

/** Simple offline before/after viewer; images stay on-device. */
class PhotoCompareActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val before = intent.getStringExtra("before")
        val after = intent.getStringExtra("after")
        if (before.isNullOrBlank() || after.isNullOrBlank()) {
            Toast.makeText(this, "Dono photos nahi mili", Toast.LENGTH_LONG).show()
            finish(); return
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(16), dp(12), dp(12))
            setBackgroundColor(0xFF101018.toInt())
        }
        val title = TextView(this).apply {
            text = "Sakura • Before / After"
            textSize = 20f; setTextColor(0xFFFFFFFF.toInt()); gravity = Gravity.CENTER
        }
        root.addView(title, LinearLayout.LayoutParams(-1, dp(48)))
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        root.addView(row, LinearLayout.LayoutParams(-1, 0, 1f))
        addPhoto(row, "BEFORE", Uri.parse(before))
        addPhoto(row, "AFTER", Uri.parse(after))
        val hint = TextView(this).apply {
            text = "Side-by-side comparison • Original aur edited files Gallery mein alag-alag rahengi"
            textSize = 12f; setTextColor(0xFFCCCCDD.toInt()); gravity = Gravity.CENTER
        }
        root.addView(hint, LinearLayout.LayoutParams(-1, dp(48)))
        setContentView(root)
    }

    private fun addPhoto(parent: LinearLayout, label: String, uri: Uri) {
        val column = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(4), dp(8), dp(4), dp(8)) }
        val caption = TextView(this).apply {
            text = label; textSize = 14f; gravity = Gravity.CENTER
            setTextColor(0xFFFFFFFF.toInt())
        }
        column.addView(caption, LinearLayout.LayoutParams(-1, dp(36)))
        val image = ImageView(this).apply { scaleType = ImageView.ScaleType.FIT_CENTER }
        try {
            image.setImageBitmap(loadSampledBitmap(uri))
        } catch (_: Exception) { }
        column.addView(image, LinearLayout.LayoutParams(-1, 0, 1f))
        parent.addView(column, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f))
    }


    /** Decode large camera images at a safe preview size to avoid OOM on mid-range phones. */
    private fun loadSampledBitmap(uri: Uri): android.graphics.Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        var sample = 1
        while (bounds.outWidth / sample > 1400 || bounds.outHeight / sample > 1800) sample *= 2
        val opts = BitmapFactory.Options().apply { inSampleSize = sample; inPreferredConfig = android.graphics.Bitmap.Config.RGB_565 }
        return contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, opts) }
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}
