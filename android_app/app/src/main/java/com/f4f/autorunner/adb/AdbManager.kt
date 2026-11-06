package com.f4f.autorunner.adb

import android.content.Context
import android.os.Build
import android.util.DisplayMetrics
import android.util.Log
import android.view.WindowManager
import dadb.AdbKeyPair
import dadb.Dadb
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

object AdbManager {

    private const val TAG = "AdbManager"

    private var dadbInstance: Dadb? = null
    var isUsingRoot: Boolean = false
        private set

    var isConnected: Boolean = false
        private set

    var wasEverConnected: Boolean = false
        private set

    var lastConnectedTime: String = ""
        private set

    var host: String = "127.0.0.1"
    var port: Int = 5555

    // Tọa độ màn hình thực tế (tự động nhận diện)
    var screenWidth: Int = 720
        private set
    var screenHeight: Int = 1600
        private set

    private val _connectionState = MutableStateFlow(false)
    val connectionState: StateFlow<Boolean> = _connectionState.asStateFlow()

    fun init(context: Context) {
        val prefs = context.getSharedPreferences("adb_config", Context.MODE_PRIVATE)
        host = prefs.getString("adb_host", "127.0.0.1") ?: "127.0.0.1"
        port = prefs.getInt("adb_port", 5555)
        wasEverConnected = prefs.getBoolean("adb_was_connected", false)
        lastConnectedTime = prefs.getString("adb_last_time", "") ?: ""

        initScreenDimensions(context)
    }

    fun initScreenDimensions(context: Context) {
        try {
            val wm = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
            val metrics = DisplayMetrics()
            @Suppress("DEPRECATION")
            wm.defaultDisplay.getRealMetrics(metrics)
            if (metrics.widthPixels > 0 && metrics.heightPixels > 0) {
                screenWidth = metrics.widthPixels
                screenHeight = metrics.heightPixels
                Log.i(TAG, "Screen dimensions detected: ${screenWidth}x${screenHeight}")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Could not get screen dimensions: ${e.message}")
        }
    }

    suspend fun connect(
        context: Context,
        targetHost: String = host,
        targetPort: Int = port
    ): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        host = targetHost
        port = targetPort
        disconnect()
        initScreenDimensions(context)

        // 1. Kiểm tra quyền Root (su) an toàn với timeout 2.5s
        if (checkRoot()) {
            isUsingRoot = true
            isConnected = true
            wasEverConnected = true
            lastConnectedTime = SimpleDateFormat("HH:mm dd/MM", Locale.getDefault()).format(Date())
            savePrefs(context)
            _connectionState.value = true
            Log.i(TAG, "Kết nối ADB qua Root (su) thành công!")
            return@withContext Pair(true, "Kết nối ADB thành công qua Root (su)!")
        }

        // 2. Kết nối qua Dadb TCP Socket
        try {
            val keyDir = File(context.filesDir, "adb")
            keyDir.mkdirs()
            val priv = File(keyDir, "adbkey")
            val pub = File(keyDir, "adbkey.pub")
            if (!priv.exists() || !pub.exists()) {
                AdbKeyPair.generate(priv, pub)
            }
            val keyPair = AdbKeyPair.read(priv, pub)
            val d = Dadb.create(host, port, keyPair)

            // Vòng lặp chờ phản hồi / popup RSA authorization nếu kết nối lần đầu (tối đa 10s)
            var isAuthOk = false
            var lastErr = ""
            for (attempt in 1..8) {
                try {
                    val res = d.shell("echo ok_f4f")
                    if (res.allOutput.contains("ok_f4f")) {
                        isAuthOk = true
                        break
                    }
                } catch (e: Exception) {
                    lastErr = e.message ?: ""
                    delay(1200)
                }
            }

            if (isAuthOk) {
                dadbInstance = d
                isUsingRoot = false
                isConnected = true
                wasEverConnected = true
                lastConnectedTime = SimpleDateFormat("HH:mm dd/MM", Locale.getDefault()).format(Date())
                savePrefs(context)
                _connectionState.value = true
                Log.i(TAG, "Kết nối ADB Socket $host:$port thành công!")
                return@withContext Pair(true, "Kết nối ADB thành công ($host:$port)!")
            } else {
                try { d.close() } catch (_: Exception) {}
                val msg = if (lastErr.contains("closed", ignoreCase = true) || lastErr.contains("auth", ignoreCase = true)) {
                    "Cần chấp nhận RSA: Vui lòng để ý hộp thoại 'Cho phép gỡ lỗi USB' trên màn hình và chọn Luôn cho phép."
                } else {
                    "Không nhận được phản hồi từ $host:$port ($lastErr). Hãy kiểm tra lại số Cổng (Port)."
                }
                return@withContext Pair(false, msg)
            }
        } catch (e: Exception) {
            isConnected = false
            _connectionState.value = false
            val msg = e.message ?: "Lỗi kết nối socket"
            Log.e(TAG, "Lỗi kết nối ADB: $msg", e)
            val friendlyMsg = if (msg.contains("Connection refused", ignoreCase = true)) {
                "Cổng $port đang đóng! Nếu dùng Gỡ lỗi qua Wi-Fi, hãy nhập đúng số Port hiển thị trong Cài đặt nhà phát triển."
            } else {
                "Lỗi kết nối ADB: $msg"
            }
            return@withContext Pair(false, friendlyMsg)
        }
    }

