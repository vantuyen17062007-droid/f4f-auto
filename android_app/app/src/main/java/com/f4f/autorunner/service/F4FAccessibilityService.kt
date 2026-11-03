package com.f4f.autorunner.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

class F4FAccessibilityService : AccessibilityService() {

    companion object {
        var instance: F4FAccessibilityService? = null
            private set

        fun isRunning(): Boolean = instance != null

        private val FOLLOW_LABELS = setOf(
            "follow", "theo dõi", "theo doi", "follow lại", "follow lai",
            "follow back", "theo dõi lại", "theo doi lai"
        )

        private val FOLLOWED_LABELS = setOf(
            "đã follow", "da follow", "đang follow", "dang follow",
            "following", "đã theo dõi", "da theo doi", "đang theo dõi", "dang theo doi",
            "bạn bè", "ban be", "friends", "followed"
        )

        private val REQUESTED_LABELS = setOf(
            "đã yêu cầu", "da yeu cau", "requested", "yêu cầu đã gửi", "request sent"
        )

        private val POPUP_DISMISS_LABELS = setOf(
            "để sau", "de sau", "không phải bây giờ", "khong phai bay gio", "lúc khác", "luc khac",
            "hủy", "huy", "từ chối", "tu choi", "không cho phép", "khong cho phep",
            "bỏ qua", "bo qua", "đóng", "dong", "not now", "cancel", "dismiss",
            "don't allow", "later", "never", "remind me later", "skip"
        )
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
        // Tự động kiểm tra và đóng popup phiền toái khi chuyển màn hình
        if (event?.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            dismissPopups()
        }
    }

    override fun onInterrupt() {}

    /**
     * Bấm nút Follow trên TikTok hoặc Instagram.
     * Trả về: "followed", "already", "requested", hoặc "failed"
     */
    fun performFollow(): String {
        val root = rootInActiveWindow ?: return "failed"

        // 1. Kiểm tra Instagram Follow Button ID đặc trưng
        val igButtons = root.findAccessibilityNodeInfosByViewId("com.instagram.android:id/profile_header_follow_button")
        if (igButtons.isNotEmpty()) {
            val btn = igButtons[0]
            val text = (btn.text ?: btn.contentDescription ?: "").toString().trim().lowercase()
            if (FOLLOWED_LABELS.any { text.contains(it) }) return "already"
            if (REQUESTED_LABELS.any { text.contains(it) }) return "requested"

            if (clickNodeOrCoordinates(btn)) return "followed"
        }

        // 2. Quét toàn bộ cây giao diện tìm nhãn Follow
        val allNodes = ArrayList<AccessibilityNodeInfo>()
        collectAllNodes(root, allNodes)

        for (node in allNodes) {
            val text = (node.text ?: node.contentDescription ?: "").toString().trim().lowercase()
            if (text.isEmpty()) continue

            if (FOLLOWED_LABELS.any { label -> text == label || text.startsWith("$label ") }) {
                return "already"
            }
            if (REQUESTED_LABELS.any { label -> text == label || text.startsWith("$label ") }) {
                return "requested"
            }
            if (FOLLOW_LABELS.any { label -> text == label || text.startsWith("$label ") }) {
                if (clickNodeOrCoordinates(node)) {
                    return "followed"
                }
            }
        }

        return "failed"
    }

    /**
     * Bấm Like video trên TikTok.
     * Trả về: "liked", "already", hoặc "failed"
     */
    fun performLikeTikTok(): String {
        val root = rootInActiveWindow ?: return "failed"
        val allNodes = ArrayList<AccessibilityNodeInfo>()
        collectAllNodes(root, allNodes)

        for (node in allNodes) {
            val desc = (node.contentDescription ?: node.text ?: "").toString().trim().lowercase()
            val resId = node.viewIdResourceName.orEmpty()

            if (desc.contains("đã thích") || desc.contains("da thich") || desc.contains("bỏ thích") || desc.contains("bo thich") ||
                ((resId.endsWith(":id/g86") || resId.endsWith(":id/g8m")) && node.isSelected)
            ) {
                return "already"
            }

            if (desc == "thích" || desc == "thich" || desc == "thích video" || desc.contains("lượt thích") ||
                desc == "like" || desc == "like video" ||
                resId.endsWith(":id/g8m") || resId.endsWith(":id/g86")
            ) {
                if (clickNodeOrCoordinates(node)) {
                    return "liked"
                }
            }
        }
        return "failed"
    }

    /**
     * Tự động đóng các popup cấp quyền / đồng bộ danh bạ.
     */
    fun dismissPopups(): Boolean {
        val root = rootInActiveWindow ?: return false
        val allNodes = ArrayList<AccessibilityNodeInfo>()
        collectAllNodes(root, allNodes)

        for (node in allNodes) {
            val text = (node.text ?: node.contentDescription ?: "").toString().trim().lowercase()
            if (POPUP_DISMISS_LABELS.contains(text)) {
                clickNodeOrCoordinates(node)
                return true
            }
        }
        return false
    }

    /**
     * Mô phỏng người thật vuốt lướt feed chống ban.
     */
    fun simulateHumanBrowse(times: Int, onComplete: () -> Unit) {
        if (times <= 0) {
            onComplete()
            return
        }

        val displayMetrics = resources.displayMetrics
        val screenWidth = displayMetrics.widthPixels
        val screenHeight = displayMetrics.heightPixels

        val startX = (screenWidth / 2).toFloat()
        val startY = (screenHeight * 0.75f)
        val endY = (screenHeight * 0.25f)

        fun doSwipe(remaining: Int) {
            if (remaining <= 0) {
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

            dispatchGesture(gesture, object : GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) {
                    Handler(Looper.getMainLooper()).postDelayed({
                        doSwipe(remaining - 1)
                    }, 2500L)
                }
            }, null)
        }

        doSwipe(times)
    }

    private fun clickNodeOrCoordinates(node: AccessibilityNodeInfo): Boolean {
        if (node.isClickable && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
            return true
        }

        // Nếu node không clickable, tìm cha gần nhất
        var parent = node.parent
        while (parent != null) {
            if (parent.isClickable && parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                return true
            }
            parent = parent.parent
        }

        // Fallback: Click trực tiếp vào tọa độ trung tâm bằng Gesture
        val rect = Rect()
        node.getBoundsInScreen(rect)
        if (rect.width() > 0 && rect.height() > 0) {
            val clickPath = Path().apply {
                moveTo(rect.centerX().toFloat(), rect.centerY().toFloat())
            }
            val gesture = GestureDescription.Builder()
                .addStroke(GestureDescription.StrokeDescription(clickPath, 0, 50))
                .build()
            dispatchGesture(gesture, null, null)
            return true
        }

        return false
    }

    private fun collectAllNodes(node: AccessibilityNodeInfo?, list: MutableList<AccessibilityNodeInfo>) {
        if (node == null) return
        list.add(node)
        for (i in 0 until node.childCount) {
            collectAllNodes(node.getChild(i), list)
        }
    }
}
