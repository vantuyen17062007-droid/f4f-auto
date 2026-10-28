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

from core.helpers import CYAN, GREEN, YELLOW, RED, WHITE, RESET
from core.ui import render_accounts_table
from core.adb import AdbController
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

        if not acc_list:
            self.log.error(f"{RED}Không tìm thấy tài khoản Instagram nào liên kết trên F4F!{RESET}")
            self.log.error("Vui lòng vào follow4follow.net -> Thêm tài khoản Instagram trước khi chạy.")
            sys.exit(1)

        saved_user = self.cfg.get("instagram_username", "").strip()

        # 1. Nếu chỉ có 1 tài khoản duy nhất -> Tự động dùng
        if len(acc_list) == 1:
            chosen = acc_list[0]
            self.username = chosen.get("username")
            self.account_id = chosen.get("id")
            self.cfg["instagram_username"] = self.username
            self.log.info(f"{GREEN}✓ Tự động chọn tài khoản Instagram:{RESET} {CYAN}@{self.username}{RESET} (ID: {self.account_id})")
            return

        # 2. Nếu có nhiều tài khoản -> Hiển thị menu chọn
        default_idx = 1
        for idx, acc in enumerate(acc_list, start=1):
            if saved_user and acc.get("username") == saved_user:
                default_idx = idx
                break

        render_accounts_table("Instagram", acc_list, default_idx)

        def_name = acc_list[default_idx - 1].get("username")
        selected_idx = default_idx
        try:
            choice = input(f"{CYAN}›{RESET} Chọn tài khoản Instagram [1-{len(acc_list)}] {CYAN}(Enter = @{def_name}){RESET}: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(acc_list):
                selected_idx = int(choice)
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)

        chosen = acc_list[selected_idx - 1]
        self.username = chosen.get("username")
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

        serial = self.cfg.get("adb_serial", "auto")
        self.log.info(f"Đang kết nối thiết bị ADB ({serial}) ...")
        self.adb = AdbController(serial=serial)
        w, h = self.adb.get_screen_size()
        self.log.info(f"{GREEN}✓ ADB sẵn sàng:{RESET} Màn hình {w}x{h}")

        pkg_cfg = self.cfg.get("instagram_package", "auto")
        if not pkg_cfg or pkg_cfg == "auto":
            self.package_name = self.adb.detect_instagram_package()
        else:
            self.package_name = pkg_cfg
        self.log.info(f"Instagram Package: {CYAN}{self.package_name}{RESET}")

        self._ensure_instagram_running()

    def _ensure_instagram_running(self):
        """Khởi động ứng dụng Instagram nếu chưa bật."""
        current = self.adb.shell("dumpsys window | grep mCurrentFocus")
        if self.package_name not in current:
            self.log.info("Mở ứng dụng Instagram...")
            self.adb.shell(f"monkey -p {self.package_name} -c android.intent.category.LAUNCHER 1")
            time.sleep(3)
            self.adb.dismiss_popups(package=self.package_name)

    def process_job(self, job: Dict[str, Any]) -> str:
        """Xử lý 1 job Follow Instagram."""
        job_id = job["id"]
        object_id = job.get("object_id") or ""
        reward = int(job.get("reward_amount", 35))
        remains = job.get("remains", "?")

        self.log.info(f"{'─'*50}")
        self.log.info(
            f"Job #{job_id} [INSTAGRAM] │ {CYAN}@{object_id}{RESET} │ "
            f"Reward: {YELLOW}{reward} xu{RESET} │ Còn: {remains}"
        )

        ok = self.adb.open_instagram_profile(object_id, package_name=self.package_name)
        if not ok:
            self.log.warning(f"  [!] Không thể mở trang cá nhân @{object_id} -> Bỏ qua job")
            self.stats["skipped"] += 1
            self._skip(job_id, object_id)
            return "skipped"

        time.sleep(random.uniform(1.8, 2.8))
        self.adb.dismiss_popups(package=self.package_name)

        state = self.adb.follow_profile(
            package=self.package_name,
            load_timeout=self.cfg.get("profile_load_timeout", 8),
            verify_timeout=self.cfg.get("verify_timeout", 3),
        )

        if state == "already":
            self.log.info(f"  {YELLOW}ℹ Đã follow @{object_id} từ trước! Nhận thưởng...{RESET}")
            self.stats["already"] += 1
            self._complete(job_id, reward)
            return "already"

        if state in ("clicked", "click_unverified"):
            self.log.info(f"  {GREEN}✓ Đã bấm Follow @{object_id} thành công!{RESET}")
            self.stats["followed"] += 1
            self._complete(job_id, reward)
            return "followed"

        if state == "requested":
            self.log.info(f"  {YELLOW}ℹ Tài khoản riêng tư (Đã gửi yêu cầu theo dõi)! Nhận thưởng...{RESET}")
            self.stats["followed"] += 1
            self._complete(job_id, reward)
            return "followed"

        self.log.warning(f"  {RED}✗ Không tìm thấy nút Follow hoặc trang lỗi (state={state}) -> Bỏ qua job{RESET}")
        self.stats["skipped"] += 1
        self._skip(job_id, object_id)
        return "skipped"

    def _complete(self, job_id: int, reward: int, retries: int = 1):
        for attempt in range(retries + 1):
            try:
                res = self.api.complete_job_ig(job_id, self.account_id, type_job="follow")
                earned = int(res.get("data", {}).get("coin_received") or reward)
                self.stats["coins_earned"] += earned
                self.log.info(f"  {GREEN}💰 Nhận thành công +{earned} xu! (Tổng kiếm: ~{self.stats['coins_earned']} xu){RESET}")
                return True
            except Exception as e:
                if "400" in str(e) and attempt < retries:
                    self.log.warning("  -> F4F đang đồng bộ dữ liệu Instagram, thử lại sau 3.5s...")
                    time.sleep(3.5)
                    continue
                self.log.error(f"  {RED}[!] Lỗi báo cáo complete-job F4F: {e}{RESET}")
                return False

    def _skip(self, job_id: int, object_id: str):
        try:
            self.api.skip_job_ig(job_id, self.account_id, self.username, object_id)
            self.log.info(f"  {YELLOW}↷ Đã gửi yêu cầu bỏ qua (skip) job #{job_id}{RESET}")
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

            for job in jobs:
                if total_processed >= max_jobs:
                    break

                res = self.process_job(job)
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
