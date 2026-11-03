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
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private val apiClient = F4FApiClient()
    private var accounts: List<SocialAccount> = emptyList()
    private var baseCoins = 0
    private var activeLogFilter: LogLevel? = null

    // Tabs
    private lateinit var viewDashboard: View
    private lateinit var viewTasks: View
    private lateinit var viewLogs: View
    private lateinit var viewSettings: View
    private lateinit var bottomNav: BottomNavigationView

    // Dashboard Views
    private lateinit var dotAccessibility: TextView
    private lateinit var tvAccessibility: TextView
    private lateinit var dotOverlay: TextView
    private lateinit var tvOverlay: TextView
    private lateinit var boxLoginForm: View
    private lateinit var boxProfileInfo: View
    private lateinit var etF4fUser: EditText
    private lateinit var etF4fPass: EditText
    private lateinit var tvProfileName: TextView
    private lateinit var tvProfileBalance: TextView
    private lateinit var tvStatFollowed: TextView
    private lateinit var tvStatLiked: TextView
    private lateinit var tvStatCoins: TextView
    private lateinit var tvStatSkipped: TextView
    private lateinit var btnDashStart: Button
    private lateinit var boxRunningControls: View
    private lateinit var btnDashPause: Button
    private lateinit var btnDashStop: Button

    // Tasks Views
    private lateinit var rgPlatform: RadioGroup
    private lateinit var rbTiktok: RadioButton
    private lateinit var rbInstagram: RadioButton
    private lateinit var spAccounts: Spinner
    private lateinit var etMaxJobs: EditText
    private lateinit var etDelay: EditText
    private lateinit var cbAntiBan: CheckBox
    private lateinit var cbFloatingWidget: CheckBox

    // Logs Views
    private lateinit var tvTerminalLogs: TextView
    private lateinit var scrollLogs: ScrollView
    private lateinit var filterAll: TextView
    private lateinit var filterSuccess: TextView
    private lateinit var filterWarn: TextView
    private lateinit var filterError: TextView

    // Settings Views
    private lateinit var tvSettingsUserStatus: TextView
    private lateinit var btnLogout: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initViews()
        setupBottomNav()
        setupListeners()
        setupStateObservers()
        loadSavedCredentials()
    }

    override fun onResume() {
        super.onResume()
        updatePermissionStatus()
    }

    private fun initViews() {
        // Tab containers
        viewDashboard = findViewById(R.id.view_dashboard)
        viewTasks = findViewById(R.id.view_tasks)
        viewLogs = findViewById(R.id.view_logs)
        viewSettings = findViewById(R.id.view_settings)
        bottomNav = findViewById(R.id.bottom_navigation)

        // Dashboard
        dotAccessibility = findViewById(R.id.dot_dash_accessibility)
        tvAccessibility = findViewById(R.id.tv_dash_accessibility)
        dotOverlay = findViewById(R.id.dot_dash_overlay)
        tvOverlay = findViewById(R.id.tv_dash_overlay)
        boxLoginForm = findViewById(R.id.box_login_form)
        boxProfileInfo = findViewById(R.id.box_profile_info)
        etF4fUser = findViewById(R.id.et_f4f_user)
        etF4fPass = findViewById(R.id.et_f4f_pass)
        tvProfileName = findViewById(R.id.tv_profile_name)
        tvProfileBalance = findViewById(R.id.tv_profile_balance)
        tvStatFollowed = findViewById(R.id.tv_stat_followed)
        tvStatLiked = findViewById(R.id.tv_stat_liked)
        tvStatCoins = findViewById(R.id.tv_stat_coins)
        tvStatSkipped = findViewById(R.id.tv_stat_skipped)
        btnDashStart = findViewById(R.id.btn_dash_start)
        boxRunningControls = findViewById(R.id.box_running_controls)
        btnDashPause = findViewById(R.id.btn_dash_pause)
        btnDashStop = findViewById(R.id.btn_dash_stop)

        // Tasks
        rgPlatform = findViewById(R.id.rg_platform)
        rbTiktok = findViewById(R.id.rb_tiktok)
        rbInstagram = findViewById(R.id.rb_instagram)
        spAccounts = findViewById(R.id.sp_accounts)
        etMaxJobs = findViewById(R.id.et_max_jobs)
        etDelay = findViewById(R.id.et_delay)
        cbAntiBan = findViewById(R.id.cb_antiban)
        cbFloatingWidget = findViewById(R.id.cb_floating_widget)

        // Logs
        tvTerminalLogs = findViewById(R.id.tv_terminal_logs)
        scrollLogs = findViewById(R.id.scroll_logs)
        filterAll = findViewById(R.id.filter_all)
        filterSuccess = findViewById(R.id.filter_success)
        filterWarn = findViewById(R.id.filter_warn)
        filterError = findViewById(R.id.filter_error)

        // Settings
        tvSettingsUserStatus = findViewById(R.id.tv_settings_user_status)
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
        // Cấp quyền
        findViewById<View>(R.id.btn_dash_accessibility).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        findViewById<View>(R.id.btn_dash_overlay).setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                startActivity(
                    Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
                )
            } else {
                Toast.makeText(this, "Quyền bong bóng nổi đã được cấp!", Toast.LENGTH_SHORT).show()
            }
        }

        // Đăng nhập F4F
        findViewById<Button>(R.id.btn_login).setOnClickListener {
            val user = etF4fUser.text.toString().trim()
            val pass = etF4fPass.text.toString().trim()

            if (user.isEmpty() || pass.isEmpty()) {
                Toast.makeText(this, "Vui lòng nhập Username và Mật khẩu F4F", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            RunnerController.addLog(LogLevel.INFO, "Đang kết nối máy chủ Follow4Follow...")
            lifecycleScope.launch {
                try {
                    val loginData = apiClient.login(user, pass)
                    saveCredentials(user, pass)

                    baseCoins = loginData.user.getNumericBalance()
                    updateUiForLoggedIn(loginData.user.username ?: user, loginData.user.getDisplayBalance())

                    RunnerController.addLog(
                        LogLevel.SUCCESS,
                        "Đăng nhập thành công: @${loginData.user.username} (Số dư: ${loginData.user.getDisplayBalance()})"
                    )

                    loadAccounts()
                } catch (e: Exception) {
                    RunnerController.addLog(LogLevel.ERROR, "Đăng nhập thất bại: ${e.message}")
                    Toast.makeText(this@MainActivity, "Lỗi đăng nhập: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }

        // Đăng xuất
        btnLogout.setOnClickListener {
            clearSavedCredentials()
            apiClient.token = null
            apiClient.user = null
            boxLoginForm.visibility = View.VISIBLE
            boxProfileInfo.visibility = View.GONE
            tvSettingsUserStatus.text = "Chưa đăng nhập tài khoản Follow4Follow"
            spAccounts.adapter = null
            accounts = emptyList()
            RunnerController.stop()
            Toast.makeText(this, "Đã đăng xuất khỏi F4F", Toast.LENGTH_SHORT).show()
        }

        // Chuyển nền tảng TikTok / Instagram
        rgPlatform.setOnCheckedChangeListener { _, checkedId ->
            if (checkedId == R.id.rb_tiktok) {
                rbTiktok.setBackgroundResource(R.drawable.bg_input_field)
                rbInstagram.background = null
            } else {
                rbInstagram.setBackgroundResource(R.drawable.bg_input_field)
                rbTiktok.background = null
            }

            if (apiClient.token != null) {
                lifecycleScope.launch { loadAccounts() }
            }
        }

        // Các nút điều khiển chính
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

        // Bộ lọc logs
        filterAll.setOnClickListener { setLogFilter(null, it) }
        filterSuccess.setOnClickListener { setLogFilter(LogLevel.SUCCESS, it) }
        filterWarn.setOnClickListener { setLogFilter(LogLevel.WARN, it) }
        filterError.setOnClickListener { setLogFilter(LogLevel.ERROR, it) }

        // Sao chép logs
        findViewById<View>(R.id.btn_copy_log).setOnClickListener {
            val fullLogs = RunnerController.logs.value.joinToString("\n") {
                "[${it.timestamp}] [${it.level}] ${it.message}"
            }
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            clipboard.setPrimaryClip(ClipData.newPlainText("F4F Logs", fullLogs))
            Toast.makeText(this, "Đã sao chép toàn bộ nhật ký vào bộ nhớ tạm", Toast.LENGTH_SHORT).show()
        }

        // Xóa logs
        findViewById<View>(R.id.btn_clear_log).setOnClickListener {
            RunnerController.clearLogs()
        }
    }

    private fun setupStateObservers() {
        // 1. Quan sát trạng thái Running / Paused / Stopped
        lifecycleScope.launch {
            RunnerController.state.collectLatest { state ->
                when (state) {
                    RunnerState.IDLE, RunnerState.STOPPED -> {
                        btnDashStart.visibility = View.VISIBLE
                        boxRunningControls.visibility = View.GONE
                        btnDashStart.text = "🚀 BẮT ĐẦU CHẠY AUTO"
                        btnDashStart.setBackgroundResource(R.drawable.bg_btn_primary)
                        btnDashStart.setTextColor(Color.parseColor("#05080E"))
                    }
                    RunnerState.RUNNING -> {
                        btnDashStart.visibility = View.GONE
                        boxRunningControls.visibility = View.VISIBLE
                        btnDashPause.text = "⏸ Tạm dừng"
                        btnDashPause.setTextColor(Color.parseColor("#F59E0B"))
                    }
                    RunnerState.PAUSED -> {
                        btnDashStart.visibility = View.GONE
                        boxRunningControls.visibility = View.VISIBLE
                        btnDashPause.text = "▶ Tiếp tục"
                        btnDashPause.setTextColor(Color.parseColor("#10B981"))
                    }
                }
            }
        }

        // 2. Quan sát thống kê Realtime
        lifecycleScope.launch {
            RunnerController.stats.collectLatest { stats ->
                tvStatFollowed.text = stats.followed.toString()
                tvStatLiked.text = stats.liked.toString()
                tvStatCoins.text = "+${stats.coinsEarned}"
                tvStatSkipped.text = (stats.skipped + stats.errors).toString()

                val currentCoins = baseCoins + stats.coinsEarned
                tvProfileBalance.text = "🪙 $currentCoins xu (+${stats.coinsEarned})"
            }
        }

        // 3. Quan sát nhật ký (Logs)
        lifecycleScope.launch {
            RunnerController.logs.collectLatest { logs ->
                renderLogs(logs)
            }
        }
    }

    private fun startRunner() {
        if (!F4FAccessibilityService.isRunning()) {
            Toast.makeText(this, "Vui lòng bật quyền Trợ Năng trước!", Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return
        }

        if (apiClient.token == null) {
            Toast.makeText(this, "Vui lòng đăng nhập tài khoản Follow4Follow trước!", Toast.LENGTH_SHORT).show()
            return
        }

        if (accounts.isEmpty()) {
            Toast.makeText(this, "Chưa có tài khoản MXH nào được chọn!", Toast.LENGTH_SHORT).show()
            return
        }

        val platform = if (rbInstagram.isChecked) "instagram" else "tiktok"
        val selectedIdx = spAccounts.selectedItemPosition.coerceAtLeast(0)
        val selectedAccount = accounts.getOrNull(selectedIdx) ?: accounts[0]

        val maxJobs = etMaxJobs.text.toString().trim().toIntOrNull() ?: 50
        val accName = selectedAccount.getDisplayName()

        // Phân tích delay an toàn
        val delayText = etDelay.text.toString().trim()
        var delayMin = 8
        var delayMax = 18
        if (delayText.isNotEmpty()) {
            if (delayText.contains("-")) {
                val parts = delayText.split("-")
                delayMin = parts[0].trim().toIntOrNull() ?: 8
                delayMax = parts.getOrNull(1)?.trim()?.toIntOrNull() ?: (delayMin + 5)
            } else {
                delayMin = delayText.toIntOrNull() ?: 8
                delayMax = delayMin + 4
            }
        }
        if (delayMin < 3) delayMin = 3
        if (delayMax < delayMin) delayMax = delayMin + 3

        // Khởi động bong bóng nổi nếu được bật
        if (cbFloatingWidget.isChecked) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)) {
                startService(Intent(this, FloatingWidgetService::class.java))
            }
        }

        val antiBanScrolls = if (cbAntiBan.isChecked) 2 else 0

        RunnerController.start(
            context = this,
            apiClient = apiClient,
            platform = platform,
            accountId = selectedAccount.getId(),
            accountName = accName,
            maxJobs = maxJobs,
            delayMin = delayMin,
            delayMax = delayMax,
            antiBanScrollTimes = antiBanScrolls
        )
    }

    private fun setLogFilter(level: LogLevel?, view: View) {
        activeLogFilter = level
        val filters = listOf(filterAll, filterSuccess, filterWarn, filterError)
        for (f in filters) {
            f.setBackgroundColor(Color.TRANSPARENT)
            f.setTextColor(Color.parseColor("#94A3B8"))
        }
        (view as TextView).setBackgroundColor(Color.parseColor("#2B3B56"))
        view.setTextColor(Color.WHITE)
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
                LogLevel.INFO -> Color.parseColor("#00E5FF")
            }
            ssb.setSpan(ForegroundColorSpan(color), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }

        tvTerminalLogs.text = ssb
        scrollLogs.post { scrollLogs.fullScroll(View.FOCUS_DOWN) }
    }

    private fun updatePermissionStatus() {
        val hasAccessibility = F4FAccessibilityService.isRunning()
        dotAccessibility.backgroundTintList = ColorStateList.valueOf(
            if (hasAccessibility) Color.parseColor("#10B981") else Color.parseColor("#EF4444")
        )
        tvAccessibility.text = if (hasAccessibility) "Trợ năng: BẬT" else "Trợ năng: TẮT"

        val hasOverlay = Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)
        dotOverlay.backgroundTintList = ColorStateList.valueOf(
            if (hasOverlay) Color.parseColor("#10B981") else Color.parseColor("#EF4444")
        )
        tvOverlay.text = if (hasOverlay) "Bong bóng: ĐÃ CẤP" else "Bong bóng: CHƯA"
    }

    private suspend fun loadAccounts() {
        val platform = if (rbInstagram.isChecked) "instagram" else "tiktok"
        try {
            accounts = apiClient.getAccounts(platform)
            val names = if (accounts.isEmpty()) {
                listOf("(Chưa có nick $platform nào trên F4F)")
            } else {
                accounts.map { "@${it.getDisplayName()} (${it.status ?: "Hoạt động"})" }
            }

            val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, names)
            spAccounts.adapter = adapter
            RunnerController.addLog(LogLevel.INFO, "Đã tải ${accounts.size} tài khoản [$platform] từ F4F.")
        } catch (e: Exception) {
            RunnerController.addLog(LogLevel.ERROR, "Lỗi tải tài khoản: ${e.message}")
        }
    }

    private fun updateUiForLoggedIn(username: String, balance: String) {
        boxLoginForm.visibility = View.GONE
        boxProfileInfo.visibility = View.VISIBLE
        tvProfileName.text = "@$username"
        tvProfileBalance.text = "🪙 $balance"
        tvSettingsUserStatus.text = "Đang đăng nhập tài khoản F4F: @$username"
    }

    private fun loadSavedCredentials() {
        val prefs = getSharedPreferences("f4f_config", Context.MODE_PRIVATE)
        val user = prefs.getString("f4f_user", "") ?: ""
        val pass = prefs.getString("f4f_pass", "") ?: ""
        if (user.isNotEmpty()) etF4fUser.setText(user)
        if (pass.isNotEmpty()) etF4fPass.setText(pass)
    }

    private fun saveCredentials(user: String, pass: String) {
        val prefs = getSharedPreferences("f4f_config", Context.MODE_PRIVATE)
        prefs.edit()
            .putString("f4f_user", user)
            .putString("f4f_pass", pass)
            .apply()
    }

    private fun clearSavedCredentials() {
        val prefs = getSharedPreferences("f4f_config", Context.MODE_PRIVATE)
        prefs.edit().clear().apply()
        etF4fUser.setText("")
        etF4fPass.setText("")
    }
}
