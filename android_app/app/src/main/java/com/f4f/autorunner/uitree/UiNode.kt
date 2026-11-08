package com.f4f.autorunner.uitree

import android.graphics.Rect

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