    fun disconnect() {
        try {
            dadbInstance?.close()
        } catch (_: Exception) {}
        dadbInstance = null
        isUsingRoot = false
        isConnected = false
        _connectionState.value = false
    }

    private fun checkRoot(): Boolean {
        return try {
            val p = Runtime.getRuntime().exec(arrayOf("su", "-c", "id"))
            val finished = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                p.waitFor(2500, TimeUnit.MILLISECONDS)
            } else {
                p.waitFor()
                true
            }
            if (!finished) {
                p.destroy()
                return false
            }
            val output = p.inputStream.bufferedReader().readLine()
            output?.contains("uid=0") == true
        } catch (_: Exception) {
            false
        }
    }

    private fun runRootCommand(cmd: String, timeoutSec: Long = 6): String {
        val p = Runtime.getRuntime().exec(arrayOf("su", "-c", cmd))
        val stdout = StringBuilder()
        val reader = BufferedReader(InputStreamReader(p.inputStream))

        val readThread = Thread {
            try {
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    stdout.append(line).append("\n")
                }
            } catch (_: Exception) {}
        }
        readThread.start()

        val finished = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            p.waitFor(timeoutSec, TimeUnit.SECONDS)
        } else {
            p.waitFor()
            true
        }
        readThread.join(500)

        if (!finished) {
            p.destroy()
            throw RuntimeException("Root command timed out ($timeoutSec s): $cmd")
        }
        return stdout.toString().trim()
    }

    private fun savePrefs(context: Context) {
        context.getSharedPreferences("adb_config", Context.MODE_PRIVATE).edit()
            .putString("adb_host", host)
            .putInt("adb_port", port)
            .putBoolean("adb_was_connected", wasEverConnected)
            .putString("adb_last_time", lastConnectedTime)
            .apply()
    }

    suspend fun shell(cmd: String): String = withContext(Dispatchers.IO) {
        if (!isConnected) {
            throw IllegalStateException("Chưa kết nối ADB!")
        }

        if (isUsingRoot) {
            return@withContext runRootCommand(cmd)
        }

        val d = dadbInstance ?: throw IllegalStateException("ADB Socket không khả dụng!")
        return@withContext try {
            val res = d.shell(cmd)
            res.allOutput
        } catch (e: Exception) {
            // Thử một lần gửi lại nếu socket bị ngắt tạm thời
            Log.w(TAG, "Socket command error: ${e.message}, retrying once...")
            val res = d.shell(cmd)
            res.allOutput
        }
    }

    suspend fun tap(x: Int, y: Int) {
        shell("input tap $x $y")
    }

    suspend fun doubleTap(x: Int, y: Int, intervalMs: Long = 120) {
        val sec = String.format(Locale.US, "%.2f", intervalMs / 1000.0)
        shell("input tap $x $y && sleep $sec && input tap $x $y")
    }

    suspend fun likeCenter() {
        val cx = screenWidth / 2
        val cy = (screenHeight * 0.45).toInt()
        doubleTap(cx, cy)
    }

    suspend fun followTikTokHeuristic() {
        // Nút Follow chuẩn TikTok nằm lệch trái một chút hoặc giữa, khoảng 30% chiều cao màn hình
        val cx = (screenWidth * 0.38).toInt()
        val cy = (screenHeight * 0.30).toInt()
        tap(cx, cy)
    }

    suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int = 300) {
        shell("input swipe $x1 $y1 $x2 $y2 $durationMs")
    }

    suspend fun swipeFeed() {
        val cx = screenWidth / 2
        val startY = (screenHeight * 0.75).toInt()
        val endY = (screenHeight * 0.25).toInt()
        swipe(cx, startY, cx, endY, 320)
    }

    suspend fun keyevent(keyCode: Int) {
        shell("input keyevent $keyCode")
    }

    suspend fun openUrl(url: String, packageName: String? = null) {
        val pkgArg = if (!packageName.isNullOrBlank()) " -p $packageName" else ""
        shell("am start -a android.intent.action.VIEW -d \"$url\"$pkgArg")
    }

    suspend fun dumpUiXml(): String = withContext(Dispatchers.IO) {
        return@withContext try {
            // Dùng /data/local/tmp và cờ --compressed để dump cực nhanh và không dính Scoped Storage
            val out = shell("uiautomator dump --compressed /data/local/tmp/f4f_dump.xml && cat /data/local/tmp/f4f_dump.xml")
            if (out.contains("<node")) {
                val startIdx = out.indexOf("<?xml")
                if (startIdx >= 0) out.substring(startIdx) else out
            } else {
                ""
            }
        } catch (e: Exception) {
            Log.w(TAG, "Lỗi dump UI XML: ${e.message}")
            ""
        }
    }
}
