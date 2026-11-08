package com.f4f.autorunner.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.f4f.autorunner.uitree.UiNode
import com.f4f.autorunner.uitree.UiXmlParser
import com.f4f.autorunner.util.AppPackages

/**
 * Service chỉ làm 3 việc "thô": đọc cây giao diện (snapshotNodes), chạm tọa độ (tapAt / doubleTapAt)
 * và vuốt feed. Việc nhận diện Follow/Like dùng chung UiXmlParser với chế độ ADB để hai chế độ
 * cho kết quả giống nhau, và AutoJobEngine sẽ xác minh kết quả sau khi bấm.
 */
class F4FAccessibilityService : AccessibilityService() {

    companion object {
        var instance: F4FAccessibilityService? = null
            private set

        @Volatile
        var automationActive: Boolean = false

        fun isRunning(): Boolean = instance != null
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (!automationActive) return
        if (event?.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return

        // Chỉ xử lý popup khi cửa sổ thuộc TikTok / Instagram, không đụng tới app/hệ thống khác
        val pkg = event.packageName?.toString() ?: return
        if (pkg in AppPackages.ALL) dismissPopups()
    }

    override fun onInterrupt() {}

    /**
     * Chụp cây giao diện của cửa sổ đang hiển thị thành danh sách UiNode.
     * Trả về rỗng nếu cửa sổ hiện tại không phải TikTok / Instagram.
     */
    fun snapshotNodes(): List<UiNode> {
        val root = rootInActiveWindow ?: return emptyList()
        val pkg = root.packageName?.toString().orEmpty()
        if (pkg !in AppPackages.ALL) return emptyList()

        val out = ArrayList<UiNode>()

        fun walk(node: AccessibilityNodeInfo?, depth: Int) {
            if (node == null || depth > 40) return
            val rect = Rect()
            node.getBoundsInScreen(rect)
            out.add(
                UiNode(
                    text = (node.text ?: "").toString().trim(),
                    desc = (node.contentDescription ?: "").toString().trim(),
                    resId = node.viewIdResourceName.orEmpty(),
                    className = node.className?.toString().orEmpty(),
                    packageName = pkg,
                    bounds = rect,
                    clickable = node.isClickable,
                    selected = node.isSelected
                )
            )
            for (i in 0 until node.childCount) {
                walk(node.getChild(i), depth + 1)
            }
        }

        walk(root, 0)
        return out
    }

    /** Chạm 1 lần tại tọa độ màn hình. */
    fun tapAt(x: Int, y: Int, durationMs: Long = 50): Boolean {
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, durationMs))
            .build()
        return dispatchGesture(gesture, null, null)
    }

    /** Chạm 2 lần liên tiếp (double-tap thả tim). */
    fun doubleTapAt(x: Int, y: Int): Boolean {
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 50))
            .addStroke(GestureDescription.StrokeDescription(path, 170, 50))
            .build()
        return dispatchGesture(gesture, null, null)
    }

    /** Tự động đóng popup cấp quyền / đồng bộ danh bạ (chỉ trong TikTok / Instagram). */
    fun dismissPopups(): Boolean {
        if (!automationActive) return false
        val pt = UiXmlParser.findPopupDismissButton(snapshotNodes()) ?: return false
        return tapAt(pt.x, pt.y)
    }

    /** Mô phỏng người thật vuốt lướt feed. */
    fun simulateHumanBrowse(times: Int, onComplete: () -> Unit) {
        if (times <= 0 || !automationActive) {
            onComplete()
            return
        }

        val displayMetrics = resources.displayMetrics
        val screenWidth = displayMetrics.widthPixels
        val screenHeight = displayMetrics.heightPixels

        val startX = (screenWidth / 2).toFloat()
        val startY = (screenHeight * 0.75f)
        val endY = (screenHeight * 0.25f)
        val handler = Handler(Looper.getMainLooper())

        fun doSwipe(remaining: Int) {
            if (remaining <= 0 || !automationActive) {
                onComplete()
                return
            }

            val path = Path().apply {
                moveTo(startX, startY)
                lineTo(startX, endY)
            }

            val gesture = GestureDescription.Builder()
                .addStroke(GestureDescription.StrokeDescription(path, 0, 280))
                .build()

            val dispatched = dispatchGesture(gesture, object : GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) {
                    handler.postDelayed({ doSwipe(remaining - 1) }, 2500L)
                }

                override fun onCancelled(gestureDescription: GestureDescription?) {
                    handler.postDelayed({ doSwipe(remaining - 1) }, 1000L)
                }
            }, null)

            if (!dispatched) onComplete()
        }

        doSwipe(times)
    }
}
