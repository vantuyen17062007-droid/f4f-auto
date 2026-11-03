package com.f4f.autorunner

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
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
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private val apiClient = F4FApiClient()
    private var engine: AutoJobEngine? = null
    private var accounts: List<SocialAccount> = emptyList()

    private lateinit var tvTerminalLogs: TextView
    private lateinit var tvAccountInfo: TextView
    private lateinit var etF4fUser: EditText
    private lateinit var etF4fPass: EditText
    private lateinit var spAccounts: Spinner
    private lateinit var rgPlatform: RadioGroup
    private lateinit var btnStart: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initViews()
        setupListeners()
    }

    private fun initViews() {
        tvTerminalLogs = findViewById(R.id.tv_terminal_logs)
        tvAccountInfo = findViewById(R.id.tv_account_info)
        etF4fUser = findViewById(R.id.et_f4f_user)
        etF4fPass = findViewById(R.id.et_f4f_pass)
        spAccounts = findViewById(R.id.sp_accounts)
        rgPlatform = findViewById(R.id.rg_platform)
        btnStart = findViewById(R.id.btn_start)

        findViewById<Button>(R.id.btn_enable_accessibility).setOnClickListener {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            startActivity(intent)
        }

        findViewById<Button>(R.id.btn_enable_overlay).setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName")
                )
                startActivity(intent)
            } else {
                Toast.makeText(this, "Đã có quyền cửa sổ nổi!", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun setupListeners() {
        findViewById<Button>(R.id.btn_login).setOnClickListener {
            val user = etF4fUser.text.toString().trim()
            val pass = etF4fPass.text.toString().trim()

            if (user.isEmpty() || pass.isEmpty()) {
                Toast.makeText(this, "Vui lòng nhập Username và Password", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            log("Đang đăng nhập Follow4Follow...")
            lifecycleScope.launch {
                try {
                    val loginData = apiClient.login(user, pass)
                    tvAccountInfo.text = "✓ @${loginData.user.username} | Số dư: ${loginData.user.balance} xu"
                    log("✓ Đăng nhập thành công! Số dư: ${loginData.user.balance} xu")

                    loadAccounts()
                } catch (e: Exception) {
                    log("❌ Lỗi đăng nhập: ${e.message}")
                    Toast.makeText(this@MainActivity, "Đăng nhập thất bại: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }

        rgPlatform.setOnCheckedChangeListener { _, _ ->
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
    }

    private suspend fun loadAccounts() {
        val platform = getSelectedPlatform()
        try {
            accounts = apiClient.getAccounts(platform)
            val names = accounts.map { "@${it.username ?: it.name} (${it.status ?: "Hoạt động"})" }

            val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, names)
            spAccounts.adapter = adapter
            log("✓ Đã tải ${accounts.size} tài khoản $platform.")
        } catch (e: Exception) {
            log("❌ Lỗi tải danh sách tài khoản: ${e.message}")
        }
    }

    private fun startAuto() {
        if (!F4FAccessibilityService.isRunning()) {
            Toast.makeText(this, "Vui lòng bật Dịch vụ Trợ Năng trước!", Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return
        }

        if (apiClient.token == null) {
            Toast.makeText(this, "Vui lòng đăng nhập tài khoản F4F trước!", Toast.LENGTH_SHORT).show()
            return
        }

        if (accounts.isEmpty()) {
            Toast.makeText(this, "Không có tài khoản liên kết nào để chạy!", Toast.LENGTH_SHORT).show()
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
                    FloatingWidgetService.updateStatus("Xu: ${stats.coinsEarned} | Follow: ${stats.followed}")
                }
            }
        )

        engine?.start()
        btnStart.text = "DỪNG LẠI"
        btnStart.setBackgroundColor(getColor(R.color.error))
    }

    private fun stopAuto() {
        engine?.stop()
        btnStart.text = "BẮT ĐẦU CHẠY AUTO"
        btnStart.setBackgroundColor(getColor(R.color.primary))
        stopService(Intent(this, FloatingWidgetService::class.java))
    }

    private fun getSelectedPlatform(): String {
        return if (findViewById<RadioButton>(R.id.rb_instagram).isChecked) "instagram" else "tiktok"
    }

    private fun log(message: String) {
        val current = tvTerminalLogs.text.toString()
        val lines = current.lines()
        val trimmed = if (lines.size > 200) lines.takeLast(100).joinToString("\n") else current
        tvTerminalLogs.text = "$trimmed\n$message"
    }
}
