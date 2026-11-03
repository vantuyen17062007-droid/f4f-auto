package com.f4f.autorunner

import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.f4f.autorunner.api.F4FApiClient
import com.f4f.autorunner.api.SocialAccount
import com.f4f.autorunner.engine.AutoJobEngine
import com.f4f.autorunner.service.F4FAccessibilityService
import com.f4f.autorunner.service.FloatingWidgetService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private val apiClient = F4FApiClient()
    private var engine: AutoJobEngine? = null
    private var accounts: List<SocialAccount> = emptyList()

    private lateinit var tvTerminalLogs: TextView
    private lateinit var scrollLogs: ScrollView
    private lateinit var etF4fUser: EditText
    private lateinit var etF4fPass: EditText
    private lateinit var spAccounts: Spinner
    private lateinit var rgPlatform: RadioGroup
    private lateinit var rbTiktok: RadioButton
    private lateinit var rbInstagram: RadioButton
    private lateinit var btnStart: Button
    private lateinit var boxProfileInfo: View
    private lateinit var tvProfileName: TextView
    private lateinit var tvProfileBalance: TextView

    private lateinit var dotAccessibility: TextView
    private lateinit var tvStatusAccessibility: TextView
    private lateinit var dotOverlay: TextView
    private lateinit var tvStatusOverlay: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initViews()
        setupListeners()
    }

    override fun onResume() {
        super.onResume()
        updatePermissionStatus()
    }

    private fun initViews() {
        tvTerminalLogs = findViewById(R.id.tv_terminal_logs)
        scrollLogs = findViewById(R.id.scroll_logs)
        etF4fUser = findViewById(R.id.et_f4f_user)
        etF4fPass = findViewById(R.id.et_f4f_pass)
        spAccounts = findViewById(R.id.sp_accounts)
        rgPlatform = findViewById(R.id.rg_platform)
        rbTiktok = findViewById(R.id.rb_tiktok)
        rbInstagram = findViewById(R.id.rb_instagram)
        btnStart = findViewById(R.id.btn_start)
        boxProfileInfo = findViewById(R.id.box_profile_info)
        tvProfileName = findViewById(R.id.tv_profile_name)
        tvProfileBalance = findViewById(R.id.tv_profile_balance)

        dotAccessibility = findViewById(R.id.dot_accessibility)
        tvStatusAccessibility = findViewById(R.id.tv_status_accessibility)
        dotOverlay = findViewById(R.id.dot_overlay)
        tvStatusOverlay = findViewById(R.id.tv_status_overlay)
    }

    private fun setupListeners() {
        findViewById<View>(R.id.btn_toggle_accessibility).setOnClickListener {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            startActivity(intent)
        }

        findViewById<View>(R.id.btn_toggle_overlay).setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName")
                )
                startActivity(intent)
            } else {
                Toast.makeText(this, "Quyền bong bóng nổi đã được cấp!", Toast.LENGTH_SHORT).show()
            }
        }

        findViewById<Button>(R.id.btn_login).setOnClickListener {
            val user = etF4fUser.text.toString().trim()
            val pass = etF4fPass.text.toString().trim()

            if (user.isEmpty() || pass.isEmpty()) {
                Toast.makeText(this, "Vui lòng nhập Username và Mật khẩu F4F", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            log("⏳ Đang kết nối máy chủ Follow4Follow...")
            lifecycleScope.launch {
                try {
                    val loginData = apiClient.login(user, pass)

                    boxProfileInfo.visibility = View.VISIBLE
                    tvProfileName.text = "@${loginData.user.username}"
                    tvProfileBalance.text = "🪙 ${loginData.user.getDisplayBalance()}"

                    log("✓ Đăng nhập thành công: @${loginData.user.username} | Số dư: ${loginData.user.getDisplayBalance()}")

                    loadAccounts()
                } catch (e: Exception) {
                    log("❌ Đăng nhập thất bại: ${e.message}")
                    Toast.makeText(this@MainActivity, "Lỗi đăng nhập: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }

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

        btnStart.setOnClickListener {
            if (engine?.isRunning == true) {
                stopAuto()
            } else {
                startAuto()
            }
        }

        findViewById<TextView>(R.id.btn_clear_log).setOnClickListener {
            tvTerminalLogs.text = "[System] Nhật ký đã được làm sạch.\n"
        }
    }

    private fun updatePermissionStatus() {
        val hasAccessibility = F4FAccessibilityService.isRunning()
        dotAccessibility.backgroundTintList = ColorStateList.valueOf(
            if (hasAccessibility) Color.parseColor("#10B981") else Color.parseColor("#EF4444")
        )
        tvStatusAccessibility.text = if (hasAccessibility) "Trợ năng: BẬT" else "Trợ năng: TẮT"

        val hasOverlay = Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)
        dotOverlay.backgroundTintList = ColorStateList.valueOf(
            if (hasOverlay) Color.parseColor("#10B981") else Color.parseColor("#EF4444")
        )
        tvStatusOverlay.text = if (hasOverlay) "Bong bóng: ĐÃ CẤP" else "Bong bóng: CHƯA"
    }

    private suspend fun loadAccounts() {
        val platform = getSelectedPlatform()
        try {
            accounts = apiClient.getAccounts(platform)
            val names = accounts.map { "@${it.username ?: it.name} (${it.status ?: "Hoạt động"})" }

            val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, names)
            spAccounts.adapter = adapter
            log("✓ Đã tải ${accounts.size} tài khoản liên kết [$platform].")
        } catch (e: Exception) {
            log("❌ Lỗi tải danh sách tài khoản: ${e.message}")
        }
    }

    private fun startAuto() {
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
            Toast.makeText(this, "Chưa có tài khoản mạng xã hội nào được chọn!", Toast.LENGTH_SHORT).show()
            return
        }

        val platform = getSelectedPlatform()
        val selectedIdx = spAccounts.selectedItemPosition.coerceAtLeast(0)
        val selectedAccount = accounts[selectedIdx]

        val maxJobs = findViewById<EditText>(R.id.et_max_jobs).text.toString().toIntOrNull() ?: 50
        val accName = selectedAccount.username ?: selectedAccount.name ?: ""

        // Khởi động bong bóng nổi nếu có quyền
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(this)) {
            startService(Intent(this, FloatingWidgetService::class.java))
        }

        engine = AutoJobEngine(
            context = this,
            apiClient = apiClient,
            platform = platform,
            accountId = selectedAccount.id,
            accountName = accName,
            maxJobs = maxJobs,
            onLog = { msg ->
                lifecycleScope.launch(Dispatchers.Main) {
                    log(msg)
                }
            },
            onStatsUpdated = { stats ->
                lifecycleScope.launch(Dispatchers.Main) {
                    FloatingWidgetService.updateStatus("Xu: +${stats.coinsEarned} | Follow: ${stats.followed}")
                }
            }
        )

        engine?.start()
        btnStart.text = "⏹ DỪNG LẠI"
        btnStart.setBackgroundResource(R.drawable.bg_btn_danger)
        btnStart.setTextColor(Color.WHITE)
    }

    private fun stopAuto() {
        engine?.stop()
        btnStart.text = "🚀 BẮT ĐẦU CHẠY AUTO"
        btnStart.setBackgroundResource(R.drawable.bg_btn_primary)
        btnStart.setTextColor(Color.parseColor("#05080E"))
        stopService(Intent(this, FloatingWidgetService::class.java))
    }

    private fun getSelectedPlatform(): String {
        return if (findViewById<RadioButton>(R.id.rb_instagram).isChecked) "instagram" else "tiktok"
    }

    private fun log(message: String) {
        val current = tvTerminalLogs.text.toString()
        val lines = current.lines()
        val trimmed = if (lines.size > 250) lines.takeLast(120).joinToString("\n") else current
        tvTerminalLogs.text = "$trimmed\n$message"

        scrollLogs.post {
            scrollLogs.fullScroll(View.FOCUS_DOWN)
        }
    }
}
