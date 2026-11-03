package com.f4f.autorunner.service

import android.annotation.SuppressLint
import android.app.Service
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.view.*
import android.widget.TextView
import com.f4f.autorunner.R
import com.f4f.autorunner.controller.RunnerController
import com.f4f.autorunner.controller.RunnerState
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.collectLatest

class FloatingWidgetService : Service() {

    private var windowManager: WindowManager? = null
    private var floatingView: View? = null
    private val serviceScope = CoroutineScope(Dispatchers.Main + Job())
    private var startTimeMs: Long = 0

    override fun onBind(intent: Intent?): IBinder? = null

    @SuppressLint("ClickableViewAccessibility")
    override fun onCreate() {
        super.onCreate()

        floatingView = LayoutInflater.from(this).inflate(R.layout.layout_floating_widget, null)

        val layoutFlag = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutFlag,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 40
            y = 200
        }

        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        windowManager?.addView(floatingView, params)

        startTimeMs = System.currentTimeMillis()

        // Drag handler via drag_handle_pill
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f

        val dragPill = floatingView?.findViewById<View>(R.id.drag_handle_pill) ?: floatingView
        dragPill?.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialX = params.x
                    initialY = params.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    params.x = initialX + (event.rawX - initialTouchX).toInt()
                    params.y = initialY + (event.rawY - initialTouchY).toInt()
                    try {
                        windowManager?.updateViewLayout(floatingView, params)
                    } catch (_: Exception) {}
                    true
                }
                else -> false
            }
        }

        val btnResume = floatingView?.findViewById<View>(R.id.btn_floating_resume)
        val btnPause = floatingView?.findViewById<View>(R.id.btn_floating_pause)
        val btnStop = floatingView?.findViewById<View>(R.id.btn_floating_stop)
        val btnMinimize = floatingView?.findViewById<View>(R.id.btn_floating_minimize)
        val btnClose = floatingView?.findViewById<View>(R.id.btn_floating_close)

        val tvStatusTime = floatingView?.findViewById<TextView>(R.id.tv_floating_status_time)
        val dotIndicator = floatingView?.findViewById<TextView>(R.id.dot_floating_indicator)
        val tvSuccess = floatingView?.findViewById<TextView>(R.id.tv_floating_success)
        val tvFailed = floatingView?.findViewById<TextView>(R.id.tv_floating_failed)
        val boxButtons = floatingView?.findViewById<View>(R.id.box_floating_buttons)

        btnResume?.setOnClickListener {
            RunnerController.resume()
        }

        btnPause?.setOnClickListener {
            RunnerController.pause()
        }

        btnStop?.setOnClickListener {
            RunnerController.stop()
            stopSelf()
        }

        btnMinimize?.setOnClickListener {
            if (boxButtons?.visibility == View.VISIBLE) {
                boxButtons.visibility = View.GONE
            } else {
                boxButtons?.visibility = View.VISIBLE
            }
        }

        btnClose?.setOnClickListener {
            stopSelf()
        }

        // Lắng nghe trạng thái
        serviceScope.launch {
            RunnerController.state.collectLatest { state ->
                when (state) {
                    RunnerState.RUNNING -> {
                        dotIndicator?.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#10B981"))
                    }
                    RunnerState.PAUSED -> {
                        dotIndicator?.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#F59E0B"))
                    }
                    RunnerState.STOPPED, RunnerState.IDLE -> {
                        dotIndicator?.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#EF4444"))
                        stopSelf()
                    }
                }
            }
        }

        // Lắng nghe thống kê
        serviceScope.launch {
            RunnerController.stats.collectLatest { stats ->
                val completed = stats.followed + stats.liked
                val failed = stats.skipped + stats.errors
                tvSuccess?.text = "$completed Thành công"
                tvFailed?.text = "$failed Thất bại"
            }
        }

        // Cập nhật bộ đếm thời gian mỗi giây
        serviceScope.launch {
            while (isActive) {
                val elapsedSec = (System.currentTimeMillis() - startTimeMs) / 1000
                val hours = elapsedSec / 3600
                val mins = (elapsedSec % 3600) / 60
                val stateName = if (RunnerController.isPaused) "Tạm dừng" else "Đang chạy"
                tvStatusTime?.text = "$stateName • ${hours}h ${mins}m"
                delay(1000)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        if (floatingView != null) {
            try {
                windowManager?.removeView(floatingView)
            } catch (_: Exception) {}
        }
    }
}
