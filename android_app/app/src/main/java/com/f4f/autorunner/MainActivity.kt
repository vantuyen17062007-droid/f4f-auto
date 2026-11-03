package com.f4f.autorunner

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
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
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.f4f.autorunner.api.F4FApiClient
import com.f4f.autorunner.api.SocialAccount
import com.f4f.autorunner.controller.LogLevel
import com.f4f.autorunner.controller.RunnerController
import com.f4f.autorunner.controller.RunnerState
import com.f4f.autorunner.service.F4FAccessibilityService
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
    private lateinit var tvTiktokConnStatus: TextView
    private lateinit var tvInstagramConnStatus: TextView
    private lateinit var tvDashStatCompleted: TextView
    private lateinit var tvDashStatFailed: TextView
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
    private lateinit var btnLogout: Button

    // Current parameters
    private var maxJobs = 100
    private var delayMin = 8
    private var delayMax = 18

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initViews()
        setupBottomNav()
        setupListeners()
        setupStateObservers()
        initTaskControls()
        loadSavedSession()
    }

    override fun onResume() {
        super.onResume()
        checkPermissionsHealth()
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
        tvTiktokConnStatus = findViewById(R.id.tv_tiktok_conn_status)
        tvInstagramConnStatus = findViewById(R.id.tv_instagram_conn_status)
        tvDashStatCompleted = findViewById(R.id.tv_dash_stat_completed)
        tvDashStatFailed = findViewById(R.id.tv_dash_stat_failed)
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
        btnLogout = findViewById(R.id.btn_logout)
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
                    true
                }
                R.id.nav_tasks -> {
                    viewTasks.visibility = View.VISIBLE
                    true
                }
                R.id.nav_logs -> {
                    viewLogs.visibility = View.VISIBLE
                    true
                }
                R.id.nav_settings -> {
                    viewSettings.visibility = View.VISIBLE
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
                .setMessage("• Số lượng Job: Giới hạn số nhiệm vụ tối đa trong một phiên.\n• Delay: Khoảng thời gian nghỉ ngẫu nhiên giữa các job để tránh checkpoint.\n• Tùy chọn nâng cao: Giữ app chạy nền mượt mà.")
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
                tvStepperJobsValue.text = maxJobs.toString()
            }
        }

        findViewById<View>(R.id.btn_stepper_jobs_plus).setOnClickListener {
            if (maxJobs < 1000) {
                maxJobs += 25
                tvStepperJobsValue.text = maxJobs.toString()
            }
        }

        // Steppers: Delay
        findViewById<View>(R.id.btn_stepper_delay_minus).setOnClickListener {
            if (delayMin > 4) {
                delayMin -= 2
                delayMax -= 2
                tvStepperDelayValue.text = "$delayMin - $delayMax"
            }
        }

        findViewById<View>(R.id.btn_stepper_delay_plus).setOnClickListener {
            if (delayMax < 40) {
                delayMin += 2
                delayMax += 2
                tvStepperDelayValue.text = "$delayMin - $delayMax"
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
    }

    private fun setPlatformSelection(plat: String) {
        selectedPlatform = plat
        if (plat == "tiktok") {
            btnSegmentTiktok.setBackgroundResource(R.drawable.bg_pill_active)
            (btnSegmentTiktok.findViewById<TextView>(android.R.id.text1) ?: btnSegmentTiktok).findViewWithTag<TextView>("tag_txt")
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
    }

    private fun setupStateObservers() {
        // 1. Runner state
        lifecycleScope.launch {
            RunnerController.state.collectLatest { state ->
                when (state) {
                    RunnerState.IDLE, RunnerState.STOPPED -> {
                        dotHeroStatus.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#10B981"))
                        tvHeroTitle.text = "Đang sẵn sàng"
                        tvHeroSubtitle.text = "Nhấn START để bắt đầu auto"
                        btnDashStart.visibility = View.VISIBLE
                        boxRunningControls.visibility = View.GONE
                    }
                    RunnerState.RUNNING -> {
                        dotHeroStatus.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#10B981"))
                        tvHeroTitle.text = "Đang chạy chiến dịch"
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

        // 2. Runner stats
        lifecycleScope.launch {
            RunnerController.stats.collectLatest { stats ->
                val completed = stats.followed + stats.liked
                val failed = stats.skipped + stats.errors
                val total = completed + failed

                tvDashStatCompleted.text = completed.toString()
                tvDashStatFailed.text = failed.toString()
                tvDashStatTotal.text = total.toString()
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

    private fun checkPermissionsHealth() {
        val hasAcc = F4FAccessibilityService.isRunning()
        val hasOverlay = Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)

        if (!hasAcc) {
            tvHeroSubtitle.text = "Cần bật quyền Trợ Năng để tự động click"
        }
    }

    private fun startRunner() {
        if (!F4FAccessibilityService.isRunning()) {
            Toast.makeText(this, "Vui lòng cấp quyền Trợ Năng trước!", Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
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

        // Start floating widget if overlay granted
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)) {
            startService(Intent(this, FloatingWidgetService::class.java))
        }

        startTimeMs = System.currentTimeMillis()

        RunnerController.start(
            context = this,
            apiClient = apiClient,
            platform = selectedPlatform,
            accountId = selectedAccount.getId(),
            accountName = selectedAccount.getDisplayName(),
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
                getSharedPreferences("f4f_config", Context.MODE_PRIVATE).edit()
                    .putString("f4f_user", user)
                    .putString("f4f_pass", pass)
                    .apply()

                tvSettingsUsername.text = data.user.username ?: user
                tvSettingsUserid.text = "ID: ${data.user.id ?: "F4F"}"
                tvTiktokConnStatus.text = "Đã kết nối"
                tvInstagramConnStatus.text = "Đã kết nối"

                RunnerController.addLog(LogLevel.SUCCESS, "Đăng nhập thành công: @${data.user.username}")
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
        val pass = prefs.getString("f4f_pass", "") ?: ""
        if (user.isNotEmpty() && pass.isNotEmpty()) {
            performLogin(user, pass)
        }
    }
}
