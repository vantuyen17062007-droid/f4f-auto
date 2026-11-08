package com.f4f.autorunner.service

import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.view.*
import android.widget.TextView
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.f4f.autorunner.R
import com.f4f.autorunner.automation.RunnerController
import com.f4f.autorunner.model.LogLevel
import com.f4f.autorunner.model.RunnerState
import com.f4f.autorunner.ui.MainActivity
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.collectLatest

/**
 * Foreground service: giữ tiến trình sống khi app xuống nền (đặc biệt ở chế độ ADB)
 * và hiển thị bong bóng điều khiển nổi nếu đã cấp quyền + người dùng bật công tắc.
 */
class FloatingWidgetService : Service() {

    companion object {
        private const val CHANNEL_ID = "f4f_runner"
        private const val NOTIF_ID = 1001
        const val PREFS = "f4f_config"
        const val PREF_WIDGET_ENABLED = "widget_enabled"
    }

    private var windowManager: WindowManager? = null
    private var floatingView: View? = null
    private val serviceScope = CoroutineScope(Dispatchers.Main + Job())
    private var overlayJob: Job? = null
    private var startTimeMs: Long = 0
    private var seenActive = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        startTimeMs = System.currentTimeMillis()
        startAsForeground()

        // Tự dừng khi phiên chạy kết thúc. Chỉ dừng sau khi đã thấy RUNNING/PAUSED,
        // tránh tự tắt ngay lúc khởi tạo khi state còn là IDLE/STOPPED của phiên trước.
        serviceScope.launch {
            RunnerController.state.collectLatest { state ->
                when (state) {
                    RunnerState.RUNNING, RunnerState.PAUSED -> seenActive = true
                    RunnerState.STOPPED, RunnerState.IDLE -> if (seenActive) stopSelf()
                }
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startTimeMs = System.currentTimeMillis()
        if (floatingView == null && canShowOverlay()) {
            try {
                setupOverlay()
            } catch (e: Exception) {
                android.util.Log.e("FloatingWidget", "setupOverlay failed", e)
                RunnerController.addLog(LogLevel.ERROR, "Không hiện được cửa sổ nổi: ${e.message}")
                removeOverlay()
            }
        }
        return START_NOT_STICKY
    }

    private fun canShowOverlay(): Boolean {
        val enabled = getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(PREF_WIDGET_ENABLED, true)
        return enabled && Settings.canDrawOverlays(this)
    }

    private fun startAsForeground() {
        try {
            val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Tn Tool", NotificationManager.IMPORTANCE_LOW)
            )
            val openApp = PendingIntent.getActivity(
                this, 0,
                Intent(this, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
            )
            val notification = NotificationCompat.Builder(this, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_f_logo)
                .setContentTitle("Tn Tool")
                .setContentText("Đang chạy chiến dịch tự động")
                .setOngoing(true)
                .setContentIntent(openApp)
                .build()

            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIF_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
            } else {
                startForeground(NOTIF_ID, notification)
            }
        } catch (e: Exception) {
            android.util.Log.e("FloatingWidget", "startAsForeground failed", e)
            RunnerController.addLog(LogLevel.WARN, "Không khởi tạo được thông báo chạy ngầm: ${e.message}")
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun setupOverlay() {
        val themedContext = ContextThemeWrapper(this, R.style.Theme_F4FAutoRunner)
        val view = LayoutInflater.from(themedContext).inflate(R.layout.layout_floating_widget, null)
        floatingView = view

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 40
            y = 200
        }

        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        windowManager?.addView(view, params)

        // Kéo thả bằng drag_handle_pill
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f

        val dragPill = view.findViewById<View>(R.id.drag_handle_pill) ?: view
        dragPill.setOnTouchListener { _, event ->
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
                        windowManager?.updateViewLayout(view, params)
                    } catch (_: Exception) {}
                    true
                }
                else -> false
            }
        }

        val btnResume = view.findViewById<View>(R.id.btn_floating_resume)
        val btnPause = view.findViewById<View>(R.id.btn_floating_pause)
        val btnStop = view.findViewById<View>(R.id.btn_floating_stop)
        val btnMinimize = view.findViewById<View>(R.id.btn_floating_minimize)
        val btnClose = view.findViewById<View>(R.id.btn_floating_close)

        val tvStatusTime = view.findViewById<TextView>(R.id.tv_floating_status_time)
        val dotIndicator = view.findViewById<TextView>(R.id.dot_floating_indicator)
        val tvSuccess = view.findViewById<TextView>(R.id.tv_floating_success)
        val tvFailed = view.findViewById<TextView>(R.id.tv_floating_failed)
        val tvCoins = view.findViewById<TextView>(R.id.tv_floating_coins)
        val boxButtons = view.findViewById<View>(R.id.box_floating_buttons)

        val tvFloatingPlatform = view.findViewById<TextView>(R.id.tv_floating_platform)
        val tvFloatingAccount = view.findViewById<TextView>(R.id.tv_floating_account)
        val tvFloatingJobInfo = view.findViewById<TextView>(R.id.tv_floating_job_info)

        btnResume?.setOnClickListener { RunnerController.resume() }
        btnPause?.setOnClickListener { RunnerController.pause() }
        btnStop?.setOnClickListener {
            RunnerController.stop()
            stopSelf()
        }

        btnMinimize?.setOnClickListener {
            boxButtons?.visibility =
                if (boxButtons?.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }

        // Đóng bong bóng nhưng KHÔNG dừng phiên chạy (service vẫn giữ tiến trình sống)
        btnClose?.setOnClickListener { removeOverlay() }

        // Lắng nghe tài khoản & công việc đang chạy (gom vào overlayJob để hủy khi đóng bong bóng)
        overlayJob?.cancel()
        overlayJob = serviceScope.launch {
            launch {
                RunnerController.currentAccount.collectLatest { acc ->
                    tvFloatingAccount?.text = if (acc.isNotBlank()) "@$acc" else "Chưa chọn nick"
                }
            }

            launch {
                RunnerController.currentPlatform.collectLatest { plat ->
                    tvFloatingPlatform?.text = if (plat == "instagram") "Instagram" else "TikTok"
                }
            }

            launch {
                RunnerController.currentJobInfo.collectLatest { info ->
                    tvFloatingJobInfo?.text = info
                }
            }

            launch {
                RunnerController.state.collectLatest { state ->
                    val color = when (state) {
                        RunnerState.RUNNING -> R.color.status_ok
                        RunnerState.PAUSED -> R.color.status_warn
                        RunnerState.STOPPED, RunnerState.IDLE -> R.color.status_error
                    }
                    dotIndicator?.backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(this@FloatingWidgetService, color))
                }
            }

            launch {
                RunnerController.stats.collectLatest { stats ->
                    val completed = stats.followed + stats.liked
                    val failed = stats.skipped + stats.errors
                    tvSuccess?.text = "$completed Thành công"
                    tvFailed?.text = "$failed Thất bại"
                    tvCoins?.text = "+${stats.coinsEarned} xu"
                }
            }

            launch {
                while (isActive) {
                    val startMs = if (RunnerController.sessionStartTimeMs > 0) RunnerController.sessionStartTimeMs else startTimeMs
                    val elapsedSec = (System.currentTimeMillis() - startMs) / 1000
                    val hours = elapsedSec / 3600
                    val mins = (elapsedSec % 3600) / 60
                    val stateName = if (RunnerController.isPaused) "Tạm dừng" else "Đang chạy"
                    tvStatusTime?.text = "$stateName • ${hours}h ${mins}m"
                    delay(1000)
                }
            }
        }
    }

    private fun removeOverlay() {
        overlayJob?.cancel()
        overlayJob = null
        floatingView?.let {
            try {
                windowManager?.removeView(it)
            } catch (e: Exception) {
                android.util.Log.w("FloatingWidget", "removeView failed: ${e.message}")
            }
        }
        floatingView = null
    }

    override fun onDestroy() {
        super.onDestroy()
        removeOverlay()
        serviceScope.cancel()
    }
}
