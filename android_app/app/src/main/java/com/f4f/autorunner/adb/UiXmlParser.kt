package com.f4f.autorunner.adb

import android.graphics.Point
import android.graphics.Rect
import org.xmlpull.v1.XmlPullParser
import org.xmlpull.v1.XmlPullParserFactory
import java.io.StringReader
import java.util.regex.Pattern

data class UiNode(
    val text: String = "",
    val desc: String = "",
    val resId: String = "",
    val className: String = "",
    val packageName: String = "",
    val bounds: Rect = Rect(),
    val clickable: Boolean = false,
    val selected: Boolean = false
) {
    val centerX: Int get() = bounds.centerX()
    val centerY: Int get() = bounds.centerY()
    val width: Int get() = bounds.width()
    val height: Int get() = bounds.height()
}

object UiXmlParser {

    private val BOUNDS_PATTERN = Pattern.compile("\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]")

    val FOLLOW_LABELS = setOf(
        "follow", "theo dõi", "theo doi", "follow lại", "follow lai",
        "follow back", "theo dõi lại", "theo doi lai"
    )

    val FOLLOWED_LABELS = setOf(
        "đã follow", "da follow", "đang follow", "dang follow",
        "following", "đã theo dõi", "da theo doi", "đang theo dõi", "dang theo doi",
        "bạn bè", "ban be", "friends", "followed"
    )

    val REQUESTED_LABELS = setOf(
        "đã yêu cầu", "da yeu cau", "requested", "yêu cầu đã gửi", "request sent", "đã gửi yêu cầu", "da gui yeu cau"
    )

    val MESSAGE_LABELS = setOf(
        "nhắn tin", "nhan tin", "tin nhắn", "tin nhan", "message", "messages", "gửi tin nhắn", "gui tin nhan"
    )

    private val UNLIKE_LABELS = setOf(
        "bỏ thích", "bo thich", "đã thích", "da thich", "unlike", "liked"
    )

    private val LIKE_LABELS = setOf(
        "thích", "thich", "like", "thích video", "like video"
    )

    private val POPUP_DISMISS_LABELS = setOf(
        "để sau", "de sau", "không phải bây giờ", "khong phai bay gio", "lúc khác", "luc khac",
        "hủy", "huy", "từ chối", "tu choi", "không cho phép", "khong cho phep",
        "bỏ qua", "bo qua", "đóng", "dong", "not now", "cancel", "dismiss",
        "don't allow", "later", "never", "remind me later", "skip"
    )

    fun parseNodes(xmlContent: String): List<UiNode> {
        val nodes = mutableListOf<UiNode>()
        if (xmlContent.isBlank()) return nodes

        try {
            val factory = XmlPullParserFactory.newInstance()
            val parser = factory.newPullParser()
            parser.setInput(StringReader(xmlContent))

            var eventType = parser.eventType
            while (eventType != XmlPullParser.END_DOCUMENT) {
                if (eventType == XmlPullParser.START_TAG && parser.name == "node") {
                    val text = parser.getAttributeValue(null, "text") ?: ""
                    val desc = parser.getAttributeValue(null, "content-desc") ?: ""
                    val resId = parser.getAttributeValue(null, "resource-id") ?: ""
                    val className = parser.getAttributeValue(null, "class") ?: ""
                    val pkg = parser.getAttributeValue(null, "package") ?: ""
                    val boundsStr = parser.getAttributeValue(null, "bounds") ?: ""
                    val clickable = parser.getAttributeValue(null, "clickable")?.toBoolean() ?: false
                    val selected = parser.getAttributeValue(null, "selected")?.toBoolean() ?: false

                    val rect = parseBounds(boundsStr)
                    nodes.add(
                        UiNode(
                            text = text.trim(),
                            desc = desc.trim(),
                            resId = resId.trim(),
                            className = className.trim(),
                            packageName = pkg.trim(),
                            bounds = rect,
                            clickable = clickable,
                            selected = selected
                        )
                    )
                }
                eventType = parser.next()
            }
        } catch (_: Exception) {}

        return nodes
    }

    private fun parseBounds(boundsStr: String): Rect {
        val matcher = BOUNDS_PATTERN.matcher(boundsStr)
        if (matcher.find()) {
            val left = matcher.group(1)?.toIntOrNull() ?: 0
            val top = matcher.group(2)?.toIntOrNull() ?: 0
            val right = matcher.group(3)?.toIntOrNull() ?: 0
            val bottom = matcher.group(4)?.toIntOrNull() ?: 0
            return Rect(left, top, right, bottom)
        }
        return Rect()
    }

