package com.f4f.autorunner.engine

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.f4f.autorunner.api.F4FApiClient
import com.f4f.autorunner.api.F4FJob
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
    private val onLog: (String) -> Unit,
    private val onStatsUpdated: (RunnerStats) -> Unit
) {
    private var jobScope: CoroutineScope? = null
    val stats = RunnerStats()
    private var jobsSinceHuman = 0
    var isRunning = false
        private set

    fun start() {
        if (isRunning) return
        isRunning = true
        jobScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

        jobScope?.launch {
            runJobLoop()
        }
    }

    fun stop() {
        isRunning = false
        jobScope?.cancel()
        jobScope = null
        onLog("⏹ Đã dừng phiên chạy.")
    }

    private suspend fun runJobLoop() {
        onLog("🚀 Bắt đầu phiên chạy $platform (Mục tiêu: $maxJobs jobs)...")
        var totalProcessed = 0
        var consecutiveErrors = 0

        val typesToRun = if (jobType == "all" && platform == "tiktok") listOf("follow", "like") else listOf(jobType)

        while (isRunning && totalProcessed < maxJobs) {
            var jobsFoundInRound = false

            for (tJob in typesToRun) {
                if (!isRunning || totalProcessed >= maxJobs) break

                val jobs = try {
                    apiClient.getJobs(platform, accountName, typeJob = tJob)
                } catch (e: Exception) {
                    onLog("❌ Lỗi lấy job ($tJob): ${e.message}")
                    delay(4000)
                    continue
                }

                if (jobs.isEmpty()) continue
                jobsFoundInRound = true

                for (job in jobs) {
                    if (!isRunning || totalProcessed >= maxJobs) break
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
                        onLog("⚠️ Gặp 5 lỗi liên tiếp! Tạm dừng 25s...")
                        delay(25000)
                        consecutiveErrors = 0
                    }

                    // Anti-ban
                    if (antiBanEveryNJobs > 0 && jobsSinceHuman >= antiBanEveryNJobs) {
                        onLog("☕ [Anti-Ban] Lướt feed $antiBanScrollTimes lần...")
                        triggerAntiBan()
                        jobsSinceHuman = 0
                    }

                    // Delay giữa các job
                    if (totalProcessed < maxJobs && isRunning) {
                        val sleepSec = Random.nextInt(delayMin, delayMax + 1)
                        onLog("⏳ Chờ ${sleepSec}s trước job kế tiếp...")
                        delay(sleepSec * 1000L)
                    }
                }
            }

            if (!jobsFoundInRound && totalProcessed < maxJobs && isRunning) {
                onLog("ℹ Hiện hết job. Tự động chờ 20s quét lại...")
                delay(20000)
            }
        }

        onLog("🏁 Hoàn thành phiên chạy! Tổng nhận: ~${stats.coinsEarned} xu.")
        isRunning = false
    }

    private suspend fun processJob(job: F4FJob): String {
        val target = job.link ?: job.originalLink ?: job.objectId ?: ""
        onLog("👉 Job #${job.id} [${job.typeJob.uppercase()}] | @$target | +${job.rewardAmount} xu")

        // 1. Mở trang đích qua Android Intent
        val openOk = openTarget(target, job.typeJob)
        if (!openOk) {
            onLog("⚠️ Không mở được liên kết -> Bỏ qua job")
            apiClient.skipJob(platform, job.id, accountId, accountName, target)
            stats.skipped++
            return "skipped"
        }

        // Chờ giao diện tải xong
        delay(3000)

        val service = F4FAccessibilityService.instance
        if (service == null) {
            onLog("❌ Dịch vụ Trợ năng chưa bật!")
            return "failed"
        }

        service.dismissPopups()

        // 2. Tương tác dựa vào loại Job
        val state = if (job.typeJob == "like") {
            service.performLikeTikTok()
        } else {
            service.performFollow()
        }

        // 3. Xử lý kết quả & báo cáo API
        return when (state) {
            "already" -> {
                onLog("ℹ Đã thực hiện từ trước -> Nhận thưởng...")
                stats.already++
                reportComplete(job)
                "already"
            }
            "followed" -> {
                onLog("✓ Đã bấm Follow thành công!")
                stats.followed++
                reportComplete(job)
                "followed"
            }
            "liked" -> {
                onLog("✓ Đã bấm Like video thành công!")
                stats.liked++
                reportComplete(job)
                "liked"
            }
            "requested" -> {
                onLog("ℹ Tài khoản riêng tư (Đã gửi yêu cầu) -> Nhận thưởng...")
                stats.followed++
                reportComplete(job)
                "followed"
            }
            else -> {
                onLog("✗ Không tìm thấy nút tương tác -> Bỏ qua job")
                apiClient.skipJob(platform, job.id, accountId, accountName, target)
                stats.skipped++
                "skipped"
            }
        }
    }

    private suspend fun reportComplete(job: F4FJob) {
        // Thử lại 1 lần nếu gặp độ trễ đồng bộ
        for (attempt in 0..1) {
            try {
                val res = apiClient.completeJob(platform, job.id, accountId, job.typeJob)
                val coins = res?.coinReceived ?: job.rewardAmount
                stats.coinsEarned += coins
                onLog("💰 Nhận thành công +$coins xu! (Tổng: ~${stats.coinsEarned} xu)")
                return
            } catch (e: Exception) {
                if (e.message?.contains("400") == true && attempt == 0) {
                    onLog("-> Server đang đồng bộ dữ liệu, chờ 3.5s thử lại...")
                    delay(3500)
                    continue
                }
                onLog("❌ Lỗi báo cáo complete-job: ${e.message}")
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
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }

    private suspend fun triggerAntiBan() = withContext(Dispatchers.Main) {
        val completer = CompletableDeferred<Unit>()
        F4FAccessibilityService.instance?.simulateHumanBrowse(antiBanScrollTimes) {
            completer.complete(Unit)
        } ?: completer.complete(Unit)
        completer.await()
    }
}
