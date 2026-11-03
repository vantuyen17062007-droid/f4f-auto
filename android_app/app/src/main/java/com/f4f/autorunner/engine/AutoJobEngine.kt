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
    private val onStatsUpdated: (RunnerStats) -> Unit,
    private val onFinished: (() -> Unit)? = null
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
            try {
                runJobLoop()
            } finally {
                isRunning = false
                withContext(Dispatchers.Main) {
                    onFinished?.invoke()
                }
            }
        }
    }

    fun stop() {
        if (!isRunning) return
        isRunning = false
        jobScope?.cancel()
        jobScope = null
        onLog("⏹ Đã dừng phiên chạy.")
    }

    private suspend fun runJobLoop() {
        onLog("🚀 Bắt đầu phiên chạy $platform (Mục tiêu: $maxJobs jobs, Delay: ${delayMin}-${delayMax}s)...")
        var totalProcessed = 0
        var consecutiveErrors = 0

        val typesToRun = when {
            platform == "instagram" -> listOf("follow")
            jobType == "all" && platform == "tiktok" -> listOf("follow", "like")
            else -> listOf(jobType)
        }

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

                    // Anti-ban simulation
                    if (antiBanEveryNJobs > 0 && jobsSinceHuman >= antiBanEveryNJobs) {
                        onLog("☕ [Anti-Ban] Lướt feed $antiBanScrollTimes lần...")
                        triggerAntiBan()
                        jobsSinceHuman = 0
                    }

                    // Delay giữa các job
                    if (totalProcessed < maxJobs && isRunning) {
                        val minD = delayMin.coerceAtLeast(3)
                        val maxD = delayMax.coerceAtLeast(minD)
                        val sleepSec = if (minD == maxD) minD else Random.nextInt(minD, maxD + 1)
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
    }

    private suspend fun processJob(job: F4FJob): String {
        val target = job.link ?: job.originalLink ?: job.objectId ?: ""
        val reward = job.getRewardInt()
        onLog("👉 Job #${job.id} [${job.typeJob.uppercase()}] | @$target | +$reward xu")

        // 1. Mở trang đích qua Android Intent
        val openOk = openTarget(target, job.typeJob)
        if (!openOk) {
            onLog("⚠️ Không mở được liên kết -> Bỏ qua job")
            try {
                apiClient.skipJob(platform, job.id, accountId, accountName, target)
            } catch (_: Exception) {}
            stats.skipped++
            return "skipped"
        }

        val service = F4FAccessibilityService.instance
        if (service == null) {
            onLog("❌ Dịch vụ Trợ năng chưa bật!")
            return "failed"
        }

        // Chờ trang tải và thử tìm nút tương tác (tối đa 4s)
        delay(2500)
        service.dismissPopups()

        var state = "failed"
        val deadline = System.currentTimeMillis() + 4000L
        while (System.currentTimeMillis() <= deadline && isRunning) {
            state = if (job.typeJob == "like") {
                service.performLikeTikTok()
            } else {
                service.performFollow()
            }
            if (state != "failed") break
            delay(700)
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
                delay(2000) // Đợi 2s để TikTok/IG lưu trạng thái trước khi gọi API
                reportComplete(job)
                "followed"
            }
            "liked" -> {
                onLog("✓ Đã bấm Like video thành công!")
                stats.liked++
                delay(2000)
                reportComplete(job)
                "liked"
            }
            "requested" -> {
                onLog("ℹ Tài khoản riêng tư (Đã gửi yêu cầu) -> Nhận thưởng...")
                stats.followed++
                delay(2000)
                reportComplete(job)
                "followed"
            }
            else -> {
                onLog("✗ Không tìm thấy nút tương tác -> Bỏ qua job")
                try {
                    apiClient.skipJob(platform, job.id, accountId, accountName, target)
                } catch (_: Exception) {}
                stats.skipped++
                "skipped"
            }
        }
    }

    private suspend fun reportComplete(job: F4FJob) {
        val retryDelays = listOf(4000L, 8000L)
        for (attempt in 0..2) {
            try {
                val res = apiClient.completeJob(platform, job.id, accountId, job.typeJob)
                val coins = res?.getCoinReceivedInt(job.getRewardInt()) ?: job.getRewardInt()
                stats.coinsEarned += coins
                onLog("💰 Nhận thành công +$coins xu! (Tổng phiên: ~${stats.coinsEarned} xu)")
                return
            } catch (e: Exception) {
                val isBusy = e.message?.contains("400") == true ||
                             e.message?.contains("đồng bộ") == true ||
                             e.message?.contains("bận") == true
                if (isBusy && attempt < 2) {
                    val waitMs = retryDelays[attempt]
                    onLog("-> F4F đang kiểm tra đồng bộ, chờ ${waitMs / 1000}s thử lại...")
                    delay(waitMs)
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

            // Ưu tiên mở trực tiếp bằng package của TikTok/Instagram để tránh bị nhảy vào trình duyệt Chrome
            findInstalledAppPackage(context, platform)?.let { pkg ->
                intent.setPackage(pkg)
            }

            context.startActivity(intent)
            true
        } catch (_: Exception) {
            // Fallback mở intent thông thường nếu setPackage thất bại
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
