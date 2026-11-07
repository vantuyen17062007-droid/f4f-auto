package com.f4f.autorunner.util

import android.content.Context

/** Danh sách package của TikTok / Instagram mà app được phép điều khiển. */
object AppPackages {
    const val INSTAGRAM = "com.instagram.android"

    // Bản quốc tế (musically) và bản khu vực châu Á (trill)
    val TIKTOK = listOf("com.zhiliaoapp.musically", "com.ss.android.ugc.trill")

    val ALL: Set<String> = TIKTOK.toSet() + INSTAGRAM

    /** Trả về package đã cài đặt của nền tảng, hoặc null nếu chưa cài. */
    fun resolve(context: Context, platform: String): String? {
        val candidates = if (platform == "instagram") listOf(INSTAGRAM) else TIKTOK
        val pm = context.packageManager
        return candidates.firstOrNull {
            try {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(it, 0)
                true
            } catch (_: Exception) {
                false
            }
        }
    }
}
