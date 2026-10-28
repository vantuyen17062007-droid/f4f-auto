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
from typing import Optional, Dict, Any, List

from core.helpers import CYAN, GREEN, YELLOW, RED, WHITE, RESET
from core.ui import render_accounts_table
from core.adb import AdbController
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
            res = self.api.get_acc_tik()
            acc_list = res.get("data", {}).get("data", [])
        except Exception as e:
            self.log.error(f"Lỗi gọi API lấy danh sách tài khoản: {e}")
            sys.exit(1)

        if not acc_list:
            self.log.error(f"{RED}Không tìm thấy tài khoản TikTok nào liên kết trên F4F!{RESET}")
            self.log.error("Vui lòng vào website follow4follow.net -> Thêm tài khoản TikTok trước khi chạy.")
            sys.exit(1)

        saved_uid = self.cfg.get("tiktok_uid", "").strip()

        # 1. Nếu chỉ có duy nhất 1 tài khoản -> Tự động dùng ngay
        if len(acc_list) == 1:
            chosen = acc_list[0]
            self.account_name = chosen["name"]
            self.account_id = chosen["id"]
            self.cfg["tiktok_uid"] = self.account_name
            self.log.info(f"{GREEN}✓ Tự động chọn tài khoản TikTok duy nhất:{RESET} {CYAN}@{self.account_name}{RESET} (ID: {self.account_id})")
            return

        # 2. Nếu có từ 2 tài khoản trở lên -> Luôn hiện menu để người dùng chọn (Enter = tài khoản mặc định)
        default_idx = 1
        for idx, acc in enumerate(acc_list, start=1):
            if saved_uid and acc.get("name") == saved_uid:
                default_idx = idx
                break

        if not sys.stdin.isatty():
            chosen = acc_list[default_idx - 1]
            self.account_name = chosen["name"]
            self.account_id = chosen["id"]
            self.cfg["tiktok_uid"] = self.account_name
            self.log.info(f"{GREEN}✓ Đang dùng tài khoản TikTok:{RESET} {CYAN}@{self.account_name}{RESET} (ID: {self.account_id})")
            return

        render_accounts_table("TikTok", acc_list, default_idx)

        def_name = acc_list[default_idx - 1]["name"]
        prompt_txt = f"{CYAN}›{RESET} Chọn tài khoản [1-{len(acc_list)}] {CYAN}(Enter = @{def_name}){RESET}: "

        selected_idx = default_idx
        try:
            choice = input(prompt_txt).strip()
            if choice.isdigit() and 1 <= int(choice) <= len(acc_list):
                selected_idx = int(choice)
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        chosen = acc_list[selected_idx - 1]
        self.account_name = chosen["name"]
        self.account_id = chosen["id"]
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

        serial = self.cfg.get("adb_serial", "auto")
        self.log.info(f"Đang kết nối thiết bị ADB ({serial}) ...")
        self.adb = AdbController(serial=serial)
        w, h = self.adb.get_screen_size()
        self.log.info(f"{GREEN}✓ ADB sẵn sàng:{RESET} Màn hình {w}x{h}")

        pkg = self.cfg.get("tiktok_package", "auto")
        if not pkg or pkg == "auto":
            self.package_name = self.adb.detect_tiktok_package()
        else:
            self.package_name = pkg
        self.log.info(f"TikTok Package: {CYAN}{self.package_name}{RESET}")

        self._ensure_tiktok_running()

    def _ensure_tiktok_running(self):
        """Bảo đảm ứng dụng TikTok đang chạy trên màn hình."""
        current = self.adb.shell("dumpsys window | grep mCurrentFocus")
        if self.package_name not in current:
            self.log.info("Mở ứng dụng TikTok...")
            self.adb.shell(f"monkey -p {self.package_name} -c android.intent.category.LAUNCHER 1")
            time.sleep(3)
            self.adb.dismiss_popups(package=self.package_name)

    def process_job(self, job: Dict[str, Any]) -> str:
        """Xử lý 1 job (Tự động nhận diện Follow hoặc Like)."""
        type_job = job.get("type_job", "follow").lower()
        if type_job == "like":
            return self._do_like(job)
        else:
            return self._do_follow(job)

    def _do_follow(self, job: Dict[str, Any]) -> str:
        """Thực hiện job Follow tài khoản TikTok."""
        job_id = job["id"]
        object_id = job["object_id"]
        reward = int(job.get("reward_amount", 26))
        remains = job.get("remains", "?")

        self.log.info(f"{'─'*50}")
        self.log.info(
            f"Job #{job_id} [FOLLOW] │ {CYAN}@{object_id}{RESET} │ "
            f"Reward: {YELLOW}{reward} coin{RESET} │ Còn: {remains}"
        )

        ok = self.adb.open_tiktok_profile(object_id, package_name=self.package_name)
        if not ok:
            self.log.warning(f"  [!] Không mở được trang cá nhân @{object_id}")
            self._skip(job, "open_failed")
            return "skipped"

        time.sleep(random.uniform(1.5, 2.5))
        self.adb.dismiss_popups(package=self.package_name)

        state = self.adb.follow_profile(
            package=self.package_name,
            load_timeout=self.cfg.get("profile_load_timeout", 8),
            verify_timeout=self.cfg.get("verify_timeout", 3),
        )

        if state == "already":
            self.log.info(f"  {YELLOW}ℹ Đã follow từ trước! Nhận thưởng...{RESET}")
            self.stats["already"] += 1
            self._complete(job_id, reward)
            return "already"

        if state in ("clicked", "click_unverified"):
            self.log.info(f"  {GREEN}✓ Đã follow thành công!{RESET}")
            self.stats["followed"] += 1
            self._complete(job_id, reward)
            return "followed"

        if state == "requested":
            self.log.info(f"  {YELLOW}ℹ Tài khoản riêng tư (Đã gửi yêu cầu theo dõi)! Nhận thưởng...{RESET}")
            self.stats["followed"] += 1
            self._complete(job_id, reward)
            return "followed"

        self.log.warning(f"  {RED}✗ Không tìm thấy nút follow (state={state}) -> Bỏ qua job{RESET}")
        self.stats["skipped"] += 1
        self._skip(job, f"state_{state}")
        return "skipped"

    def _do_like(self, job: Dict[str, Any]) -> str:
        """Thực hiện job Like video TikTok."""
        job_id = job["id"]
        target = job.get("link") or job.get("original_link") or job.get("object_id")
        reward = int(job.get("reward_amount", 10))
        remains = job.get("remains", "?")

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

        state = self.adb.like_video(
            package=self.package_name,
            load_timeout=3,
            verify_timeout=self.cfg.get("verify_timeout", 3),
        )

        if state == "already":
            self.log.info(f"  {YELLOW}ℹ Video đã like từ trước! Nhận thưởng...{RESET}")
            self.stats["already"] += 1
            self._complete(job_id, reward, type_job="like")
            return "already"

        if state in ("clicked", "click_unverified"):
            self.log.info(f"  {GREEN}✓ Đã thả tim (Like) video thành công!{RESET}")
            self.stats["liked"] += 1
            self._complete(job_id, reward, type_job="like")
            return "liked"

        self.log.warning(f"  {RED}✗ Video không tương tác được (state={state}) -> Bỏ qua job{RESET}")
        self.stats["skipped"] += 1
        self._skip(job, f"like_state_{state}")
        return "skipped"

    def _complete(self, job_id: int, reward: int, type_job: str = "follow", retries: int = 1):
        """Gửi API báo cáo hoàn thành job lên F4F (hỗ trợ thử lại nếu server trễ đồng bộ)."""
        for attempt in range(retries + 1):
            try:
                res = self.api.complete_job_api("tiktok", job_id, self.account_id, type_job=type_job)
                earned = int(res.get("data", {}).get("coin_received") or reward)
                self.stats["coins_earned"] += earned
                self.log.info(f"  {GREEN}💰 Nhận thành công +{earned} coin! (Tổng kiếm: ~{self.stats['coins_earned']} coin){RESET}")
                return True
            except Exception as e:
                if "400" in str(e) and attempt < retries:
                    self.log.warning("  -> Server F4F đang đồng bộ dữ liệu TikTok, thử lại sau 3.5s...")
                    time.sleep(3.5)
                    continue
                self.log.error(f"  {RED}[!] Lỗi báo cáo complete-job: {e}{RESET}")
                if "400" in str(e):
                    self.log.warning("  -> Server F4F vẫn báo lỗi 400 sau khi thử lại -> Tự động bỏ qua job.")
                    self.api.skip_job_tiktok(job_id, self.account_id, self.account_name, str(job_id))
                return False

    def _skip(self, job: Dict[str, Any], reason: str = ""):
        """Gửi API skip job lên F4F."""
        try:
            self.api.skip_job_api("tiktok", job["id"], self.account_id, self.account_name, str(job.get("object_id") or ""))
            self.log.info(f"  {YELLOW}↷ Đã gửi yêu cầu bỏ qua (skip) job #{job['id']}{RESET}")
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

                jobs_found_in_round = True
                for job in jobs:
                    if total_processed >= max_jobs:
                        break

                    job["type_job"] = t_job
                    result = self.process_job(job)
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
