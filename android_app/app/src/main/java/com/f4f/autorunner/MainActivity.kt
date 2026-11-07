package com.f4f.autorunner

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.view.View
import android.widget.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.f4f.autorunner.adb.AdbManager
import com.f4f.autorunner.api.F4FApiClient
import com.f4f.autorunner.api.SocialAccount
import com.f4f.autorunner.controller.LogLevel
import com.f4f.autorunner.controller.RunnerController
import com.f4f.autorunner.controller.RunnerState
import com.f4f.autorunner.security.SecureStore
import com.f4f.autorunner.service.FloatingWidgetService
import com.google.android.material.bottomnavigation.BottomNavigationView
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.collectLatest

class MainActivity : AppCompatActivity() {

    private val apiClient = F4FApiClient()
    private var accounts: List<SocialAccount> = emptyList()
    private var selectedPlatform = "tiktok"
    private var activeLogFilter: LogLevel? = null
    private var startTimeMs: Long = 0
    private var userBaseBalance: Int = 0

    // Tab Views
    private lateinit var viewDashboard: View
    private lateinit var viewTasks: View
    private lateinit var viewLogs: View
    private lateinit var viewSettings: View
    private lateinit var bottomNav: BottomNavigationView

    // Dashboard Views
    private lateinit var dotHeroStatus: TextView
    private lateinit var tvHeroTitle: TextView
    private lateinit var tvHeroSubtitle: TextView
    private lateinit var tvDashBalance: TextView
    private lateinit var tvDashAdbBadge: TextView
    private lateinit var tvTiktokConnStatus: TextView
    private lateinit var ivTiktokConnIcon: ImageView
    private lateinit var tvInstagramConnStatus: TextView
    private lateinit var ivInstagramConnIcon: ImageView
    private lateinit var tvDashStatCompleted: TextView
    private lateinit var tvDashStatFailed: TextView
    private lateinit var tvDashStatCoins: TextView
    private lateinit var tvDashStatTime: TextView
    private lateinit var tvDashStatTotal: TextView
    private lateinit var btnDashStart: Button
    private lateinit var boxRunningControls: View
    private lateinit var btnDashPause: Button
    private lateinit var btnDashStop: Button

    // Tasks Views
    private lateinit var btnSegmentTiktok: View
    private lateinit var btnSegmentInstagram: View
    private lateinit var spAccounts: Spinner
    private lateinit var spJobType: Spinner
    private lateinit var tvStepperJobsValue: TextView
    private lateinit var tvStepperDelayValue: TextView
    private lateinit var boxAdvancedOptions: View
    private lateinit var ivAdvancedArrow: TextView

    // Logs Views
    private lateinit var tvTerminalLogs: TextView
    private lateinit var scrollLogs: ScrollView
    private lateinit var chipFilterAll: TextView
    private lateinit var chipFilterInfo: TextView
    private lateinit var chipFilterSuccess: TextView
    private lateinit var chipFilterWarn: TextView
    private lateinit var chipFilterError: TextView

    // Settings Views
    private lateinit var tvSettingsUsername: TextView
    private lateinit var tvSettingsUserid: TextView
    private lateinit var tvSettingsBalance: TextView
    private lateinit var btnLogout: Button

    // ADB Views in Settings
    private lateinit var boxAdbStatusDisconnected: View
    private lateinit var boxAdbStatusConnected: View
    private lateinit var tvAdbStatusDisconnectedTitle: TextView
    private lateinit var tvAdbStatusDisconnectedSub: TextView
    private lateinit var tvAdbStatusConnectedTitle: TextView
    private lateinit var tvAdbStatusConnectedSub: TextView
    private lateinit var etAdbHost: EditText
    private lateinit var etAdbPort: EditText
    private lateinit var btnAdbConnect: Button
    private lateinit var btnAdbDisconnect: Button
    private lateinit var tvAdbGuide: TextView

    // Overlay Views
    private lateinit var cardOverlayPermission: View
    private lateinit var tvOverlayStatusDesc: TextView
    private lateinit var tvOverlayBadge: TextView
    private lateinit var swOverlayPermission: androidx.appcompat.widget.SwitchCompat
    private lateinit var swTasksFloatingWidget: androidx.appcompat.widget.SwitchCompat

    // Current parameters
    private var maxJobs = 100
    private var delayMin = 8
    private var delayMax = 18

    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        requestNotificationPermissionIfNeeded()

