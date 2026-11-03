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
import android.widget.ImageButton
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
            y = 220
        }

        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        windowManager?.addView(floatingView, params)

        // Drag handler
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f

        val dragArea = floatingView?.findViewById<View>(R.id.drag_area) ?: floatingView
        dragArea?.setOnTouchListener { _, event ->
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

        val btnPause = floatingView?.findViewById<ImageButton>(R.id.btn_floating_pause)
        val btnStop = floatingView?.findViewById<ImageButton>(R.id.btn_floating_stop)
        val tvStatus = floatingView?.findViewById<TextView>(R.id.tv_floating_status)
        val dotStatus = floatingView?.findViewById<TextView>(R.id.dot_floating_status)

        btnPause?.setOnClickListener {
            if (RunnerController.isRunning) {
                RunnerController.pause()
            } else if (RunnerController.isPaused) {
                RunnerController.resume()
            }
        }

        btnStop?.setOnClickListener {
            RunnerController.stop()
            stopSelf()
        }

        // Lắng nghe trạng thái từ RunnerController
        serviceScope.launch {
            RunnerController.state.collectLatest { state ->
                when (state) {
                    RunnerState.RUNNING -> {
                        dotStatus?.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#10B981"))
                        btnPause?.setImageResource(R.drawable.ic_pause)
                    }
                    RunnerState.PAUSED -> {
                        dotStatus?.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#F59E0B"))
                        btnPause?.setImageResource(R.drawable.ic_play)
                    }
                    RunnerState.STOPPED, RunnerState.IDLE -> {
                        dotStatus?.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#EF4444"))
                        stopSelf()
                    }
                }
            }
        }

        // Lắng nghe số liệu kiếm coin
        serviceScope.launch {
            RunnerController.stats.collectLatest { stats ->
                tvStatus?.text = "Xu: +${stats.coinsEarned} | Job: ${stats.followed + stats.liked}"
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
