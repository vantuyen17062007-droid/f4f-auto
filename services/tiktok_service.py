"""
services/tiktok_service.py — Nghiệp vụ tự động hóa TikTok (Follow & Like)
========================================================================
Hỗ trợ:
  - Tự động lấy danh sách tài khoản TikTok liên kết từ F4F API
  - Nhận job Follow & Like video từ F4F
  - Tự động mở profile qua Intent hoặc video qua DeepLinkActivityV2
  - Bấm Follow & Like thông minh, xác minh trạng thái UI
  - Nhận thưởng coin và tự động skip các video bị xóa, riêng tư, tài khoản lỗi
"""

import sys
import time
import random
from typing import Optional, Dict, Any

from core.helpers import CYAN, GREEN, YELLOW, RED, RESET
from core.ui import render_accounts_table
from api.f4f_client import ApiF4F
from services.base_runner import BaseJobRunner
from config.settings import save_config


class TikTokJobRunner(BaseJobRunner):
    def __init__(self, config: Optional[Dict[str, Any]] = None, job_type: str = "all"):
        super().__init__(platform_name="TikTok", config=config)
        self.api = ApiF4F()
        self.job_type = job_type or self.cfg.get("job_type", "all")
        self.account_name = None
        self.account_id = None

    def _select_tiktok_account(self):
        """Lấy danh sách tài khoản TikTok qua API get_acc_tik() của F4F."""
        self.log.info("Lấy danh sách tài khoản TikTok liên kết trên F4F...")
        try:
            acc_list = self.api.get_active_accounts("tiktok")
        except Exception as e:
            self.log.error(f"Lỗi gọi API lấy danh sách tài khoản: {e}")
            sys.exit(1)

        acc_list = [
            acc for acc in acc_list
            if (acc.get("name") or acc.get("username")) and acc.get("id") is not None
        ]

        if not acc_list:
            self.log.error(f"{RED}Không tìm thấy tài khoản TikTok nào đang hoạt động trên F4F!{RESET}")
            self.log.error("Vui lòng vào website follow4follow.net -> Thêm tài khoản TikTok trước khi chạy.")
            sys.exit(1)

        saved_uid = self.cfg.get("tiktok_uid", "").strip()

        # 1. Nếu chỉ có duy nhất 1 tài khoản -> Tự động dùng ngay
        if len(acc_list) == 1:
            chosen = acc_list[0]
            self.account_name = chosen.get("name") or chosen.get("username")
            self.account_id = chosen.get("id")
            self.cfg["tiktok_uid"] = self.account_name
            self.log.info(f"{GREEN}✓ Tự động chọn tài khoản TikTok duy nhất:{RESET} {CYAN}@{self.account_name}{RESET} (ID: {self.account_id})")
            return

        # 2. Nếu có từ 2 tài khoản trở lên -> Luôn hiện menu để người dùng chọn (Enter = tài khoản mặc định)
        default_idx = 1
        for idx, acc in enumerate(acc_list, start=1):
            if saved_uid and (acc.get("name") or acc.get("username")) == saved_uid:
                default_idx = idx
                break

        if not (sys.stdin and sys.stdin.isatty()):
            chosen = acc_list[default_idx - 1]
            self.account_name = chosen.get("name") or chosen.get("username")
            self.account_id = chosen.get("id")
            self.cfg["tiktok_uid"] = self.account_name
            self.log.info(f"{GREEN}✓ Đang dùng tài khoản TikTok:{RESET} {CYAN}@{self.account_name}{RESET} (ID: {self.account_id})")
            return

        render_accounts_table("TikTok", acc_list, default_idx)

        def_name = acc_list[default_idx - 1].get("name") or acc_list[default_idx - 1].get("username")
        prompt_txt = f"{CYAN}›{RESET} Chọn tài khoản [1-{len(acc_list)}] {CYAN}(Enter = @{def_name}){RESET}: "

        selected_idx = default_idx
        try:
            choice = input(prompt_txt).strip()
            if choice.isdigit() and 1 <= int(choice) <= len(acc_list):
                selected_idx = int(choice)
        except KeyboardInterrupt:
            print()
            sys.exit(130)
        except EOFError:
            # Không thể đọc input (chạy headless / pipe): dùng tài khoản mặc định
            # thay vì thoát — người dùng vẫn có thể đổi bằng config tiktok_uid.
            self.log.info(
                f"{YELLOW}[i] Không đọc được input, dùng tài khoản mặc định:{RESET} "
                f"{CYAN}@{def_name}{RESET}"
            )

        chosen = acc_list[selected_idx - 1]
        self.account_name = chosen.get("name") or chosen.get("username")
        self.account_id = chosen.get("id")
        self.cfg["tiktok_uid"] = self.account_name

        self.log.info(f"{GREEN}✓ Đã chọn tài khoản TikTok:{RESET} {CYAN}@{self.account_name}{RESET} (ID: {self.account_id})")

        # Lưu lại vào config.json
        if self.cfg.get("tiktok_uid") != saved_uid:
            save_config(self.cfg)

    def setup(self):
        """Đăng nhập f4f, chọn tài khoản TikTok và kết nối ADB."""
        user = self.cfg.get("f4f_user")
        pwd = self.cfg.get("f4f_pass")
        if not user or not pwd or user == "your_f4f_username":
            self.log.error("Chưa cấu hình tài khoản follow4follow trong config.json!")
            sys.exit(1)

        self.log.info("Đang đăng nhập follow4follow.net ...")
        self.api.login(user, pwd, verbose=False)
        u_info = self.api.user
        self.log.info(
            f"{GREEN}✓ Đăng nhập thành công:{RESET} {u_info['username']} | "
            f"Coin hiện có: {YELLOW}{u_info['balance']}{RESET} | "
            f"Level: {u_info.get('level', {}).get('name', 'N/A')}"
        )

        self._select_tiktok_account()

        self.connect_device()

        pkg = self.cfg.get("tiktok_package", "auto")
        try:
            self.package_name = (
                pkg if pkg and pkg != "auto" else self.adb.detect_tiktok_package()
            )
        except RuntimeError as e:
            self.log.error(f"{RED}[Logo/App] {e}{RESET}")
            sys.exit(1)
        self.log.info(f"TikTok Package: {CYAN}{self.package_name}{RESET}")

        self._ensure_tiktok_running()

    def _ensure_tiktok_running(self):
        """Bảo đảm ứng dụng TikTok đang chạy trên màn hình."""
        if self.adb.current_package() != self.package_name:
            self.log.info("Mở ứng dụng TikTok...")
            self.adb.shell(f"monkey -p {self.package_name} -c android.intent.category.LAUNCHER 1")
            time.sleep(3)
            self.adb.dismiss_popups(package=self.package_name)
            if self.adb.current_package() != self.package_name:
                self.log.warning(
                    "Không xác nhận được TikTok đã mở. Job đầu tiên có thể bị bỏ qua."
                )

    def process_job(self, job: Dict[str, Any]) -> str:
        """Xử lý 1 job (Tự động nhận diện Follow hoặc Like)."""
        type_job = job.get("type_job", "follow").lower()
        if type_job == "like":
            return self._do_like(job)
        else:
            return self._do_follow(job)

    def _do_follow(self, job: Dict[str, Any]) -> str:
        """Thực hiện job Follow tài khoản TikTok."""
        job_id = job.get("id")
        object_id = str(job.get("object_id") or "").strip()
        reward = int(job.get("reward_amount", 26))
        remains = job.get("remains", "?")

        if not job_id or not object_id:
            self.log.warning("  [!] Job thiếu id/object_id -> Bỏ qua")
            self.stats["skipped"] += 1
            self._skip(job, "missing_job_data")
            return "skipped"

        self.log.info(f"{'─'*50}")
        self.log.info(
            f"Job #{job_id} [FOLLOW] │ {CYAN}@{object_id}{RESET} │ "
            f"Reward: {YELLOW}{reward} coin{RESET} │ Còn: {remains}"
        )

        ok = self.adb.open_tiktok_profile(object_id, package_name=self.package_name)
        if not ok:
            self.log.warning(f"  [!] Không mở được trang cá nhân @{object_id}")
            self.stats["skipped"] += 1
            self._skip(job, "open_failed")
            return "skipped"

        time.sleep(random.uniform(1.5, 2.5))
        self.adb.dismiss_popups(package=self.package_name)

        # Xác minh đã mở đúng profile trước khi bấm Follow.
        if not self.adb.wait_handle(
            object_id,
            package=self.package_name,
            timeout=self.cfg.get("profile_load_timeout", 8),
        ):
            self.log.warning(
                f"  [!] Không xác minh được profile @{object_id} đã tải xong -> Bỏ qua job"
            )
            self.stats["skipped"] += 1
            self._skip(job, "profile_not_loaded")
            return "skipped"

        state = self.adb.follow_profile(
            package=self.package_name,
            load_timeout=self.cfg.get("profile_load_timeout", 8),
            verify_timeout=self.cfg.get("verify_timeout", 3),
        )

        res = "skipped"
        if state == "already":
            self.log.info(f"  {YELLOW}ℹ Đã follow từ trước! Nhận thưởng...{RESET}")
            res = self._report_success(
                job_id, reward, "already", "already",
                type_job="follow", object_id=object_id,
            )

        elif state == "clicked":
            self.log.info(f"  {GREEN}✓ Đã follow thành công!{RESET}")
            res = self._report_success(
                job_id, reward, "followed", "followed",
                type_job="follow", object_id=object_id,
            )

        elif state == "click_unverified":
            # UI có thể cập nhật chậm; kiểm tra thêm một lần trước khi kết luận.
            time.sleep(2.0)
            recheck, _ = self.adb.get_follow_state(package=self.package_name)
            if recheck in ("followed", "requested"):
                self.log.info(f"  {GREEN}✓ Đã follow thành công (xác minh lại)!{RESET}")
                res = self._report_success(
                    job_id, reward, "followed", "followed",
                    type_job="follow", object_id=object_id,
                )
            else:
                self.log.warning(
                    f"  {RED}✗ Đã bấm Follow nhưng chưa xác minh được -> Bỏ qua job{RESET}"
                )
                self.stats["skipped"] += 1
                self._skip(job, "follow_unverified")
                res = "skipped"

        elif state == "requested":
            self.log.info(f"  {YELLOW}ℹ Tài khoản riêng tư (Đã gửi yêu cầu theo dõi)! Nhận thưởng...{RESET}")
            res = self._report_success(
                job_id, reward, "followed", "followed",
                type_job="follow", object_id=object_id,
            )

        else:
            self.log.warning(f"  {RED}✗ Không tìm thấy nút follow (state={state}) -> Bỏ qua job{RESET}")
            self.stats["skipped"] += 1
            self._skip(job, f"state_{state}")
            res = "skipped"

        # Follow thì back 1 lần để thoát trang profile
        self._back_home()
        return res

    def _back_home(self):
        """Quay lại sau khi tương tác xong profile để dọn dẹp activity stack."""
        try:
            self.adb.back()
        except Exception:
            pass

    def _do_like(self, job: Dict[str, Any]) -> str:
        """Thực hiện job Like video TikTok."""
        job_id = job.get("id")
        target = job.get("link") or job.get("original_link") or job.get("object_id")
        reward = int(job.get("reward_amount", 10))
        remains = job.get("remains", "?")

        if not job_id or not target:
            self.log.warning("  [!] Job thiếu id/link video -> Bỏ qua")
            self.stats["skipped"] += 1
            self._skip(job, "missing_job_data")
            return "skipped"

        self.log.info(f"{'─'*50}")
        self.log.info(
            f"Job #{job_id} [LIKE] │ {CYAN}{target}{RESET} │ "
            f"Reward: {YELLOW}{reward} coin{RESET} │ Còn: {remains}"
        )

        before_sig = self.adb.get_current_video_info(package=self.package_name)
        ok = self.adb.open_tiktok_video(target, package_name=self.package_name)
        if not ok:
            self.log.warning("  [!] Lỗi lệnh adb mở video -> Bỏ qua job")
            self.stats["skipped"] += 1
            self._skip(job, "open_failed")
            return "skipped"

        load_res = self.adb.wait_video_loaded(
            package=self.package_name,
            timeout=self.cfg.get("profile_load_timeout", 8),
            before_sig=before_sig,
        )

        if load_res == "unavailable":
            self.log.warning(f"  {YELLOW}⚠ Video bị xóa, riêng tư hoặc không khả dụng -> Tự động bỏ qua job{RESET}")
            self.stats["skipped"] += 1
            self._skip(job, "video_unavailable")
            return "skipped"

        if load_res == "unchanged":
            # Bắn deeplink OK nhưng màn hình không đổi sang video đích:
            # TikTok build trill không hiện trang lỗi cho video đã bị xóa.
            self.log.warning(
                f"  {YELLOW}⚠ Video không mở được (có thể đã bị tác giả xóa) -> Bỏ qua job{RESET}"
            )
            self.stats["skipped"] += 1
            self._skip(job, "video_unavailable")
            return "skipped"

        if not load_res:
            self.log.warning(
                f"  {YELLOW}⚠ Không xác định được video đã tải xong -> Bỏ qua job{RESET}"
            )
            self.stats["skipped"] += 1
            self._skip(job, "video_load_timeout")
            return "skipped"

        state = self.adb.like_video(
            package=self.package_name,
            load_timeout=3,
            verify_timeout=self.cfg.get("verify_timeout", 3),
        )

        if state == "already":
            self.log.info(f"  {YELLOW}ℹ Video đã like từ trước! Nhận thưởng...{RESET}")
            return self._report_success(
                job_id, reward, "already", "already",
                type_job="like", object_id=str(target),
            )

        if state == "clicked":
            self.log.info(f"  {GREEN}✓ Đã thả tim (Like) video thành công!{RESET}")
            return self._report_success(
                job_id, reward, "liked", "liked",
                type_job="like", object_id=str(target),
            )

        if state == "click_unverified":
            time.sleep(2.0)
            recheck, _ = self.adb.get_like_state(package=self.package_name)
            if recheck == "liked":
                self.log.info(f"  {GREEN}✓ Đã thả tim thành công (xác minh lại)!{RESET}")
                return self._report_success(
                    job_id, reward, "liked", "liked",
                    type_job="like", object_id=str(target),
                )
            self.log.warning(
                f"  {RED}✗ Đã bấm Like nhưng chưa xác minh được -> Bỏ qua job{RESET}"
            )
            self.stats["skipped"] += 1
            self._skip(job, "like_unverified")
            return "skipped"

        self.log.warning(f"  {RED}✗ Video không tương tác được (state={state}) -> Bỏ qua job{RESET}")
        self.stats["skipped"] += 1
        self._skip(job, f"like_state_{state}")
        return "skipped"

    def _report_success(
        self,
        job_id: int,
        reward: int,
        stat_key: str,
        result: str,
        type_job: str = "follow",
        object_id: Optional[str] = None,
    ) -> str:
        """Chỉ ghi nhận thành công khi F4F xác nhận complete-job."""
        if self._complete(job_id, reward, type_job=type_job, object_id=object_id):
            self.stats[stat_key] += 1
            return result
        return "error"

    def _complete(
        self,
        job_id: int,
        reward: int,
        type_job: str = "follow",
        object_id: Optional[str] = None,
        retries: int = 2,
    ) -> bool:
        """
        Gửi API báo cáo hoàn thành job lên F4F.

        Chỉ thử lại các lỗi 400 mang tính tạm thời (server đang bận/đồng bộ).
        Không gọi skip-job khi complete thất bại để tránh làm mất job/coin.
        """
        busy_hints = (
            "đang bận", "hệ thống bận", "đồng bộ",
            "busy", "try again", "sync",
        )
        retry_delays = (10, 30)

        for attempt in range(retries + 1):
            try:
                res = self.api.complete_job_api("tiktok", job_id, self.account_id, type_job=type_job)
                try:
                    earned = int((res.get("data") or {}).get("coin_received") or reward)
                except (TypeError, ValueError, AttributeError):
                    earned = reward
                self.stats["coins_earned"] += earned
                self.log.info(
                    f"  {GREEN}💰 Nhận thành công +{earned} coin! "
                    f"(Tổng kiếm: ~{self.stats['coins_earned']} coin){RESET}"
                )
                return True
            except Exception as e:
                message = str(e)
                is_400 = "400" in message
                is_transient = is_400 and any(hint in message.lower() for hint in busy_hints)
                if is_transient and attempt < retries:
                    wait = retry_delays[min(attempt, len(retry_delays) - 1)]
                    self.log.warning(
                        f"  -> F4F đang kiểm tra/đồng bộ dữ liệu, thử lại sau {wait}s..."
                    )
                    time.sleep(wait)
                    continue
                self.log.error(
                    f"  {RED}[!] Lỗi báo cáo complete-job cho job #{job_id} "
                    f"(@{object_id}): {message}{RESET}"
                )
                self.log.warning(
                    "  -> Giữ nguyên job để có thể nhận lại sau; không tự động skip."
                )
                return False
        return False

    def _skip(self, job: Dict[str, Any], reason: str = ""):
        """Gửi API skip job lên F4F."""
        job_id = job.get("id")
        if job_id is None:
            self.log.warning("  [!] Không thể skip job thiếu id.")
            return
        try:
            self.api.skip_job_api(
                "tiktok", job_id, self.account_id, self.account_name,
                str(job.get("object_id") or ""),
            )
            self.log.info(
                f"  {YELLOW}↷ Đã gửi yêu cầu bỏ qua (skip) job #{job_id}"
                f"{f' [{reason}]' if reason else ''}{RESET}"
            )
        except Exception as e:
            self.log.error(f"  [!] Lỗi skip job: {e}")

    def run(self, max_jobs: Optional[int] = None):
        """Vòng lặp chính thực hiện job TikTok."""
        self.setup()
        max_jobs = max_jobs or self.cfg.get("max_jobs_per_session", 50)

        types_to_run = ["follow", "like"] if self.job_type == "all" else [self.job_type]
        types_str = " & ".join(t.upper() for t in types_to_run)
        self.log.info(f"Bắt đầu phiên chạy TikTok ({types_str}): Tối đa {max_jobs} job(s)")

        total_processed = 0
        consecutive_errors = 0

        while total_processed < max_jobs:
            jobs_found_in_round = False

            for t_job in types_to_run:
                if total_processed >= max_jobs:
                    break

                try:
                    data = self.api.get_job_tiktok(self.account_name, type_job=t_job)
                    jobs = data.get("data", {}).get("jobs", [])
                except Exception as e:
                    self.log.error(f"Lỗi gọi API lấy job ({t_job}): {e}")
                    time.sleep(3)
                    continue

                if not jobs:
                    continue

                # Bỏ job trùng trong cùng batch và job đã thử quá số lần cho phép.
                new_jobs = []
                seen_in_batch = set()
                for job in jobs:
                    job_id = job.get("id")
                    if job_id is None:
                        continue
                    key = str(job_id)
                    if key in seen_in_batch:
                        continue
                    seen_in_batch.add(key)
                    if not self.can_attempt_job(key):
                        continue
                    new_jobs.append(job)

                if not new_jobs:
                    continue

                jobs_found_in_round = True
                for job in new_jobs:
                    if total_processed >= max_jobs:
                        break

                    job["type_job"] = t_job
                    self.mark_job_attempt(job["id"])

                    try:
                        result = self.process_job(job)
                    except Exception as e:
                        self.log.exception(f"Lỗi xử lý job #{job.get('id')}: {e}")
                        result = "error"

                    total_processed += 1
                    self.jobs_since_human += 1

                    if result in ("followed", "liked", "already", "skipped"):
                        consecutive_errors = 0
                    else:
                        self.stats["errors"] += 1
                        consecutive_errors += 1

                    if consecutive_errors >= 5:
                        self.log.error(f"{RED}Gặp 5 lỗi liên tiếp! Tạm dừng 30s...{RESET}")
                        time.sleep(30)
                        consecutive_errors = 0

                    # Anti-Ban lướt feed
                    self.trigger_anti_ban()

                    # Nghỉ delay
                    if total_processed < max_jobs:
                        self.sleep_delay()

            if not jobs_found_in_round and total_processed < max_jobs:
                self.log.info(f"{YELLOW}Hết job khả dụng ({types_str}). Chờ 25s rồi thử lại...{RESET}")
                time.sleep(25)

        self.print_summary()
