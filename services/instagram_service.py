"""
services/instagram_service.py — Nghiệp vụ tự động hóa Instagram (Follow)
========================================================================
Hỗ trợ:
  - Tự động lấy danh sách tài khoản Instagram liên kết từ F4F API
  - Nhận job Follow Instagram (+35 xu/job)
  - Mở trang cá nhân qua Intent
  - Nhận diện nút Follow đặc trưng (profile_header_follow_button)
  - Báo cáo nhận coin hoặc skip job lỗi
  - Tích hợp Anti-Ban lướt feed mô phỏng người thật
"""

import sys
import time
import random
from typing import Optional, Dict, Any

from core.helpers import CYAN, GREEN, YELLOW, RED, RESET, extract_handle
from core.ui import render_accounts_table
from api.f4f_client import ApiF4F
from services.base_runner import BaseJobRunner
from config.settings import save_config


class InstagramJobRunner(BaseJobRunner):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(platform_name="Instagram", config=config)
        self.api = ApiF4F()
        self.username = None
        self.account_id = None

    def _select_instagram_account(self):
        """Lấy và chọn tài khoản Instagram từ F4F."""
        self.log.info("Lấy danh sách tài khoản Instagram liên kết trên F4F...")
        try:
            acc_list = self.api.get_active_accounts("instagram")
        except Exception as e:
            self.log.error(f"Lỗi gọi API F4F lấy tài khoản Instagram: {e}")
            sys.exit(1)

        acc_list = [
            acc for acc in acc_list
            if (acc.get("username") or acc.get("name")) and acc.get("id") is not None
        ]

        if not acc_list:
            self.log.error(f"{RED}Không tìm thấy tài khoản Instagram nào đang hoạt động trên F4F!{RESET}")
            self.log.error("Vui lòng vào follow4follow.net -> Thêm tài khoản Instagram trước khi chạy.")
            sys.exit(1)

        saved_user = self.cfg.get("instagram_username", "").strip()

        # 1. Nếu chỉ có 1 tài khoản duy nhất -> Tự động dùng
        if len(acc_list) == 1:
            chosen = acc_list[0]
            self.username = chosen.get("username") or chosen.get("name")
            self.account_id = chosen.get("id")
            self.cfg["instagram_username"] = self.username
            self.log.info(f"{GREEN}✓ Tự động chọn tài khoản Instagram:{RESET} {CYAN}@{self.username}{RESET} (ID: {self.account_id})")
            return

        # 2. Nếu có nhiều tài khoản -> Hiển thị menu chọn
        default_idx = 1
        for idx, acc in enumerate(acc_list, start=1):
            if saved_user and (acc.get("username") or acc.get("name")) == saved_user:
                default_idx = idx
                break

        # Môi trường không tương tác (pipe, cron, Termux không TTY):
        # tự chọn tài khoản mặc định thay vì gọi input() rồi thoát.
        if not (sys.stdin and sys.stdin.isatty()):
            chosen = acc_list[default_idx - 1]
            self.username = chosen.get("username") or chosen.get("name")
            self.account_id = chosen.get("id")
            self.cfg["instagram_username"] = self.username
            self.log.info(
                f"{GREEN}✓ Đang dùng tài khoản Instagram:{RESET} "
                f"{CYAN}@{self.username}{RESET} (ID: {self.account_id})"
            )
            return

        render_accounts_table("Instagram", acc_list, default_idx)

        def_name = acc_list[default_idx - 1].get("username") or acc_list[default_idx - 1].get("name")
        selected_idx = default_idx
        try:
            choice = input(f"{CYAN}›{RESET} Chọn tài khoản Instagram [1-{len(acc_list)}] {CYAN}(Enter = @{def_name}){RESET}: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(acc_list):
                selected_idx = int(choice)
        except KeyboardInterrupt:
            print()
            sys.exit(130)
        except EOFError:
            # Không thể đọc input (headless/pipe): dùng tài khoản mặc định.
            self.log.info(
                f"{YELLOW}[i] Không đọc được input, dùng tài khoản mặc định:{RESET} "
                f"{CYAN}@{def_name}{RESET}"
            )

        chosen = acc_list[selected_idx - 1]
        self.username = chosen.get("username") or chosen.get("name")
        self.account_id = chosen.get("id")
        self.cfg["instagram_username"] = self.username
        self.log.info(f"{GREEN}✓ Đã chọn tài khoản Instagram:{RESET} {CYAN}@{self.username}{RESET} (ID: {self.account_id})")

        if self.cfg.get("instagram_username") != saved_user:
            save_config(self.cfg)

    def setup(self):
        """Đăng nhập F4F, chọn tài khoản và kết nối ADB."""
        user = self.cfg.get("f4f_user")
        pwd = self.cfg.get("f4f_pass")
        if not user or not pwd or user == "your_f4f_username":
            self.log.error("Chưa cấu hình tài khoản Follow4Follow trong config.json!")
            sys.exit(1)

        self.log.info("Đang đăng nhập Follow4Follow ...")
        self.api.login(user, pwd, verbose=False)
        u_info = self.api.user
        self.log.info(
            f"{GREEN}✓ Đăng nhập thành công:{RESET} {u_info['username']} | "
            f"Số dư: {YELLOW}{u_info['balance']} xu{RESET} | Chờ: {u_info['balance_pending']} xu"
        )

        self._select_instagram_account()

        self.connect_device()

        pkg_cfg = self.cfg.get("instagram_package", "auto")
        try:
            self.package_name = (
                pkg_cfg if pkg_cfg and pkg_cfg != "auto"
                else self.adb.detect_instagram_package()
            )
        except RuntimeError as e:
            self.log.error(f"{RED}[Logo/App] {e}{RESET}")
            sys.exit(1)
        self.log.info(f"Instagram Package: {CYAN}{self.package_name}{RESET}")

        self._ensure_instagram_running()

    def _ensure_instagram_running(self):
        """Khởi động ứng dụng Instagram nếu chưa bật."""
        if self.adb.current_package() != self.package_name:
            self.log.info("Mở ứng dụng Instagram...")
            self.adb.shell(f"monkey -p {self.package_name} -c android.intent.category.LAUNCHER 1")
            time.sleep(3)
            self.adb.dismiss_popups(package=self.package_name)
            if self.adb.current_package() != self.package_name:
                self.log.warning(
                    "Không xác nhận được Instagram đã mở. Job đầu tiên có thể bị bỏ qua."
                )

    def process_job(self, job: Dict[str, Any]) -> str:
        """Xử lý 1 job Follow Instagram."""
        job_id = job.get("id")
        object_id = str(job.get("object_id") or "").strip()
        reward = int(job.get("reward_amount", 35))
        remains = job.get("remains", "?")

        if not job_id or not object_id:
            self.log.warning("  [!] Job thiếu id/object_id -> Bỏ qua")
            self.stats["skipped"] += 1
            self._skip(job_id, object_id, "missing_job_data")
            return "skipped"

        self.log.info(f"{'─'*50}")
        self.log.info(
            f"Job #{job_id} [INSTAGRAM] │ {CYAN}@{object_id}{RESET} │ "
            f"Reward: {YELLOW}{reward} xu{RESET} │ Còn: {remains}"
        )

        ok = self.adb.open_instagram_profile(object_id, package_name=self.package_name)
        if not ok:
            self.log.warning(f"  [!] Không thể mở trang cá nhân @{object_id} -> Bỏ qua job")
            self.stats["skipped"] += 1
            self._skip(job_id, object_id, "open_failed")
            return "skipped"

        time.sleep(random.uniform(1.8, 2.8))
        self.adb.dismiss_popups(package=self.package_name)

        # Xác minh đã mở đúng profile trước khi bấm Follow.
        handle = extract_handle(object_id) or object_id
        if not self.adb.wait_handle(
            handle,
            package=self.package_name,
            timeout=self.cfg.get("profile_load_timeout", 8),
        ):
            self.log.warning(
                f"  [!] Không xác minh được profile @{object_id} đã tải xong -> Bỏ qua job"
            )
            self.stats["skipped"] += 1
            self._skip(job_id, object_id, "profile_not_loaded")
            return "skipped"

        state = self.adb.follow_profile(
            package=self.package_name,
            load_timeout=self.cfg.get("profile_load_timeout", 8),
            verify_timeout=self.cfg.get("verify_timeout", 3),
        )

        if state == "already":
            self.log.info(f"  {YELLOW}ℹ Đã follow @{object_id} từ trước! Nhận thưởng...{RESET}")
            return self._report_success(job_id, reward, "already", "already", object_id)

        if state == "clicked":
            self.log.info(f"  {GREEN}✓ Đã bấm Follow @{object_id} thành công!{RESET}")
            return self._report_success(job_id, reward, "followed", "followed", object_id)

        if state == "click_unverified":
            # UI Instagram có thể cập nhật chậm; kiểm tra thêm một lần.
            time.sleep(2.0)
            recheck, _ = self.adb.get_follow_state(package=self.package_name)
            if recheck in ("followed", "requested"):
                self.log.info(f"  {GREEN}✓ Đã bấm Follow thành công (xác minh lại)!{RESET}")
                return self._report_success(job_id, reward, "followed", "followed", object_id)
            self.log.warning(
                f"  {RED}✗ Đã bấm Follow nhưng chưa xác minh được -> Bỏ qua job{RESET}"
            )
            self.stats["skipped"] += 1
            self._skip(job_id, object_id, "follow_unverified")
            return "skipped"

        if state == "requested":
            self.log.info(f"  {YELLOW}ℹ Tài khoản riêng tư (Đã gửi yêu cầu theo dõi)! Nhận thưởng...{RESET}")
            return self._report_success(job_id, reward, "followed", "followed", object_id)

        self.log.warning(f"  {RED}✗ Không tìm thấy nút Follow hoặc trang lỗi (state={state}) -> Bỏ qua job{RESET}")
        self.stats["skipped"] += 1
        self._skip(job_id, object_id, f"state_{state}")
        return "skipped"

    def _report_success(
        self, job_id: int, reward: int, stat_key: str, result: str, object_id: str
    ) -> str:
        """Chỉ ghi nhận thành công khi F4F xác nhận complete-job."""
        if self._complete(job_id, reward, object_id=object_id):
            self.stats[stat_key] += 1
            return result
        return "error"

    def _complete(
        self,
        job_id: int,
        reward: int,
        object_id: Optional[str] = None,
        retries: int = 2,
    ) -> bool:
        """
        Báo cáo hoàn thành job Instagram.

        Chỉ thử lại lỗi 400 tạm thời (server bận/đồng bộ); không skip job khi
        complete thất bại để tránh mất job/coin của người dùng.
        """
        busy_hints = (
            "đang bận", "hệ thống bận", "đồng bộ",
            "busy", "try again", "sync",
        )
        retry_delays = (10, 30)

        for attempt in range(retries + 1):
            try:
                res = self.api.complete_job_ig(job_id, self.account_id, type_job="follow")
                try:
                    earned = int((res.get("data") or {}).get("coin_received") or reward)
                except (TypeError, ValueError, AttributeError):
                    earned = reward
                self.stats["coins_earned"] += earned
                self.log.info(
                    f"  {GREEN}💰 Nhận thành công +{earned} xu! "
                    f"(Tổng kiếm: ~{self.stats['coins_earned']} xu){RESET}"
                )
                return True
            except Exception as e:
                message = str(e)
                is_400 = "400" in message
                is_transient = is_400 and any(hint in message.lower() for hint in busy_hints)
                if is_transient and attempt < retries:
                    wait = retry_delays[min(attempt, len(retry_delays) - 1)]
                    self.log.warning(
                        f"  -> F4F đang kiểm tra/đồng bộ dữ liệu Instagram, thử lại sau {wait}s..."
                    )
                    time.sleep(wait)
                    continue
                self.log.error(
                    f"  {RED}[!] Lỗi báo cáo complete-job F4F cho job #{job_id} "
                    f"(@{object_id}): {message}{RESET}"
                )
                self.log.warning(
                    "  -> Giữ nguyên job để có thể nhận lại sau; không tự động skip."
                )
                return False
        return False

    def _skip(self, job_id, object_id: str, reason: str = ""):
        try:
            self.api.skip_job_ig(job_id, self.account_id, self.username, object_id)
            self.log.info(
                f"  {YELLOW}↷ Đã gửi yêu cầu bỏ qua (skip) job #{job_id}"
                f"{f' [{reason}]' if reason else ''}{RESET}"
            )
        except Exception as e:
            self.log.error(f"  [!] Lỗi skip job F4F: {e}")

    def run(self, max_jobs: Optional[int] = None):
        """Vòng lặp chạy auto jobs Follow Instagram."""
        self.setup()
        max_jobs = max_jobs or self.cfg.get("max_jobs_per_session", 50)
        self.log.info(f"Bắt đầu phiên chạy Instagram: Tối đa {max_jobs} job(s)")

        total_processed = 0
        consecutive_errors = 0

        while total_processed < max_jobs:
            try:
                job_data = self.api.get_job_ig(self.username, type_job="follow")
                jobs = job_data.get("data", {}).get("jobs", [])
            except Exception as e:
                self.log.error(f"Lỗi lấy job từ F4F: {e}")
                time.sleep(5)
                continue

            if not jobs:
                self.log.info(f"{YELLOW}Hiện tại chưa có job Instagram mới. Chờ 20s thử lại...{RESET}")
                time.sleep(20)
                continue

            # Bỏ job trùng trong batch và job đã thử quá số lần cho phép.
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
                self.log.info(f"{YELLOW}Không còn job Instagram mới. Chờ 20s thử lại...{RESET}")
                time.sleep(20)
                continue

            for job in new_jobs:
                if total_processed >= max_jobs:
                    break

                self.mark_job_attempt(job["id"])
                try:
                    res = self.process_job(job)
                except Exception as e:
                    self.log.exception(f"Lỗi xử lý job #{job.get('id')}: {e}")
                    res = "error"

                total_processed += 1
                self.jobs_since_human += 1

                if res in ("followed", "already", "skipped"):
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

                # Delay ngẫu nhiên giữa các job
                if total_processed < max_jobs:
                    self.sleep_delay()

        self.print_summary()
