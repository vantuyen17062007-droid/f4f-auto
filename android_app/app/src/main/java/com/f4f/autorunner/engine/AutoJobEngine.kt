package com.f4f.autorunner.engine

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.f4f.autorunner.adb.AdbManager
import com.f4f.autorunner.adb.UiXmlParser
import com.f4f.autorunner.api.F4FApiClient
import com.f4f.autorunner.api.F4FJob
import com.f4f.autorunner.controller.LogLevel
import kotlinx.coroutines.*
import kotlin.random.Random

data class RunnerStats(
    var followed: Int = 0,
    var liked: Int = 0,
    var already: Int = 0,
    var skipped: Int = 0,
    var errors: Int = 0,
    var coinsEarned: Int = 0
)

class AutoJobEngine(
    private val context: Context,
    private val apiClient: F4FApiClient,
    private val platform: String, // "tiktok" hoặc "instagram"
    private val accountId: Long,
    private val accountName: String,
    private val jobType: String = "all",
    private val maxJobs: Int = 50,
    private val delayMin: Int = 8,
    private val delayMax: Int = 18,
    private val antiBanEveryNJobs: Int = 5,
    private val antiBanScrollTimes: Int = 2,
    private val onLog: (LogLevel, String) -> Unit,
    private val onStatsUpdated: (RunnerStats) -> Unit,
    private val onFinished: (() -> Unit)? = null
) {
    private var jobScope: CoroutineScope? = null
    val stats = RunnerStats()
    private var jobsSinceHuman = 0
    var isRunning = false
        private set
    var isPaused = false
        private set

    fun start() {
        if (isRunning) return
        isRunning = true
        isPaused = false
        jobScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

        jobScope?.launch {
            try {
                if (!AdbManager.isConnected) {
                    onLog(LogLevel.ERROR, "Chưa kết nối ADB! Vui lòng vào Cài đặt để kết nối ADB trước.")
                    return@launch
                }
                runJobLoop()
            } catch (_: CancellationException) {
                onLog(LogLevel.WARN, "Tiến trình chạy đã bị hủy theo yêu cầu.")
            } catch (e: Exception) {
                onLog(LogLevel.ERROR, "Lỗi bất ngờ trong tiến trình: ${e.message}")
            } finally {
                isRunning = false
                isPaused = false
                withContext(Dispatchers.Main) {
                    onFinished?.invoke()
                }
            }
        }
    }

    fun pause() {
        isPaused = true
    }

    fun resume() {
        isPaused = false
    }

    fun stop() {
        isRunning = false
        isPaused = false
        jobScope?.cancel()
        jobScope = null
    }

    private suspend fun checkCanProceed(): Boolean {
        if (!isRunning || jobScope?.isActive == false) return false

        while (isPaused && isRunning) {
            delay(500)
        }
        return isRunning && jobScope?.isActive == true
    }

    private suspend fun cancellableDelay(seconds: Int) {
        val totalMs = seconds * 1000L
        val intervalMs = 300L
        var elapsed = 0L
        while (elapsed < totalMs) {
            if (!checkCanProceed()) return
            delay(intervalMs)
            elapsed += intervalMs
        }
    }

    private suspend fun runJobLoop() {
        onLog(
            LogLevel.INFO,
            "Bắt đầu chiến dịch ADB [$platform] (Mục tiêu: $maxJobs jobs, Delay: ${delayMin}-${delayMax}s)"
        )
        var totalProcessed = 0
        var consecutiveErrors = 0

        val typesToRun = when {
            platform == "instagram" -> listOf("follow")
            jobType == "all" && platform == "tiktok" -> listOf("follow", "like")
            else -> listOf(jobType)
        }

        while (checkCanProceed() && totalProcessed < maxJobs) {
            var jobsFoundInRound = false

            for (tJob in typesToRun) {
                if (!checkCanProceed() || totalProcessed >= maxJobs) break

                val jobs = try {
                    apiClient.getJobs(platform, accountName, typeJob = tJob)
                } catch (e: Exception) {
                    onLog(LogLevel.ERROR, "Lỗi kết nối lấy job ($tJob): ${e.message}")
                    cancellableDelay(4)
                    continue
                }

                if (jobs.isEmpty()) continue
                jobsFoundInRound = true

                for (job in jobs) {
                    if (!checkCanProceed() || totalProcessed >= maxJobs) break
                    job.typeJob = tJob

                    val result = processJob(job)
                    totalProcessed++
                    jobsSinceHuman++

                    if (result in listOf("followed", "liked", "already", "skipped")) {
                        consecutiveErrors = 0
                    } else {
                        stats.errors++
                        consecutiveErrors++
                    }
                    onStatsUpdated(stats)

                    if (consecutiveErrors >= 5) {
                        onLog(LogLevel.WARN, "Gặp 5 lỗi liên tiếp! Tạm dừng 20s để hồi phục...")
                        cancellableDelay(20)
                        consecutiveErrors = 0
                    }

                    // Mô phỏng lướt feed chống checkpoint qua ADB
                    if (antiBanEveryNJobs > 0 && jobsSinceHuman >= antiBanEveryNJobs) {
                        onLog(LogLevel.INFO, "[Anti-Ban] Lướt feed $antiBanScrollTimes lần...")
                        triggerAntiBan()
                        jobsSinceHuman = 0
                    }

                    // Delay an toàn giữa các job
                    if (totalProcessed < maxJobs && checkCanProceed()) {
                        val minD = delayMin.coerceAtLeast(3)
                        val maxD = delayMax.coerceAtLeast(minD)
                        val sleepSec = if (minD == maxD) minD else Random.nextInt(minD, maxD + 1)
                        onLog(LogLevel.INFO, "Nghỉ an toàn ${sleepSec}s trước nhiệm vụ tiếp theo...")
                        cancellableDelay(sleepSec)
                    }
                }
            }

            if (!jobsFoundInRound && totalProcessed < maxJobs && checkCanProceed()) {
                onLog(LogLevel.WARN, "Chưa có job mới khả dụng. Tự động chờ 20s quét lại...")
                cancellableDelay(20)
            }
        }

        onLog(LogLevel.SUCCESS, "Hoàn tất phiên chạy ADB! Tổng nhận: ~${stats.coinsEarned} xu.")
    }

    private suspend fun processJob(job: F4FJob): String {
        val target = job.link ?: job.originalLink ?: job.objectId ?: ""
        val reward = job.getRewardInt()
        onLog(LogLevel.INFO, "Job #${job.id} [${job.typeJob.uppercase()}] | @$target | +$reward xu")

        if (!checkCanProceed()) return "stopped"

        // 1. Mở trang đích qua ADB
        val openOk = openTargetViaAdb(target, job.typeJob)
        if (!openOk) {
            onLog(LogLevel.WARN, "Không thể mở liên kết -> Bỏ qua job")
            try {
                apiClient.skipJob(platform, job.id, accountId, accountName, target)
            } catch (_: Exception) {}
            stats.skipped++
            return "skipped"
        }

        // Chờ giao diện tải
        cancellableDelay(3)
        if (!checkCanProceed()) return "stopped"

        // Đóng các popup quảng cáo / đồng bộ
        dismissPopupsViaAdb()

        var state = "failed"
        val deadline = System.currentTimeMillis() + 4500L
        while (System.currentTimeMillis() <= deadline && checkCanProceed()) {
            val xml = AdbManager.dumpUiXml()
            val nodes = UiXmlParser.parseNodes(xml)

            if (job.typeJob == "like") {
                val (likeState, pt) = UiXmlParser.findLikeState(nodes)
                if (likeState == "already") {
                    state = "already"
                    break
                }
                if (pt != null) {
                    AdbManager.tap(pt.x, pt.y)
                    state = "liked"
                    break
                } else {
                    // Double tap vào giữa màn hình video để Like (chuẩn TikTok)
                    AdbManager.doubleTap(360, 800)
                    state = "liked"
                    break
                }
            } else {
                val (followState, pt) = UiXmlParser.findFollowButton(nodes)
                if (followState == "already" || followState == "requested") {
                    state = followState
                    break
                }
                if (pt != null) {
                    AdbManager.tap(pt.x, pt.y)
                    state = "followed"
                    break
                }
            }
            delay(800)
        }

        if (!checkCanProceed()) return "stopped"

        // 3. Xử lý kết quả & báo cáo API
        return when (state) {
            "already" -> {
                onLog(LogLevel.INFO, "Đã thực hiện từ trước -> Nhận thưởng...")
                stats.already++
                reportComplete(job)
                "already"
            }
            "followed" -> {
                onLog(LogLevel.SUCCESS, "Đã bấm Follow qua ADB thành công!")
                stats.followed++
                cancellableDelay(2)
                reportComplete(job)
                "followed"
            }
            "liked" -> {
                onLog(LogLevel.SUCCESS, "Đã bấm Like video qua ADB thành công!")
                stats.liked++
                cancellableDelay(2)
                reportComplete(job)
                "liked"
            }
            "requested" -> {
                onLog(LogLevel.INFO, "Tài khoản riêng tư (Đã gửi yêu cầu) -> Nhận thưởng...")
                stats.followed++
                cancellableDelay(2)
                reportComplete(job)
                "followed"
            }
            else -> {
                onLog(LogLevel.WARN, "Không tìm thấy nút tương tác -> Bỏ qua job")
                try {
                    apiClient.skipJob(platform, job.id, accountId, accountName, target)
                } catch (_: Exception) {}
                stats.skipped++
                "skipped"
            }
        }
    }

    private suspend fun reportComplete(job: F4FJob) {
        if (!checkCanProceed()) return

        val retryDelays = listOf(4000L, 8000L)
        for (attempt in 0..2) {
            try {
                val res = apiClient.completeJob(platform, job.id, accountId, job.typeJob)
                val coins = res?.getCoinReceivedInt(job.getRewardInt()) ?: job.getRewardInt()
                stats.coinsEarned += coins
                onStatsUpdated(stats)
                onLog(LogLevel.SUCCESS, "Nhận thành công +$coins xu! (Tổng phiên: ~${stats.coinsEarned} xu)")
                return
            } catch (e: Exception) {
                val isBusy = e.message?.contains("400") == true ||
                        e.message?.contains("đồng bộ") == true ||
                        e.message?.contains("bận") == true
                if (isBusy && attempt < 2 && checkCanProceed()) {
                    val waitMs = retryDelays[attempt]
                    onLog(LogLevel.WARN, "F4F đang kiểm tra đồng bộ, thử lại sau ${waitMs / 1000}s...")
                    delay(waitMs)
                    continue
                }
                onLog(LogLevel.ERROR, "Lỗi hoàn thành job: ${e.message}")
                return
            }
        }
    }

    private suspend fun openTargetViaAdb(target: String, typeJob: String): Boolean {
        return try {
            val url = when {
                target.startsWith("http://") || target.startsWith("https://") -> target
                platform == "instagram" -> "https://www.instagram.com/${target.removePrefix("@")}"
                typeJob == "like" && target.all { it.isDigit() } -> "https://www.tiktok.com/@video/video/$target"
                else -> "https://www.tiktok.com/@${target.removePrefix("@")}"
            }

            val pkg = if (platform == "instagram") "com.instagram.android" else "com.ss.android.ugc.trill"
            AdbManager.openUrl(url, pkg)
            true
        } catch (_: Exception) {
            // Fallback mở bằng Android Activity thông thường
            try {
                val url = when {
                    target.startsWith("http://") || target.startsWith("https://") -> target
                    platform == "instagram" -> "https://www.instagram.com/${target.removePrefix("@")}"
                    else -> "https://www.tiktok.com/@${target.removePrefix("@")}"
                }
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                }
                context.startActivity(intent)
                true
            } catch (_: Exception) {
                false
            }
        }
    }

    private suspend fun dismissPopupsViaAdb() {
        try {
            val xml = AdbManager.dumpUiXml()
            val nodes = UiXmlParser.parseNodes(xml)
            val pt = UiXmlParser.findPopupDismissButton(nodes)
            if (pt != null) {
                AdbManager.tap(pt.x, pt.y)
                delay(300)
            }
        } catch (_: Exception) {}
    }

    private suspend fun triggerAntiBan() {
        try {
            repeat(antiBanScrollTimes) {
                AdbManager.swipe(360, 1200, 360, 400, 350)
                delay(1200)
            }
        } catch (_: Exception) {}
    }
}
