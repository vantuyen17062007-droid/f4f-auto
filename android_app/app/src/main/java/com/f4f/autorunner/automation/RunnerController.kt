package com.f4f.autorunner.automation

import android.content.Context
import com.f4f.autorunner.data.api.F4FApiClient
import com.f4f.autorunner.model.LogEntry
import com.f4f.autorunner.model.LogLevel
import com.f4f.autorunner.model.RunnerState
import com.f4f.autorunner.model.RunnerStats
import com.f4f.autorunner.service.F4FAccessibilityService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

object RunnerController {

    private val _state = MutableStateFlow(RunnerState.IDLE)
    val state: StateFlow<RunnerState> = _state.asStateFlow()

    private val _stats = MutableStateFlow(RunnerStats())
    val stats: StateFlow<RunnerStats> = _stats.asStateFlow()

    private val _logs = MutableStateFlow<List<LogEntry>>(
        listOf(LogEntry(level = LogLevel.INFO, message = "Tn Tool sẵn sàng."))
    )
    val logs: StateFlow<List<LogEntry>> = _logs.asStateFlow()

    // Thông tin hiển thị trực tiếp lên Cửa sổ nổi (Floating Widget)
    private val _currentAccount = MutableStateFlow("")
    val currentAccount: StateFlow<String> = _currentAccount.asStateFlow()

    private val _currentPlatform = MutableStateFlow("tiktok")
    val currentPlatform: StateFlow<String> = _currentPlatform.asStateFlow()

    private val _currentJobInfo = MutableStateFlow("Sẵn sàng bắt đầu")
    val currentJobInfo: StateFlow<String> = _currentJobInfo.asStateFlow()

    fun updateJobInfo(info: String) {
        _currentJobInfo.value = info
    }

    private var activeEngine: AutoJobEngine? = null

    var sessionStartTimeMs: Long = 0L
        private set

    val isRunning: Boolean
        get() = _state.value == RunnerState.RUNNING

    val isPaused: Boolean
        get() = _state.value == RunnerState.PAUSED

    val isStoppedOrIdle: Boolean
        get() = _state.value == RunnerState.IDLE || _state.value == RunnerState.STOPPED

    @Synchronized
    fun start(
        context: Context,
        apiClient: F4FApiClient,
        platform: String,
        accountId: Long,
        accountName: String,
        jobType: String = "all",
        controlMode: String = "auto", // "auto" | "adb" | "accessibility"
        maxJobs: Int = 50,
        delayMin: Int = 8,
        delayMax: Int = 18,
        antiBanEveryNJobs: Int = 5,
        antiBanScrollTimes: Int = 2
    ) {
        if (_state.value == RunnerState.RUNNING) {
            return
        }

        stop() // Đảm bảo hủy triệt để engine cũ nếu có

        sessionStartTimeMs = System.currentTimeMillis()
        _state.value = RunnerState.RUNNING
        _stats.value = RunnerStats()
        _currentAccount.value = accountName
        _currentPlatform.value = platform
        _currentJobInfo.value = "Đang khởi động @$accountName..."
        addLog(LogLevel.INFO, "Khởi động chiến dịch [$platform] cho @$accountName...")
        F4FAccessibilityService.automationActive = true

        val appContext = context.applicationContext
        val engine = AutoJobEngine(
            context = appContext,
            apiClient = apiClient,
            platform = platform,
            accountId = accountId,
            accountName = accountName,
            jobType = jobType,
            controlMode = controlMode,
            maxJobs = maxJobs,
            delayMin = delayMin,
            delayMax = delayMax,
            antiBanEveryNJobs = antiBanEveryNJobs,
            antiBanScrollTimes = antiBanScrollTimes,
            onLog = { level, msg ->
                addLog(level, msg)
            },
            onJobInfo = { info ->
                _currentJobInfo.value = info
            },
            onStatsUpdated = { newStats ->
                _stats.value = newStats.copy()
            },
            onFinished = {
                _state.value = RunnerState.STOPPED
                F4FAccessibilityService.automationActive = false
                addLog(LogLevel.INFO, "Phiên chạy đã kết thúc.")
            }
        )

        activeEngine = engine
        engine.start()
    }

    @Synchronized
    fun pause() {
        if (_state.value == RunnerState.RUNNING) {
            _state.value = RunnerState.PAUSED
            activeEngine?.pause()
            F4FAccessibilityService.automationActive = false
            _currentJobInfo.value = "Đang tạm dừng..."
            addLog(LogLevel.WARN, "Đã tạm dừng (PAUSED). Nhấn Tiếp tục để chạy lại.")
        }
    }

    @Synchronized
    fun resume() {
        if (_state.value == RunnerState.PAUSED) {
            _state.value = RunnerState.RUNNING
            activeEngine?.resume()
            F4FAccessibilityService.automationActive = true
            _currentJobInfo.value = "Đã tiếp tục..."
            addLog(LogLevel.INFO, "Đã tiếp tục phiên chạy (RESUMED).")
        }
    }

    @Synchronized
    fun stop() {
        if (_state.value != RunnerState.STOPPED && _state.value != RunnerState.IDLE) {
            _state.value = RunnerState.STOPPED
            activeEngine?.stop()
            activeEngine = null
            F4FAccessibilityService.automationActive = false
            _currentJobInfo.value = "Đã dừng phiên chạy."
            addLog(LogLevel.WARN, "Đã dừng phiên chạy khẩn cấp (STOPPED).")
        }
    }

    @Synchronized
    fun addLog(level: LogLevel, message: String) {
        android.util.Log.i("RunnerController", "[$level] $message")
        val entry = LogEntry(level = level, message = message)
        val current = _logs.value.toMutableList()
        current.add(entry)
        if (current.size > 300) {
            _logs.value = current.takeLast(150)
        } else {
            _logs.value = current
        }
    }

    fun clearLogs() {
        _logs.value = listOf(LogEntry(level = LogLevel.INFO, message = "Nhật ký hệ thống đã được làm sạch."))
    }
}
