package com.f4f.autorunner.engine

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.f4f.autorunner.api.F4FApiClient
import com.f4f.autorunner.api.F4FJob
import com.f4f.autorunner.controller.LogLevel
import com.f4f.autorunner.controller.RunnerController
import com.f4f.autorunner.service.F4FAccessibilityService
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

        // Nếu đang tạm dừng, đợi cho đến khi resume hoặc stop
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
            "Bắt đầu chiến dịch $platform (Mục tiêu: $maxJobs jobs, Delay: ${delayMin}-${delayMax}s)"
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

                    // Mô phỏng lướt feed chống checkpoint
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

        onLog(LogLevel.SUCCESS, "Hoàn tất phiên chạy! Tổng nhận: ~${stats.coinsEarned} xu.")
    }

    private suspend fun processJob(job: F4FJob): String {
        val target = job.link ?: job.originalLink ?: job.objectId ?: ""
        val reward = job.getRewardInt()
        onLog(LogLevel.INFO, "Job #${job.id} [${job.typeJob.uppercase()}] | @$target | +$reward xu")

        if (!checkCanProceed()) return "stopped"

        // 1. Mở trang đích
        val openOk = openTarget(target, job.typeJob)
        if (!openOk) {
            onLog(LogLevel.WARN, "Không thể mở liên kết -> Bỏ qua job")
            try {
                apiClient.skipJob(platform, job.id, accountId, accountName, target)
            } catch (_: Exception) {}
            stats.skipped++
            return "skipped"
        }

        val service = F4FAccessibilityService.instance
        if (service == null) {
            onLog(LogLevel.ERROR, "Dịch vụ Trợ Năng Accessibility bị tắt!")
            return "failed"
        }

        // Chờ trang tải và thử tìm nút (tối đa 4s)
        cancellableDelay(2)
        if (!checkCanProceed()) return "stopped"
        service.dismissPopups()

        var state = "failed"
        val deadline = System.currentTimeMillis() + 4000L
        while (System.currentTimeMillis() <= deadline && checkCanProceed()) {
            state = if (job.typeJob == "like") {
                service.performLikeTikTok()
            } else {
                service.performFollow()
            }
            if (state != "failed") break
            delay(600)
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
                onLog(LogLevel.SUCCESS, "Đã bấm Follow thành công!")
                stats.followed++
                cancellableDelay(2)
                reportComplete(job)
                "followed"
            }
            "liked" -> {
                onLog(LogLevel.SUCCESS, "Đã bấm Like video thành công!")
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

    private fun openTarget(target: String, typeJob: String): Boolean {
        return try {
            val url = when {
                target.startsWith("http://") || target.startsWith("https://") -> target
                platform == "instagram" -> "https://www.instagram.com/${target.removePrefix("@")}"
                else -> "https://www.tiktok.com/@${target.removePrefix("@")}"
            }

            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }

            findInstalledAppPackage(context, platform)?.let { pkg ->
                intent.setPackage(pkg)
            }

            context.startActivity(intent)
            true
        } catch (_: Exception) {
            try {
                val url = when {
                    target.startsWith("http://") || target.startsWith("https://") -> target
                    platform == "instagram" -> "https://www.instagram.com/${target.removePrefix("@")}"
                    else -> "https://www.tiktok.com/@${target.removePrefix("@")}"
                }
                val fallbackIntent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                }
                context.startActivity(fallbackIntent)
                true
            } catch (_: Exception) {
                false
            }
        }
    }

    private fun findInstalledAppPackage(ctx: Context, plat: String): String? {
        val candidates = if (plat == "instagram") {
            listOf("com.instagram.android", "com.instagram.lite")
        } else {
            listOf(
                "com.ss.android.ugc.trill",
                "com.zhiliaoapp.musically",
                "com.zhiliaoapp.musically.go",
                "com.ss.android.ugc.aweme"
            )
        }
        val pm = ctx.packageManager
        for (pkg in candidates) {
            try {
                pm.getPackageInfo(pkg, 0)
                return pkg
            } catch (_: Exception) {}
        }
        return null
    }

    private suspend fun triggerAntiBan() = withContext(Dispatchers.Main) {
        val completer = CompletableDeferred<Unit>()
        F4FAccessibilityService.instance?.simulateHumanBrowse(antiBanScrollTimes) {
            completer.complete(Unit)
        } ?: completer.complete(Unit)
        completer.await()
    }
}
