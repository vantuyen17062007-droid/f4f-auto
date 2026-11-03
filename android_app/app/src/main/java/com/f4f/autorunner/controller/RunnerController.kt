package com.f4f.autorunner.controller

import android.content.Context
import com.f4f.autorunner.api.F4FApiClient
import com.f4f.autorunner.engine.AutoJobEngine
import com.f4f.autorunner.engine.RunnerStats
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

enum class RunnerState {
    IDLE,
    RUNNING,
    PAUSED,
    STOPPED
}

enum class LogLevel {
    INFO,
    SUCCESS,
    WARN,
    ERROR
}

data class LogEntry(
    val timestamp: String = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date()),
    val level: LogLevel,
    val message: String
)

object RunnerController {

    private val _state = MutableStateFlow(RunnerState.IDLE)
    val state: StateFlow<RunnerState> = _state.asStateFlow()

    private val _stats = MutableStateFlow(RunnerStats())
    val stats: StateFlow<RunnerStats> = _stats.asStateFlow()

    private val _logs = MutableStateFlow<List<LogEntry>>(
        listOf(LogEntry(level = LogLevel.INFO, message = "F4F AutoRunner v2.0 sẵn sàng."))
    )
    val logs: StateFlow<List<LogEntry>> = _logs.asStateFlow()

    private var activeEngine: AutoJobEngine? = null

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

        _state.value = RunnerState.RUNNING
        _stats.value = RunnerStats()
        addLog(LogLevel.INFO, "Khởi động chiến dịch [$platform] cho @$accountName...")

        val appContext = context.applicationContext
        val engine = AutoJobEngine(
            context = appContext,
            apiClient = apiClient,
            platform = platform,
            accountId = accountId,
            accountName = accountName,
            jobType = jobType,
            maxJobs = maxJobs,
            delayMin = delayMin,
            delayMax = delayMax,
            antiBanEveryNJobs = antiBanEveryNJobs,
            antiBanScrollTimes = antiBanScrollTimes,
            onLog = { level, msg ->
                addLog(level, msg)
            },
            onStatsUpdated = { newStats ->
                _stats.value = newStats.copy()
            },
            onFinished = {
                _state.value = RunnerState.STOPPED
                addLog(LogLevel.SUCCESS, "Phiên chạy đã hoàn thành toàn bộ mục tiêu.")
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
            addLog(LogLevel.WARN, "Đã tạm dừng (PAUSED). Nhấn Tiếp tục để chạy lại.")
        }
    }

    @Synchronized
    fun resume() {
        if (_state.value == RunnerState.PAUSED) {
            _state.value = RunnerState.RUNNING
            activeEngine?.resume()
            addLog(LogLevel.INFO, "Đã tiếp tục phiên chạy (RESUMED).")
        }
    }

    @Synchronized
    fun stop() {
        if (_state.value != RunnerState.STOPPED && _state.value != RunnerState.IDLE) {
            _state.value = RunnerState.STOPPED
            activeEngine?.stop()
            activeEngine = null
            addLog(LogLevel.WARN, "Đã dừng phiên chạy khẩn cấp (STOPPED).")
        }
    }

    fun addLog(level: LogLevel, message: String) {
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
