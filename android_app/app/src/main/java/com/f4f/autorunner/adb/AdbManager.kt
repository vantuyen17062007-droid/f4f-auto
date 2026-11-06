package com.f4f.autorunner.adb

import android.content.Context
import android.util.Log
import dadb.AdbKeyPair
import dadb.Dadb
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object AdbManager {

    private const val TAG = "AdbManager"

    private var dadbInstance: Dadb? = null
    private var isUsingRoot: Boolean = false

    var isConnected: Boolean = false
        private set

    var wasEverConnected: Boolean = false
        private set

    var lastConnectedTime: String = ""
        private set

    var host: String = "127.0.0.1"
    var port: Int = 5555

    private val _connectionState = MutableStateFlow(false)
    val connectionState: StateFlow<Boolean> = _connectionState.asStateFlow()

    fun init(context: Context) {
        val prefs = context.getSharedPreferences("adb_config", Context.MODE_PRIVATE)
        host = prefs.getString("adb_host", "127.0.0.1") ?: "127.0.0.1"
        port = prefs.getInt("adb_port", 5555)
        wasEverConnected = prefs.getBoolean("adb_was_connected", false)
        lastConnectedTime = prefs.getString("adb_last_time", "") ?: ""
    }

    suspend fun connect(
        context: Context,
        targetHost: String = host,
        targetPort: Int = port
    ): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        host = targetHost
        port = targetPort
        disconnect()

        // 1. Kiểm tra quyền Root (su) trực tiếp
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

            // Kiểm tra lệnh test
            val res = d.shell("echo ok_f4f")
            if (res.allOutput.contains("ok_f4f")) {
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
                return@withContext Pair(false, "Không nhận được phản hồi: ${res.allOutput}")
            }
        } catch (e: Exception) {
            isConnected = false
            _connectionState.value = false
            Log.e(TAG, "Lỗi kết nối ADB: ${e.message}", e)
            return@withContext Pair(false, "Lỗi kết nối ADB: ${e.message ?: "Kiểm tra lại cổng"}")
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
            val p = Runtime.getRuntime().exec("su -c id")
            val output = p.inputStream.bufferedReader().readLine()
            p.waitFor()
            output?.contains("uid=0") == true
        } catch (_: Exception) {
            false
        }
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
            // Thử auto-connect lại nếu chưa kết nối
            throw IllegalStateException("Chưa kết nối ADB!")
        }

        if (isUsingRoot) {
            val p = Runtime.getRuntime().exec(arrayOf("su", "-c", cmd))
            val output = p.inputStream.bufferedReader().readText()
            p.waitFor()
            return@withContext output
        }

        val d = dadbInstance ?: throw IllegalStateException("ADB Socket không khả dụng!")
        val res = d.shell(cmd)
        return@withContext res.allOutput
    }

    suspend fun tap(x: Int, y: Int) {
        shell("input tap $x $y")
    }

    suspend fun doubleTap(x: Int, y: Int, intervalMs: Long = 120) {
        val sec = String.format(Locale.US, "%.2f", intervalMs / 1000.0)
        shell("input tap $x $y; sleep $sec; input tap $x $y")
    }

    suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int = 300) {
        shell("input swipe $x1 $y1 $x2 $y2 $durationMs")
    }

    suspend fun keyevent(keyCode: Int) {
        shell("input keyevent $keyCode")
    }

    suspend fun openUrl(url: String, packageName: String? = null) {
        val pkgArg = if (!packageName.isNullOrBlank()) " -p $packageName" else ""
        shell("am start -a android.intent.action.VIEW -d \"$url\"$pkgArg")
    }

    suspend fun dumpUiXml(): String {
        return try {
            shell("uiautomator dump /sdcard/f4f_dump.xml && cat /sdcard/f4f_dump.xml")
        } catch (e: Exception) {
            Log.e(TAG, "Lỗi dump UI XML: ${e.message}")
            ""
        }
    }
}
