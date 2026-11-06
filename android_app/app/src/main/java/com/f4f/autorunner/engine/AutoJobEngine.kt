package com.f4f.autorunner.engine

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.f4f.autorunner.adb.AdbManager
import com.f4f.autorunner.adb.UiXmlParser
import com.f4f.autorunner.api.F4FApiClient
import com.f4f.autorunner.api.F4FJob
import com.f4f.autorunner.controller.LogLevel
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
                val hasAdb = AdbManager.isConnected
                val hasAccessibility = F4FAccessibilityService.isRunning()

                if (!hasAdb && !hasAccessibility) {
                    onLog(LogLevel.ERROR, "Chưa kết nối ADB và chưa bật Trợ Năng F4F! Vui lòng vào Cài đặt để kết nối ADB hoặc bật Trợ Năng.")
                    return@launch
                }

                if (hasAdb) {
                    onLog(LogLevel.INFO, "⚡ Sử dụng chế độ: ADB Tự động hóa (Tối ưu, ổn định)")
                } else {
                    onLog(LogLevel.INFO, "♿ Sử dụng chế độ: Trợ Năng F4F (Chế độ dự phòng)")
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
            "Bắt đầu chiến dịch [$platform] (Mục tiêu: $maxJobs jobs, Delay: ${delayMin}-${delayMax}s)"
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
                        onLog(LogLevel.WARN, "Gặp 5 lỗi liên tiếp! Tạm dừng 15s để làm mới...")
                        cancellableDelay(15)
                        consecutiveErrors = 0
                    }

                    // Mô phỏng lướt feed chống checkpoint
                    if (antiBanEveryNJobs > 0 && jobsSinceHuman >= antiBanEveryNJobs) {
                        onLog(LogLevel.INFO, "[Anti-Ban] Lướt feed $antiBanScrollTimes lần mô phỏng người thật...")
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

        // Chờ giao diện tải
        cancellableDelay(3)
        if (!checkCanProceed()) return "stopped"

        var state = "failed"

        // ==================== A. XỬ LÝ JOB LIKE ====================
        if (job.typeJob == "like") {
            if (AdbManager.isConnected) {
                // Trên TikTok/Instagram, Double-tap vào tâm video đảm bảo thả tim 100% cực nhanh, không lo vướng uiautomator
                AdbManager.likeCenter()
                state = "liked"
                cancellableDelay(1)
            } else if (F4FAccessibilityService.isRunning()) {
                val accState = F4FAccessibilityService.instance?.performLikeTikTok() ?: "failed"
                state = if (accState == "already") "already" else "liked"
            }
        }
        // ==================== B. XỬ LÝ JOB FOLLOW ====================
        else {
            if (AdbManager.isConnected) {
                // Thử dump UI nhanh
                val xml = AdbManager.dumpUiXml()
                val nodes = UiXmlParser.parseNodes(xml)
                val (followState, pt) = UiXmlParser.findFollowButton(nodes)

                if (followState == "already" || followState == "requested") {
                    state = followState
                } else if (pt != null) {
                    AdbManager.tap(pt.x, pt.y)
                    state = "followed"
                    // Bấm phím Back để đóng popup hỏi quyền thông báo của TikTok nếu có
                    delay(800)
                    AdbManager.keyevent(4)
                } else {
                    // Nếu không dump được do video animation hoặc nút bị che, dùng tọa độ nút Follow chuẩn TikTok
                    onLog(LogLevel.INFO, "Dùng tọa độ chuẩn để bấm Follow...")
                    AdbManager.followTikTokHeuristic()
                    state = "followed"
                    delay(800)
                    AdbManager.keyevent(4)
                }
            } else if (F4FAccessibilityService.isRunning()) {
                state = F4FAccessibilityService.instance?.performFollow() ?: "failed"
            }
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
                onLog(LogLevel.SUCCESS, "Đã bấm Like thành công!")
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
                onLog(LogLevel.WARN, "Không hoàn thành tương tác -> Bỏ qua job")
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

    private suspend fun openTarget(target: String, typeJob: String): Boolean {
        val url = when {
            target.startsWith("http://") || target.startsWith("https://") -> target
            platform == "instagram" -> "https://www.instagram.com/${target.removePrefix("@")}"
            typeJob == "like" && target.all { it.isDigit() } -> "https://www.tiktok.com/@video/video/$target"
            else -> "https://www.tiktok.com/@${target.removePrefix("@")}"
        }

        val pkg = if (platform == "instagram") "com.instagram.android" else "com.ss.android.ugc.trill"

        // Ưu tiên mở qua ADB nếu kết nối
        if (AdbManager.isConnected) {
            try {
                AdbManager.openUrl(url, pkg)
                return true
            } catch (_: Exception) {}
        }

        // Fallback mở bằng Intent Android thông thường
        return try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                if (pkg.isNotEmpty()) setPackage(pkg)
            }
            context.startActivity(intent)
            true
        } catch (_: Exception) {
            try {
                // Thử mở không chỉ định package nếu app chưa cài hoặc intent bị từ chối
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

    private suspend fun triggerAntiBan() {
        try {
            if (AdbManager.isConnected) {
                repeat(antiBanScrollTimes) {
                    AdbManager.swipeFeed()
                    delay(1200)
                }
            } else if (F4FAccessibilityService.isRunning()) {
                val completeSignal = CompletableDeferred<Unit>()
                F4FAccessibilityService.instance?.simulateHumanBrowse(antiBanScrollTimes) {
                    completeSignal.complete(Unit)
                }
                completeSignal.await()
            }
        } catch (_: Exception) {}
    }
}