        AdbManager.init(this)
        initViews()
        setupBottomNav()
        setupListeners()
        setupStateObservers()
        initTaskControls()
        loadSavedSession()
        initAdbState()
    }

    override fun onResume() {
        super.onResume()
        updateAdbUiState()
        updateOverlayPermissionUi()
        checkPlatformAccountsHealth()
    }

    private fun initViews() {
        viewDashboard = findViewById(R.id.view_dashboard)
        viewTasks = findViewById(R.id.view_tasks)
        viewLogs = findViewById(R.id.view_logs)
        viewSettings = findViewById(R.id.view_settings)
        bottomNav = findViewById(R.id.bottom_navigation)

        // Dashboard
        dotHeroStatus = findViewById(R.id.dot_hero_status)
        tvHeroTitle = findViewById(R.id.tv_hero_title)
        tvHeroSubtitle = findViewById(R.id.tv_hero_subtitle)
        tvDashBalance = findViewById(R.id.tv_dash_balance)
        tvDashAdbBadge = findViewById(R.id.tv_dash_adb_badge)
        tvTiktokConnStatus = findViewById(R.id.tv_tiktok_conn_status)
        ivTiktokConnIcon = findViewById(R.id.iv_tiktok_conn_icon)
        tvInstagramConnStatus = findViewById(R.id.tv_instagram_conn_status)
        ivInstagramConnIcon = findViewById(R.id.iv_instagram_conn_icon)
        tvDashStatCompleted = findViewById(R.id.tv_dash_stat_completed)
        tvDashStatFailed = findViewById(R.id.tv_dash_stat_failed)
        tvDashStatCoins = findViewById(R.id.tv_dash_stat_coins)
        tvDashStatTime = findViewById(R.id.tv_dash_stat_time)
        tvDashStatTotal = findViewById(R.id.tv_dash_stat_total)
        btnDashStart = findViewById(R.id.btn_dash_start)
        boxRunningControls = findViewById(R.id.box_running_controls)
        btnDashPause = findViewById(R.id.btn_dash_pause)
        btnDashStop = findViewById(R.id.btn_dash_stop)

        // Tasks
        btnSegmentTiktok = findViewById(R.id.btn_segment_tiktok)
        btnSegmentInstagram = findViewById(R.id.btn_segment_instagram)
        spAccounts = findViewById(R.id.sp_accounts)
        spJobType = findViewById(R.id.sp_job_type)
        tvStepperJobsValue = findViewById(R.id.tv_stepper_jobs_value)
        tvStepperDelayValue = findViewById(R.id.tv_stepper_delay_value)
        boxAdvancedOptions = findViewById(R.id.box_advanced_options)
        ivAdvancedArrow = findViewById(R.id.iv_advanced_arrow)

        // Logs
        tvTerminalLogs = findViewById(R.id.tv_terminal_logs)
        scrollLogs = findViewById(R.id.scroll_logs)
        chipFilterAll = findViewById(R.id.chip_filter_all)
        chipFilterInfo = findViewById(R.id.chip_filter_info)
        chipFilterSuccess = findViewById(R.id.chip_filter_success)
        chipFilterWarn = findViewById(R.id.chip_filter_warn)
        chipFilterError = findViewById(R.id.chip_filter_error)

        // Settings
        tvSettingsUsername = findViewById(R.id.tv_settings_username)
        tvSettingsUserid = findViewById(R.id.tv_settings_userid)
        tvSettingsBalance = findViewById(R.id.tv_settings_balance)
        btnLogout = findViewById(R.id.btn_logout)

        // Settings ADB
        boxAdbStatusDisconnected = findViewById(R.id.box_adb_status_disconnected)
        boxAdbStatusConnected = findViewById(R.id.box_adb_status_connected)
        tvAdbStatusDisconnectedTitle = findViewById(R.id.tv_adb_status_disconnected_title)
        tvAdbStatusDisconnectedSub = findViewById(R.id.tv_adb_status_disconnected_sub)
        tvAdbStatusConnectedTitle = findViewById(R.id.tv_adb_status_connected_title)
        tvAdbStatusConnectedSub = findViewById(R.id.tv_adb_status_connected_sub)
        etAdbHost = findViewById(R.id.et_adb_host)
        etAdbPort = findViewById(R.id.et_adb_port)
        btnAdbConnect = findViewById(R.id.btn_adb_connect)
        btnAdbDisconnect = findViewById(R.id.btn_adb_disconnect)
        tvAdbGuide = findViewById(R.id.tv_adb_guide)

        // Overlay Views
        cardOverlayPermission = findViewById(R.id.card_overlay_permission)
        tvOverlayStatusDesc = findViewById(R.id.tv_overlay_status_desc)
        tvOverlayBadge = findViewById(R.id.tv_overlay_badge)
        swOverlayPermission = findViewById(R.id.sw_overlay_permission)
        swTasksFloatingWidget = findViewById(R.id.sw_tasks_floating_widget)
    }

    private fun setupBottomNav() {
        bottomNav.setOnItemSelectedListener { item ->
            viewDashboard.visibility = View.GONE
            viewTasks.visibility = View.GONE
            viewLogs.visibility = View.GONE
            viewSettings.visibility = View.GONE

            when (item.itemId) {
                R.id.nav_dashboard -> {
                    viewDashboard.visibility = View.VISIBLE
                    checkPlatformAccountsHealth()
                    updateAdbUiState()
                    true
                }
                R.id.nav_tasks -> {
                    viewTasks.visibility = View.VISIBLE
                    updateOverlayPermissionUi()
                    true
                }
                R.id.nav_logs -> {
                    viewLogs.visibility = View.VISIBLE
                    true
                }
                R.id.nav_settings -> {
                    viewSettings.visibility = View.VISIBLE
                    updateAdbUiState()
                    updateOverlayPermissionUi()
                    true
                }
                else -> false
            }
        }
    }

    private fun setupListeners() {
        // Quick Settings button on Dashboard header
        findViewById<View>(R.id.btn_dash_quick_settings).setOnClickListener {
            bottomNav.selectedItemId = R.id.nav_settings
        }

        // Back from Tasks to Dashboard
        findViewById<View>(R.id.btn_tasks_back).setOnClickListener {
            bottomNav.selectedItemId = R.id.nav_dashboard
        }

        // Help dialog
        findViewById<View>(R.id.btn_tasks_help).setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Hướng dẫn Cấu hình")
                .setMessage("• Số lượng Job: Giới hạn số nhiệm vụ tối đa trong một phiên.\n• Delay: Khoảng thời gian nghỉ ngẫu nhiên giữa các job để tránh checkpoint.\n• Tự động hóa qua ADB: Chạy trực tiếp qua lệnh hệ thống, không sợ văng quyền Trợ Năng.")
                .setPositiveButton("Đã hiểu", null)
                .show()
        }

        // Platform segment toggles
        btnSegmentTiktok.setOnClickListener {
            setPlatformSelection("tiktok")
        }

        btnSegmentInstagram.setOnClickListener {
            setPlatformSelection("instagram")
        }

        // Steppers: Jobs
        findViewById<View>(R.id.btn_stepper_jobs_minus).setOnClickListener {
            if (maxJobs > 25) {
                maxJobs -= 25
                tvStepperJobsValue.text = maxJobs.toString(); saveTaskPrefs()
            }
        }

        findViewById<View>(R.id.btn_stepper_jobs_plus).setOnClickListener {
            if (maxJobs < 1000) {
                maxJobs += 25
                tvStepperJobsValue.text = maxJobs.toString(); saveTaskPrefs()
            }
        }

        // Steppers: Delay
        findViewById<View>(R.id.btn_stepper_delay_minus).setOnClickListener {
            if (delayMin > 4) {
                delayMin -= 2
                delayMax -= 2
                tvStepperDelayValue.text = "$delayMin - $delayMax"; saveTaskPrefs()
            }
        }

        findViewById<View>(R.id.btn_stepper_delay_plus).setOnClickListener {
            if (delayMax < 40) {
                delayMin += 2
                delayMax += 2
                tvStepperDelayValue.text = "$delayMin - $delayMax"; saveTaskPrefs()
            }
        }

        // Advanced Options accordion toggle
        findViewById<View>(R.id.header_advanced_options).setOnClickListener {
            if (boxAdvancedOptions.visibility == View.VISIBLE) {
                boxAdvancedOptions.visibility = View.GONE
                ivAdvancedArrow.text = "▼"
            } else {
                boxAdvancedOptions.visibility = View.VISIBLE
                ivAdvancedArrow.text = "▲"
            }
        }

        // Save settings button
        findViewById<View>(R.id.btn_save_settings).setOnClickListener {
            saveTaskPrefs()
            Toast.makeText(this, "✓ Đã lưu cấu hình chiến dịch thành công!", Toast.LENGTH_SHORT).show()
            bottomNav.selectedItemId = R.id.nav_dashboard
        }

        // Action controllers
        btnDashStart.setOnClickListener {
            startRunner()
        }

        btnDashPause.setOnClickListener {
            if (RunnerController.isRunning) {
                RunnerController.pause()
            } else if (RunnerController.isPaused) {
                RunnerController.resume()
            }
        }

        btnDashStop.setOnClickListener {
            RunnerController.stop()
            stopService(Intent(this, FloatingWidgetService::class.java))
        }

        // Log Filter Chips
        chipFilterAll.setOnClickListener { setChipFilter(null, it) }
        chipFilterInfo.setOnClickListener { setChipFilter(LogLevel.INFO, it) }
        chipFilterSuccess.setOnClickListener { setChipFilter(LogLevel.SUCCESS, it) }
        chipFilterWarn.setOnClickListener { setChipFilter(LogLevel.WARN, it) }
        chipFilterError.setOnClickListener { setChipFilter(LogLevel.ERROR, it) }

        // Copy logs
        findViewById<View>(R.id.btn_copy_log).setOnClickListener {
            val fullLogs = RunnerController.logs.value.joinToString("\n") {
                "[${it.timestamp}] [${it.level}] ${it.message}"
            }
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            clipboard.setPrimaryClip(ClipData.newPlainText("F4F Logs", fullLogs))
            Toast.makeText(this, "Đã sao chép nhật ký vào bộ nhớ tạm", Toast.LENGTH_SHORT).show()
        }

        // Clear logs
        val clearAction = View.OnClickListener {
            RunnerController.clearLogs()
            Toast.makeText(this, "Đã xóa sạch nhật ký", Toast.LENGTH_SHORT).show()
        }
        findViewById<View>(R.id.btn_clear_log).setOnClickListener(clearAction)
        findViewById<View>(R.id.btn_clear_log_top).setOnClickListener(clearAction)

        // Logout
        btnLogout.setOnClickListener {
            showLoginOrLogoutDialog()
        }

        // ADB Connect / Disconnect buttons
        btnAdbConnect.setOnClickListener {
            val targetHost = etAdbHost.text.toString().trim().ifEmpty { "127.0.0.1" }
            val targetPort = etAdbPort.text.toString().trim().toIntOrNull() ?: 5555
            Toast.makeText(this, "Đang kết nối ADB tới $targetHost:$targetPort...", Toast.LENGTH_SHORT).show()
            RunnerController.addLog(LogLevel.INFO, "Đang thử kết nối ADB: $targetHost:$targetPort...")

            lifecycleScope.launch {
                val (ok, message) = AdbManager.connect(this@MainActivity, targetHost, targetPort)
                updateAdbUiState()
                if (ok) {
                    Toast.makeText(this@MainActivity, message, Toast.LENGTH_SHORT).show()
                    RunnerController.addLog(LogLevel.SUCCESS, message)
                } else {
                    Toast.makeText(this@MainActivity, message, Toast.LENGTH_LONG).show()
                    RunnerController.addLog(LogLevel.ERROR, message)
                }
            }
        }

        btnAdbDisconnect.setOnClickListener {
            AdbManager.disconnect()
            updateAdbUiState()
            Toast.makeText(this, "Đã ngắt kết nối ADB", Toast.LENGTH_SHORT).show()
            RunnerController.addLog(LogLevel.WARN, "Đã ngắt kết nối ADB.")
        }

        // Overlay Listeners
        cardOverlayPermission.setOnClickListener {
            requestOverlayPermission()
        }

        swOverlayPermission.setOnClickListener {
            requestOverlayPermission()
        }

        swTasksFloatingWidget.setOnClickListener {
            val wanted = swTasksFloatingWidget.isChecked
            taskPrefs().edit().putBoolean(FloatingWidgetService.PREF_WIDGET_ENABLED, wanted).apply()
            if (wanted && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                swTasksFloatingWidget.isChecked = false
                requestOverlayPermission()
            }
        }
    }

    private fun updateOverlayPermissionUi() {
        val hasOverlay = Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)
        swOverlayPermission.isChecked = hasOverlay
        swTasksFloatingWidget.isChecked =
            hasOverlay && taskPrefs().getBoolean(FloatingWidgetService.PREF_WIDGET_ENABLED, true)

        if (hasOverlay) {
            tvOverlayBadge.text = "ĐÃ BẬT"
            tvOverlayBadge.setTextColor(Color.parseColor("#10B981"))
            tvOverlayBadge.setBackgroundResource(R.drawable.bg_pill_active)
            tvOverlayStatusDesc.text = "Cửa sổ nổi đã sẵn sàng hoạt động khi bắt đầu auto"
        } else {
            tvOverlayBadge.text = "CHƯA BẬT"
            tvOverlayBadge.setTextColor(Color.parseColor("#EF4444"))
            tvOverlayBadge.setBackgroundResource(R.drawable.bg_pill_inactive)
            tvOverlayStatusDesc.text = "Chạm để cấp quyền hiển thị cửa sổ điều khiển nổi"
        }
    }

    private fun requestOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (!Settings.canDrawOverlays(this)) {
                Toast.makeText(this, "Vui lòng tìm 'F4F AutoRunner' và gạt Bật cho phép hiển thị", Toast.LENGTH_LONG).show()
                try {
                    val intent = Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:$packageName")
                    )
                    startActivity(intent)
                } catch (_: Exception) {
                    try {
                        val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
                        startActivity(intent)
                    } catch (e: Exception) {
                        Toast.makeText(this, "Không thể mở cài đặt quyền: ${e.message}", Toast.LENGTH_SHORT).show()
                    }
                }
            } else {
                Toast.makeText(this, "Quyền hiển thị trên ứng dụng khác đã được cấp!", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun initAdbState() {
        etAdbHost.setText(AdbManager.host)
        etAdbPort.setText(AdbManager.port.toString())

        lifecycleScope.launch {
            if (AdbManager.wasEverConnected) {
                // Tự động kết nối lại nếu từng kết nối thành công
                AdbManager.connect(this@MainActivity, AdbManager.host, AdbManager.port)
            }
            updateAdbUiState()
        }
    }

    private fun updateAdbUiState() {
        if (AdbManager.isConnected) {
            tvDashAdbBadge.text = "⚡ ADB: Đã kết nối (${AdbManager.host}:${AdbManager.port})"
            tvDashAdbBadge.setTextColor(Color.parseColor("#10B981"))

            // Cập nhật thẻ trạng thái trong Cài đặt
            boxAdbStatusConnected.setBackgroundResource(R.drawable.bg_pill_active)
            tvAdbStatusConnectedTitle.setTextColor(Color.WHITE)
            tvAdbStatusConnectedSub.text = "Đang kết nối: ${AdbManager.host}:${AdbManager.port}"

            boxAdbStatusDisconnected.setBackgroundResource(R.drawable.bg_card_secondary)
            tvAdbStatusDisconnectedTitle.setTextColor(Color.parseColor("#94A3B8"))
            tvAdbStatusDisconnectedSub.text = "Nhấn Ngắt để hủy"

            btnAdbConnect.text = "🔄 KẾT NỐI LẠI"
        } else if (AdbManager.wasEverConnected) {
            tvDashAdbBadge.text = "⚡ ADB: Từng kết nối (${AdbManager.lastConnectedTime})"
            tvDashAdbBadge.setTextColor(Color.parseColor("#F59E0B"))

            boxAdbStatusDisconnected.setBackgroundResource(R.drawable.bg_pill_active)
            tvAdbStatusDisconnectedTitle.setTextColor(Color.WHITE)
            tvAdbStatusDisconnectedSub.text = "Đang ngắt kết nối"

            boxAdbStatusConnected.setBackgroundResource(R.drawable.bg_card_secondary)
            tvAdbStatusConnectedTitle.setTextColor(Color.parseColor("#10B981"))
            tvAdbStatusConnectedSub.text = "Từng kết nối: ${AdbManager.lastConnectedTime}"

            btnAdbConnect.text = "⚡ KẾT NỐI ADB"
        } else {
            tvDashAdbBadge.text = "⚡ ADB: Chưa kết nối"
            tvDashAdbBadge.setTextColor(Color.parseColor("#EF4444"))

            boxAdbStatusDisconnected.setBackgroundResource(R.drawable.bg_pill_active)
            tvAdbStatusDisconnectedTitle.setTextColor(Color.WHITE)
            tvAdbStatusDisconnectedSub.text = "Chưa kết nối ADB"

            boxAdbStatusConnected.setBackgroundResource(R.drawable.bg_card_secondary)
            tvAdbStatusConnectedTitle.setTextColor(Color.parseColor("#94A3B8"))
            tvAdbStatusConnectedSub.text = "Chưa có lịch sử kết nối"

            btnAdbConnect.text = "⚡ KẾT NỐI ADB"
        }
    }

    private fun checkPlatformAccountsHealth() {
        lifecycleScope.launch {
            if (apiClient.token == null) {
                tvTiktokConnStatus.text = "Chưa kết nối"
                tvTiktokConnStatus.setTextColor(Color.parseColor("#94A3B8"))
                ivTiktokConnIcon.setImageResource(R.drawable.ic_close_circle)
                ivTiktokConnIcon.imageTintList = ColorStateList.valueOf(Color.parseColor("#64748B"))

                tvInstagramConnStatus.text = "Chưa kết nối"
                tvInstagramConnStatus.setTextColor(Color.parseColor("#94A3B8"))
                ivInstagramConnIcon.setImageResource(R.drawable.ic_close_circle)
                ivInstagramConnIcon.imageTintList = ColorStateList.valueOf(Color.parseColor("#64748B"))
                return@launch
            }

            // Kiểm tra TikTok
            try {
                val ttAccs = apiClient.getAccounts("tiktok")
                if (ttAccs.isNotEmpty()) {
                    tvTiktokConnStatus.text = "Đã kết nối (@${ttAccs[0].getDisplayName()})"
                    tvTiktokConnStatus.setTextColor(Color.parseColor("#10B981"))
                    ivTiktokConnIcon.setImageResource(R.drawable.ic_check_circle)
                    ivTiktokConnIcon.imageTintList = ColorStateList.valueOf(Color.parseColor("#10B981"))
                } else {
                    tvTiktokConnStatus.text = "Chưa kết nối"
                    tvTiktokConnStatus.setTextColor(Color.parseColor("#94A3B8"))
                    ivTiktokConnIcon.setImageResource(R.drawable.ic_close_circle)
                    ivTiktokConnIcon.imageTintList = ColorStateList.valueOf(Color.parseColor("#64748B"))
                }
            } catch (_: Exception) {}

            // Kiểm tra Instagram
            try {
                val igAccs = apiClient.getAccounts("instagram")
                if (igAccs.isNotEmpty()) {
                    tvInstagramConnStatus.text = "Đã kết nối (@${igAccs[0].getDisplayName()})"
                    tvInstagramConnStatus.setTextColor(Color.parseColor("#10B981"))
                    ivInstagramConnIcon.setImageResource(R.drawable.ic_check_circle)
                    ivInstagramConnIcon.imageTintList = ColorStateList.valueOf(Color.parseColor("#10B981"))
                } else {
                    tvInstagramConnStatus.text = "Chưa kết nối"
                    tvInstagramConnStatus.setTextColor(Color.parseColor("#94A3B8"))
                    ivInstagramConnIcon.setImageResource(R.drawable.ic_close_circle)
                    ivInstagramConnIcon.imageTintList = ColorStateList.valueOf(Color.parseColor("#64748B"))
                }
            } catch (_: Exception) {}
        }
    }

    private fun setPlatformSelection(plat: String) {
        selectedPlatform = plat
        if (plat == "tiktok") {
            btnSegmentTiktok.setBackgroundResource(R.drawable.bg_pill_active)
            btnSegmentInstagram.background = null
        } else {
            btnSegmentInstagram.setBackgroundResource(R.drawable.bg_pill_active)
            btnSegmentTiktok.background = null
        }
        lifecycleScope.launch {
            loadAccounts()
        }
    }

    private fun initTaskControls() {
        val jobTypes = listOf("Follow", "Like", "Tất cả (Follow & Like)")
        val jobAdapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, jobTypes)
        spJobType.adapter = jobAdapter
        loadTaskPrefs()
    }

    private fun taskPrefs() = getSharedPreferences("f4f_config", Context.MODE_PRIVATE)

    private fun saveTaskPrefs() {
        taskPrefs().edit()
            .putInt("task_max_jobs", maxJobs)
            .putInt("task_delay_min", delayMin)
            .putInt("task_delay_max", delayMax)
            .putInt("task_job_type", spJobType.selectedItemPosition.coerceAtLeast(0))
            .apply()
    }

    private fun loadTaskPrefs() {
        val p = taskPrefs()
        maxJobs = p.getInt("task_max_jobs", 100).coerceIn(25, 1000)
        delayMin = p.getInt("task_delay_min", 8).coerceAtLeast(4)
        delayMax = p.getInt("task_delay_max", 18).coerceAtLeast(delayMin)
        tvStepperJobsValue.text = maxJobs.toString()
        tvStepperDelayValue.text = "$delayMin - $delayMax"
        spJobType.setSelection(p.getInt("task_job_type", 2).coerceIn(0, 2))
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private fun setupStateObservers() {
        // 1. Runner state
        lifecycleScope.launch {
            RunnerController.state.collectLatest { state ->
                when (state) {
                    RunnerState.IDLE, RunnerState.STOPPED -> {
                        dotHeroStatus.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#10B981"))
                        tvHeroTitle.text = "Đang sẵn sàng"
                        tvHeroSubtitle.text = "Nhấn START để bắt đầu chạy auto"
                        btnDashStart.visibility = View.VISIBLE
                        boxRunningControls.visibility = View.GONE
                    }
                    RunnerState.RUNNING -> {
                        dotHeroStatus.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#10B981"))
                        tvHeroTitle.text = "Đang chạy chiến dịch (${if (AdbManager.isConnected) "ADB" else "Trợ Năng"})"
                        tvHeroSubtitle.text = "Tự động tương tác và nhận xu..."
                        btnDashStart.visibility = View.GONE
                        boxRunningControls.visibility = View.VISIBLE
                        btnDashPause.text = "⏸  TẠM DỪNG"
                        btnDashPause.setTextColor(Color.WHITE)
                    }
                    RunnerState.PAUSED -> {
                        dotHeroStatus.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#F59E0B"))
                        tvHeroTitle.text = "Đang tạm dừng"
                        tvHeroSubtitle.text = "Nhấn TIẾP TỤC để chạy lại"
                        btnDashStart.visibility = View.GONE
                        boxRunningControls.visibility = View.VISIBLE
                        btnDashPause.text = "▶  TIẾP TỤC"
                        btnDashPause.setTextColor(Color.parseColor("#10B981"))
                    }
                }
            }
        }

        // 2. Runner stats & Coin tracking
        lifecycleScope.launch {
            RunnerController.stats.collectLatest { stats ->
                val completed = stats.followed + stats.liked
                val failed = stats.skipped + stats.errors
                val total = completed + failed

                tvDashStatCompleted.text = completed.toString()
                tvDashStatFailed.text = failed.toString()
                tvDashStatTotal.text = total.toString()
                tvDashStatCoins.text = "+${stats.coinsEarned} xu"

                val dynamicTotalBalance = userBaseBalance + stats.coinsEarned
                tvDashBalance.text = "🪙 Số dư F4F: $dynamicTotalBalance xu"
                tvSettingsBalance.text = "🪙 Số dư: $dynamicTotalBalance xu"
            }
        }

        // 3. Runner logs
        lifecycleScope.launch {
            RunnerController.logs.collectLatest { logs ->
                renderLogs(logs)
            }
        }

        // 4. Timer updater
        lifecycleScope.launch {
            while (isActive) {
                if (RunnerController.isRunning && startTimeMs > 0) {
                    val elapsedSec = (System.currentTimeMillis() - startTimeMs) / 1000
                    val hours = elapsedSec / 3600
                    val mins = (elapsedSec % 3600) / 60
                    tvDashStatTime.text = "${hours}h ${mins}m"
                }
                delay(1000)
            }
        }
    }

    private fun setChipFilter(level: LogLevel?, view: View) {
        activeLogFilter = level
        val chips = listOf(chipFilterAll, chipFilterInfo, chipFilterSuccess, chipFilterWarn, chipFilterError)
        for (c in chips) {
            c.setBackgroundResource(R.drawable.bg_pill_inactive)
            c.setTextColor(Color.parseColor("#94A3B8"))
        }
        view.setBackgroundResource(R.drawable.bg_pill_active)
        (view as TextView).setTextColor(Color.WHITE)
        renderLogs(RunnerController.logs.value)
    }

    private fun renderLogs(logs: List<com.f4f.autorunner.controller.LogEntry>) {
        val filtered = if (activeLogFilter == null) {
            logs
        } else {
            logs.filter { it.level == activeLogFilter }
        }

        val ssb = SpannableStringBuilder()
        for (entry in filtered) {
            val start = ssb.length
            val line = "[${entry.timestamp}] [${entry.level}] ${entry.message}\n"
            ssb.append(line)
            val end = ssb.length

            val color = when (entry.level) {
                LogLevel.SUCCESS -> Color.parseColor("#10B981")
                LogLevel.WARN -> Color.parseColor("#F59E0B")
                LogLevel.ERROR -> Color.parseColor("#EF4444")
                LogLevel.INFO -> Color.parseColor("#38BDF8")
            }
            ssb.setSpan(ForegroundColorSpan(color), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }

        tvTerminalLogs.text = ssb
        scrollLogs.post { scrollLogs.fullScroll(View.FOCUS_DOWN) }
    }

    private fun startRunner() {
        val hasAdb = AdbManager.isConnected
        val hasAccessibility = com.f4f.autorunner.service.F4FAccessibilityService.isRunning()

        if (!hasAdb && !hasAccessibility) {
            AlertDialog.Builder(this)
                .setTitle("Chưa có chế độ điều khiển")
                .setMessage("Cần bật dịch vụ Trợ Năng 'F4F Auto Runner' hoặc kết nối ADB để app tự bấm Follow/Like.")
                .setPositiveButton("Mở cài đặt Trợ Năng") { _, _ ->
                    try {
                        startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                    } catch (e: Exception) {
                        Toast.makeText(this, "Không thể mở cài đặt Trợ Năng: ${e.message}", Toast.LENGTH_SHORT).show()
                    }
                }
                .setNeutralButton("Cài đặt ADB") { _, _ -> bottomNav.selectedItemId = R.id.nav_settings }
                .setNegativeButton("Hủy", null)
                .show()
            return
        }

        if (apiClient.token == null) {
            showLoginOrLogoutDialog()
            return
        }

        if (accounts.isEmpty()) {
            Toast.makeText(this, "Chưa chọn tài khoản MXH nào!", Toast.LENGTH_SHORT).show()
            bottomNav.selectedItemId = R.id.nav_tasks
            return
        }

        val selectedIdx = spAccounts.selectedItemPosition.coerceAtLeast(0)
        val selectedAccount = accounts.getOrNull(selectedIdx) ?: accounts[0]

        // Start floating widget if overlay granted and switch is enabled
        val hasOverlay = Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)
        // Luôn chạy foreground service để tiến trình không bị hệ thống kill khi app xuống nền;
        // service tự quyết định có vẽ bong bóng nổi hay không.
        try {
            ContextCompat.startForegroundService(this, Intent(this, FloatingWidgetService::class.java))
        } catch (_: Exception) {}
        if (!hasOverlay && swTasksFloatingWidget.isChecked) {
            Toast.makeText(this, "Mẹo: Bạn có thể bật 'Hiển thị trên ứng dụng khác' trong Cài đặt để hiện cửa sổ nổi!", Toast.LENGTH_LONG).show()
        }

        saveTaskPrefs()
        val selectedJobType = when (spJobType.selectedItemPosition) {
            0 -> "follow"
            1 -> "like"
            else -> "all"
        }

        startTimeMs = System.currentTimeMillis()

        RunnerController.start(
            context = this,
            apiClient = apiClient,
            platform = selectedPlatform,
            accountId = selectedAccount.getId(),
            accountName = selectedAccount.getDisplayName(),
            jobType = selectedJobType,
            maxJobs = maxJobs,
            delayMin = delayMin,
            delayMax = delayMax
        )
    }

    private fun showLoginOrLogoutDialog() {
        val dialogView = layoutInflater.inflate(R.layout.dialog_f4f_login, null)
        val etUser = dialogView.findViewById<EditText>(R.id.dialog_et_user)
        val etPass = dialogView.findViewById<EditText>(R.id.dialog_et_pass)

        val prefs = getSharedPreferences("f4f_config", Context.MODE_PRIVATE)
        etUser.setText(prefs.getString("f4f_user", ""))

        AlertDialog.Builder(this)
            .setTitle("Đăng nhập Follow4Follow")
            .setView(dialogView)
            .setPositiveButton("Đăng nhập") { _, _ ->
                val u = etUser.text.toString().trim()
                val p = etPass.text.toString().trim()
                if (u.isNotEmpty() && p.isNotEmpty()) {
                    performLogin(u, p)
                }
            }
            .setNegativeButton("Hủy", null)
            .show()
    }

    private fun performLogin(user: String, pass: String) {
        RunnerController.addLog(LogLevel.INFO, "Đang kết nối F4F...")
        lifecycleScope.launch {
            try {
                val data = apiClient.login(user, pass)
                val displayBalance = data.user.getDisplayBalance()
                userBaseBalance = data.user.getNumericBalance()

                val editor = getSharedPreferences("f4f_config", Context.MODE_PRIVATE).edit()
                    .putString("f4f_user", user)
                    .remove("f4f_pass") // xóa mật khẩu dạng văn bản thường của phiên bản cũ
                    .putString("f4f_balance", displayBalance)
                    .putInt("f4f_balance_num", userBaseBalance)
                val encrypted = SecureStore.encryptOrNull(pass)
                if (encrypted != null) editor.putString("f4f_pass_enc", encrypted) else editor.remove("f4f_pass_enc")
                editor.apply()

                tvSettingsUsername.text = data.user.username ?: user
                tvSettingsUserid.text = "ID: ${data.user.id ?: "F4F"}"
                tvSettingsBalance.text = "🪙 Số dư: $displayBalance"
                tvDashBalance.text = "🪙 Số dư F4F: $displayBalance"

                RunnerController.addLog(LogLevel.SUCCESS, "Đăng nhập thành công: @${data.user.username} | $displayBalance")
                checkPlatformAccountsHealth()
                loadAccounts()
            } catch (e: Exception) {
                RunnerController.addLog(LogLevel.ERROR, "Đăng nhập thất bại: ${e.message}")
                Toast.makeText(this@MainActivity, "Lỗi đăng nhập: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private suspend fun loadAccounts() {
        try {
            accounts = apiClient.getAccounts(selectedPlatform)
            val names = if (accounts.isEmpty()) {
                listOf("(Chưa có nick $selectedPlatform nào)")
            } else {
                accounts.map { "@${it.getDisplayName()} (${it.status ?: "Hoạt động"})" }
            }
            val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, names)
            spAccounts.adapter = adapter
            RunnerController.addLog(LogLevel.INFO, "Đã tải ${accounts.size} nick [$selectedPlatform] từ F4F.")
        } catch (e: Exception) {
            RunnerController.addLog(LogLevel.ERROR, "Lỗi tải nick: ${e.message}")
        }
    }

    private fun loadSavedSession() {
        val prefs = getSharedPreferences("f4f_config", Context.MODE_PRIVATE)
        val user = prefs.getString("f4f_user", "") ?: ""
        // Ưu tiên bản mã hóa; vẫn đọc được bản cũ (văn bản thường) để tự chuyển sang mã hóa khi đăng nhập
        val legacyPass = prefs.getString("f4f_pass", null)
        val pass = prefs.getString("f4f_pass_enc", null)?.let { SecureStore.decrypt(it) }
            ?: legacyPass.orEmpty()
        val savedBal = prefs.getString("f4f_balance", "0 xu") ?: "0 xu"
        userBaseBalance = prefs.getInt("f4f_balance_num", 0)

        tvSettingsBalance.text = "🪙 Số dư: $savedBal"
        tvDashBalance.text = "🪙 Số dư F4F: $savedBal"

        if (user.isNotEmpty() && pass.isNotEmpty()) {
            performLogin(user, pass)
        }
    }
}