    /**
     * Tìm trạng thái Follow và tọa độ nút bấm:
     * Trả về Pair(state: "followed" | "already" | "requested" | "failed", Point(cx, cy)?)
     */
    fun findFollowButton(nodes: List<UiNode>, requireClickable: Boolean = false): Pair<String, Point?> {
        // 1. Kiểm tra nút Instagram đặc trưng
        for (node in nodes) {
            if (node.resId.contains("profile_header_follow_button")) {
                val label = (node.text.ifEmpty { node.desc }).lowercase()
                val pt = Point(node.centerX, node.centerY)
                if (FOLLOWED_LABELS.any { label.contains(it) }) return Pair("already", pt)
                if (REQUESTED_LABELS.any { label.contains(it) }) return Pair("requested", pt)
                if (FOLLOW_LABELS.any { label.contains(it) }) return Pair("followed", pt)
            }
        }

        // 2. Tìm Anchor "Nhắn tin" trên TikTok Profile
        var messageAnchorY: Int? = null
        for (node in nodes) {
            val label = (node.text.ifEmpty { node.desc }).lowercase()
            if (MESSAGE_LABELS.contains(label) && node.height >= 50) {
                messageAnchorY = node.centerY
                break
            }
        }

        // 3. Lọc các nút ứng viên (Bỏ qua các nhãn thống kê như 'Đã follow: 2 người', 'Follower: 96M')
        val candidates = mutableListOf<Pair<String, UiNode>>()
        for (node in nodes) {
            // Nút bấm thực tế trên TikTok luôn có chiều cao >= 50px và chiều rộng >= 60px
            if (node.height < 50 || node.width < 60) continue

            // Chế độ Trợ Năng: chỉ nhận nút thật sự bấm được, tránh nhầm nhãn thống kê "Following"
            if (requireClickable && !(node.clickable || node.className.contains("Button", ignoreCase = true))) continue

            // Bỏ qua các textview nhãn số liệu thống kê follower/following
            if (node.resId.endsWith(":id/t9q") || node.resId.endsWith(":id/t9r")) continue

            val label = (node.text.ifEmpty { node.desc }).lowercase()
            if (label.isEmpty()) continue

            if (FOLLOWED_LABELS.any { label == it || label.startsWith("$it ") }) {
                candidates.add(Pair("already", node))
            } else if (REQUESTED_LABELS.any { label == it || label.startsWith("$it ") }) {
                candidates.add(Pair("requested", node))
            } else if (FOLLOW_LABELS.any { label == it || label.startsWith("$it ") }) {
                candidates.add(Pair("followed", node))
            }
        }

        // Nếu có Anchor "Nhắn tin", ưu tiên nút nằm cùng hàng ngang
        if (messageAnchorY != null) {
            for ((state, node) in candidates) {
                if (kotlin.math.abs(node.centerY - messageAnchorY) <= 80) {
                    return Pair(state, Point(node.centerX, node.centerY))
                }
            }
        }

        // Nếu không có anchor (hoặc profile không cho nhắn tin), lấy ứng viên đầu tiên hợp lệ
        if (candidates.isNotEmpty()) {
            val (state, node) = candidates.first()
            return Pair(state, Point(node.centerX, node.centerY))
        }

        return Pair("failed", null)
    }

    /**
     * Nhận diện trạng thái Like video:
     * Trả về Pair(state: "already" | "liked" | "failed", Point(cx, cy)?)
     */
    fun findLikeState(nodes: List<UiNode>): Pair<String, Point?> {
        var likePos: Point? = null
        var isAlreadyLiked = false

        for (node in nodes) {
            val desc = (node.desc.ifEmpty { node.text }).lowercase()
            val resId = node.resId.lowercase()

            val isUnlike = UNLIKE_LABELS.any { desc.contains(it) } ||
                    ((resId.endsWith(":id/g86") || resId.endsWith(":id/g8m")) && node.selected)

            if (isUnlike) {
                isAlreadyLiked = true
                likePos = Point(node.centerX, node.centerY)
            }

            val isLikeButton = LIKE_LABELS.any { desc == it } ||
                    (resId.endsWith(":id/g86") || resId.endsWith(":id/g8m"))

            if (isLikeButton && likePos == null) {
                likePos = Point(node.centerX, node.centerY)
            }
        }

        return when {
            isAlreadyLiked -> Pair("already", likePos)
            likePos != null -> Pair("liked", likePos)
            else -> Pair("failed", null)
        }
    }

    /**
     * Tìm nút đóng Popup cấp quyền hoặc đề xuất
     */
    fun findPopupDismissButton(nodes: List<UiNode>): Point? {
        for (node in nodes) {
            val label = (node.text.ifEmpty { node.desc }).lowercase()
            if (node.width > 0 && node.height > 0 && POPUP_DISMISS_LABELS.contains(label)) {
                return Point(node.centerX, node.centerY)
            }
        }
        return null
    }
}
