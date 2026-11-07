package com.f4f.autorunner.engine

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.f4f.autorunner.adb.AdbManager
import com.f4f.autorunner.adb.UiNode
import com.f4f.autorunner.adb.UiXmlParser
import com.f4f.autorunner.api.ApiException
import com.f4f.autorunner.api.F4FApiClient
import com.f4f.autorunner.api.F4FJob
import com.f4f.autorunner.controller.LogLevel
import com.f4f.autorunner.service.F4FAccessibilityService
import com.f4f.autorunner.util.AppPackages
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
    private var pkg: String = ""
    private val usernameRegex = Regex("^[A-Za-z0-9_.]{1,64}$")

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

                pkg = AppPackages.resolve(context, platform).orEmpty()
                if (pkg.isEmpty()) {
                    val appName = if (platform == "instagram") "Instagram" else "TikTok"
                    onLog(LogLevel.ERROR, "Chưa cài ứng dụng $appName trên máy này! Hãy cài đặt rồi chạy lại.")
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
                // Khi bị stop() thì scope đã bị hủy nên withContext sẽ ném CancellationException
                // và onFinished không chạy -> không ghi đè state của phiên mới.
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

    // ============================ Hàm dùng chung ADB / Trợ Năng ============================

    private suspend fun snapshot(): List<UiNode> =
        if (AdbManager.isConnected) {
            UiXmlParser.parseNodes(AdbManager.dumpUiXml())
        } else {
            F4FAccessibilityService.instance?.snapshotNodes().orEmpty()
        }

    private suspend fun tap(x: Int, y: Int) {
        if (AdbManager.isConnected) {
            AdbManager.tap(x, y)
        } else {
            F4FAccessibilityService.instance?.tapAt(x, y)
        }
    }

    private suspend fun doubleTapCenter() {
        if (AdbManager.isConnected) {
            AdbManager.likeCenter()
        } else {
            val cx = AdbManager.screenWidth / 2
            val cy = (AdbManager.screenHeight * 0.45).toInt()
            F4FAccessibilityService.instance?.doubleTapAt(cx, cy)
        }
    }

    private suspend fun dismissPopupIfAny() {
        val pt = UiXmlParser.findPopupDismissButton(snapshot()) ?: return
        tap(pt.x, pt.y)
        delay(800)
    }

    private fun followNeedsClickable() = !AdbManager.isConnected

    /** Sau khi bấm Follow: đợi, đóng popup, đọc lại giao diện để XÁC MINH đã follow thật. */
    private suspend fun verifyFollowed(hadTargetPoint: Boolean = false): String {
        delay(1200)
        dismissPopupIfAny()
        if (AdbManager.isConnected) {
            // Đóng bottom sheet hỏi quyền thông báo của TikTok nếu xuất hiện
            AdbManager.keyevent(4)
            delay(500)
        }
        val nodes = snapshot()
        val (s, _) = UiXmlParser.findFollowButton(nodes, followNeedsClickable())
        return when (s) {
            "already" -> "followed"
            "requested" -> "requested"
            else -> {
                // Nếu đã bấm trúng nút Follow (hadTargetPoint) nhưng dump sau đó rỗng do animation/idle timeout
                if (hadTargetPoint && nodes.isEmpty()) "followed" else "failed"
            }
        }
    }

    // ============================ Vòng lặp chính ============================

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
                    if (e is ApiException && e.statusCode == 401) {
                        onLog(LogLevel.ERROR, "Phiên đăng nhập F4F hết hạn hoặc sai mật khẩu. Hãy đăng nhập lại rồi chạy tiếp.")
                        return
                    }
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
                    if (result == "stopped") break // người dùng dừng: không tính là lỗi

                    totalProcessed++
                    jobsSinceHuman++

                    when (result) {
                        "followed", "liked", "already" -> consecutiveErrors = 0
                        "skipped" -> consecutiveErrors++ // stats.skipped đã được tăng trong processJob
                        else -> {
                            stats.errors++
                            consecutiveErrors++
                        }
                    }
                    onStatsUpdated(stats)

                    if (consecutiveErrors >= 5) {
                        onLog(LogLevel.WARN, "Gặp 5 job thất bại liên tiếp! Tạm dừng 15s để làm mới...")
                        cancellableDelay(15)
                        consecutiveErrors = 0
                    }

                    // Mô phỏng lướt feed chống checkpoint
                    if (antiBanEveryNJobs > 0 && jobsSinceHuman >= antiBanEveryNJobs) {
                        onLog(LogLevel.INFO, "[Anti-Ban] Lướt feed $antiBanScrollTimes lần mô phỏng người thật...")
                        com.f4f.autorunner.controller.RunnerController.updateJobInfo("🛡️ [Anti-Ban] Đang lướt feed...")
                        triggerAntiBan()
                        jobsSinceHuman = 0
                    }

                    // Delay an toàn giữa các job
                    if (totalProcessed < maxJobs && checkCanProceed()) {
                        val minD = delayMin.coerceAtLeast(3)
                        val maxD = delayMax.coerceAtLeast(minD)
                        val sleepSec = if (minD == maxD) minD else Random.nextInt(minD, maxD + 1)
                        onLog(LogLevel.INFO, "Nghỉ an toàn ${sleepSec}s trước nhiệm vụ tiếp theo...")
                        com.f4f.autorunner.controller.RunnerController.updateJobInfo("⏳ Chờ ${sleepSec}s trước job tiếp theo...")
                        cancellableDelay(sleepSec)
                    }
                }
            }

            if (!jobsFoundInRound && totalProcessed < maxJobs && checkCanProceed()) {
                onLog(LogLevel.WARN, "Chưa có job mới khả dụng. Tự động chờ 20s quét lại...")
                com.f4f.autorunner.controller.RunnerController.updateJobInfo("🔍 Chưa có job mới. Chờ 20s quét lại...")
                cancellableDelay(20)
            }
        }

        if (totalProcessed >= maxJobs) {
            onLog(LogLevel.SUCCESS, "Hoàn tất phiên chạy! Tổng nhận: ~${stats.coinsEarned} xu.")
            com.f4f.autorunner.controller.RunnerController.updateJobInfo("🎉 Đã hoàn thành mục tiêu ($totalProcessed/$maxJobs jobs)")
        }
    }

    private suspend fun processJob(job: F4FJob): String {
        val target = job.link ?: job.originalLink ?: job.objectId ?: ""
        val reward = job.getRewardInt()
        val jobDesc = "[${job.typeJob.uppercase()}] @${target.removePrefix("@")} (+$reward xu)"
        onLog(LogLevel.INFO, "Job #${job.id} $jobDesc")
        com.f4f.autorunner.controller.RunnerController.updateJobInfo("🎯 $jobDesc")

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
            val nodesBefore = snapshot()
            val (before, _) = UiXmlParser.findLikeState(nodesBefore)
            if (before == "already") {
                state = "already"
            } else {
                doubleTapCenter()
                cancellableDelay(1)
                val nodesAfter = snapshot()
                val (after, _) = UiXmlParser.findLikeState(nodesAfter)
                // Nếu giao diện xác nhận đã thích, HOẶC không dump được do video đang phát animation 60fps nhưng đã double-tap thả tim
                state = if (after == "already" || (nodesAfter.isEmpty() && AdbManager.isConnected)) "liked" else "failed"
            }
        }
        // ==================== B. XỬ LÝ JOB FOLLOW ====================
        else {
            val (followState, pt) = UiXmlParser.findFollowButton(snapshot(), followNeedsClickable())

            state = when {
                followState == "already" || followState == "requested" -> followState
                pt != null -> {
                    tap(pt.x, pt.y)
                    verifyFollowed(hadTargetPoint = true)
                }
                AdbManager.isConnected -> {
                    // Không đọc được giao diện: thử tọa độ chuẩn nhưng vẫn phải xác minh lại
                    onLog(LogLevel.INFO, "Dùng tọa độ chuẩn để bấm Follow...")
                    AdbManager.followTikTokHeuristic()
                    verifyFollowed(hadTargetPoint = true)
                }
                else -> "failed"
            }
        }

        if (!checkCanProceed()) return "stopped"

        // 3. Xử lý kết quả & báo cáo API (chỉ báo hoàn thành khi đã xác minh)
        val finalStatus = when (state) {
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
                onLog(LogLevel.WARN, "Không xác minh được tương tác -> Bỏ qua job (không báo hoàn thành)")
                try {
                    apiClient.skipJob(platform, job.id, accountId, accountName, target)
                } catch (_: Exception) {}
                stats.skipped++
                "skipped"
            }
        }

        // Nếu là job FOLLOW thì BACK về trang chủ, còn LIKE thì KHÔNG back
        if (job.typeJob == "follow" && checkCanProceed()) {
            navigateBackHome()
        }

        return finalStatus
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
                val isBusy = (e is ApiException && e.statusCode == 400) ||
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
        val trimmed = target.trim()
        val clean = trimmed.removePrefix("@")

        val url = when {
            trimmed.startsWith("https://") -> trimmed
            trimmed.startsWith("http://") -> "https://" + trimmed.removePrefix("http://")
            platform == "instagram" ->
                if (usernameRegex.matches(clean)) "https://www.instagram.com/$clean" else return false
            typeJob == "like" && trimmed.isNotEmpty() && trimmed.all { it.isDigit() } ->
                "https://www.tiktok.com/@video/video/$trimmed"
            else ->
                if (usernameRegex.matches(clean)) "https://www.tiktok.com/@$clean" else return false
        }

        // Dữ liệu từ server: chỉ mở khi là link TikTok / Instagram hợp lệ
        if (!AdbManager.isSafeTargetUrl(url)) {
            onLog(LogLevel.WARN, "Liên kết không hợp lệ hoặc không an toàn, đã bỏ qua: $url")
            return false
        }

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
                setPackage(pkg)
            }
            context.startActivity(intent)
            true
        } catch (_: Exception) {
            false
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
                withTimeoutOrNull(30_000L) { completeSignal.await() }
            }
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {}
    }

    private suspend fun navigateBackHome() {
        try {
            delay(600)
            if (AdbManager.isConnected) {
                // Nhấn Back 2 lần để thoát trang cá nhân trở về trang chủ TikTok/Instagram
                AdbManager.keyevent(4)
                delay(400)
                AdbManager.keyevent(4)
            } else if (F4FAccessibilityService.isRunning()) {
                F4FAccessibilityService.instance?.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK)
                delay(400)
                F4FAccessibilityService.instance?.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK)
            }
        } catch (_: Exception) {}
    }
}
