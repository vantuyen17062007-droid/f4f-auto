"""
Instagram Follow4Follow Auto Job Runner
======================================
Hỗ trợ chạy auto job Follow Instagram kiếm coin trên Follow4Follow:
  - Tự động nhận diện thiết bị ADB (PC hoặc Termux)
  - Tự động nhận diện package Instagram trên máy (com.instagram.android, com.instagram.lite)
  - Tự động chọn tài khoản Instagram liên kết từ F4F API
  - Mở profile qua Intent và nhận diện nút Follow (Theo dõi) chính xác
  - Xác minh trạng thái sau click (Đang theo dõi / Đã yêu cầu)
  - Báo cáo hoàn thành job nhận coin (+35 coin/job)
  - Tự động skip job khi tài khoản bị khóa, đổi tên hoặc lỗi
  - Mô phỏng hành vi người thật (lướt feed) và delay ngẫu nhiên chống checkpoint
"""

import os
import sys
import json
import time
import random
import logging
from datetime import datetime

# Đảm bảo console hiển thị UTF-8 không lỗi
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from api_f4f import ApiF4F
from adbcontrol import AdbController

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(LOG_DIR, f"instagram_{datetime.now():%Y%m%d_%H%M%S}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger("f4f-instagram")

G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
W = "\033[97m"
D = "\033[0m"


def banner():
    print(f"""
{C}╔══════════════════════════════════════════════════════╗
║     Instagram Follow4Follow — Auto Job Runner        ║
║        Hỗ trợ: PC (Windows/Linux) & Phone (Termux)    ║
╚══════════════════════════════════════════════════════╝{D}
""")


class InstagramJobRunner:
    def __init__(self, config=None):
        self.cfg = config or self._load_config()
        self.api = ApiF4F()
        self.adb = None
        self.account_id = None
        self.username = None
        self.package_name = None
        self.stats = {
            "followed": 0,
            "already": 0,
            "skipped": 0,
            "errors": 0,
            "coins_earned": 0,
        }
        self.jobs_since_human = 0

    def _load_config(self):
        cfg = {
            "f4f_user": "",
            "f4f_pass": "",
            "instagram_username": "",
            "adb_serial": "auto",
            "instagram_package": "auto",
            "max_jobs_per_session": 50,
            "delay_min": 8,
            "delay_max": 18,
            "profile_load_timeout": 8,
            "verify_timeout": 3,
            "human_behavior": True,
            "human_behavior_every_n_jobs": 5,
            "human_behavior_scroll_times": 3,
        }
        if os.path.isfile(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg.update(json.load(f))
            except Exception:
                pass
        return cfg

    def _select_instagram_account(self):
        """Lấy và chọn tài khoản Instagram từ F4F."""
        log.info("Lấy danh sách tài khoản Instagram liên kết trên F4F...")
        try:
            acc_list = self.api.get_active_accounts("instagram")
        except Exception as e:
            log.error(f"Lỗi gọi API F4F lấy tài khoản Instagram: {e}")
            sys.exit(1)

        if not acc_list:
            log.error(f"{R}Không tìm thấy tài khoản Instagram nào liên kết trên F4F!{D}")
            log.error("Vui lòng vào follow4follow.net -> Thêm tài khoản Instagram trước khi chạy tool.")
            sys.exit(1)

        saved_user = self.cfg.get("instagram_username", "").strip()

        # 1. Nếu chỉ có 1 tài khoản duy nhất -> Tự động dùng
        if len(acc_list) == 1:
            chosen = acc_list[0]
            self.username = chosen.get("username")
            self.account_id = chosen.get("id")
            self.cfg["instagram_username"] = self.username
            log.info(f"{G}✓ Tự động chọn tài khoản Instagram:{D} {C}@{self.username}{D} (ID: {self.account_id})")
            return

        # 2. Nếu có nhiều tài khoản -> Hiển thị menu chọn
        default_idx = 1
        for idx, acc in enumerate(acc_list, start=1):
            if saved_user and acc.get("username") == saved_user:
                default_idx = idx
                break

        print(f"\n{C}┌── Danh sách tài khoản Instagram liên kết ──────────────────────┐{D}")
        for idx, acc in enumerate(acc_list, start=1):
            name = acc.get("username") or acc.get("name")
            acc_id = acc.get("id")
            is_def = f" {G}(Mặc định){D}" if idx == default_idx else ""
            print(f"{C}│{D}  [{idx}] {W}@{name:<22}{D} │ ID: {acc_id:<6} {is_def} {C}│{D}")
        print(f"{C}└────────────────────────────────────────────────────────────────┘{D}")

        def_name = acc_list[default_idx - 1].get("username")
        selected_idx = default_idx
        try:
            choice = input(f"{Y}[?] Chọn tài khoản Instagram [1-{len(acc_list)}] (Enter = @{def_name}): {D}").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(acc_list):
                selected_idx = int(choice)
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)

        chosen = acc_list[selected_idx - 1]
        self.username = chosen.get("username")
        self.account_id = chosen.get("id")
        self.cfg["instagram_username"] = self.username
        log.info(f"{G}✓ Đã chọn tài khoản Instagram:{D} {C}@{self.username}{D} (ID: {self.account_id})")

    def setup(self):
        """Đăng nhập F4F, chọn tài khoản và kết nối ADB."""
        user = self.cfg.get("f4f_user")
        pwd = self.cfg.get("f4f_pass")
        if not user or not pwd or user == "your_f4f_username":
            log.error("Chưa cấu hình tài khoản Follow4Follow trong config.json!")
            sys.exit(1)

        log.info("Đang đăng nhập Follow4Follow ...")
        self.api.login(user, pwd, verbose=False)
        u_info = self.api.user
        log.info(
            f"{G}✓ Đăng nhập thành công:{D} {u_info['username']} | "
            f"Số dư: {Y}{u_info['balance']} xu{D} | Chờ: {u_info['balance_pending']} xu"
        )

        self._select_instagram_account()

        serial = self.cfg.get("adb_serial", "auto")
        log.info(f"Đang kết nối thiết bị ADB ({serial}) ...")
        self.adb = AdbController(serial=serial)
        w, h = self.adb.get_screen_size()
        log.info(f"{G}✓ ADB sẵn sàng:{D} Màn hình {w}x{h}")

        pkg_cfg = self.cfg.get("instagram_package", "auto")
        if not pkg_cfg or pkg_cfg == "auto":
            self.package_name = self.adb.detect_instagram_package()
        else:
            self.package_name = pkg_cfg
        log.info(f"Instagram Package: {C}{self.package_name}{D}")

        self._ensure_instagram_running()

    def _ensure_instagram_running(self):
        """Khởi động ứng dụng Instagram nếu chưa bật."""
        current = self.adb.shell("dumpsys window | grep mCurrentFocus")
        if self.package_name not in current:
            log.info("Mở ứng dụng Instagram...")
            self.adb.shell(f"monkey -p {self.package_name} -c android.intent.category.LAUNCHER 1")
            time.sleep(3)
            self.adb.dismiss_popups(package=self.package_name)

    def process_job(self, job):
        """Xử lý 1 job Follow Instagram."""
        job_id = job["id"]
        object_id = job.get("object_id") or ""
        reward = int(job.get("reward_amount", 35))

        log.info(f"👉 Bắt đầu Job #{job_id}: Follow @{object_id} (+{reward} xu)")

        # 1. Mở trang cá nhân Instagram
        ok = self.adb.open_instagram_profile(object_id, package_name=self.package_name)
        if not ok:
            log.warning(f"  [!] Không thể mở trang cá nhân @{object_id} -> Bỏ qua job")
            self._skip(job_id, object_id)
            return "skipped"

        # Đợi trang tải
        time.sleep(random.uniform(1.8, 2.8))
        self.adb.dismiss_popups(package=self.package_name)

        # 2. Thực hiện Follow
        state = self.adb.follow_profile(
            package=self.package_name,
            load_timeout=self.cfg.get("profile_load_timeout", 8),
            verify_timeout=self.cfg.get("verify_timeout", 3),
        )

        if state == "already":
            log.info(f"  {Y}ℹ Đã follow @{object_id} từ trước! Nhận thưởng...{D}")
            self.stats["already"] += 1
            self._complete(job_id, reward)
            return "already"

        if state in ("clicked", "click_unverified"):
            log.info(f"  {G}✓ Đã bấm Follow @{object_id} thành công!{D}")
            self.stats["followed"] += 1
            self._complete(job_id, reward)
            return "followed"

        if state == "requested":
            log.info(f"  {Y}ℹ Tài khoản riêng tư (Đã gửi yêu cầu theo dõi)! Nhận thưởng...{D}")
            self.stats["followed"] += 1
            self._complete(job_id, reward)
            return "followed"

        # Nếu không tìm thấy profile / bị khóa
        log.warning(f"  {R}✗ Không tìm thấy nút Follow hoặc trang lỗi (state={state}) -> Bỏ qua job{D}")
        self.stats["skipped"] += 1
        self._skip(job_id, object_id)
        return "skipped"

    def _complete(self, job_id, reward):
        try:
            res = self.api.complete_job_ig(job_id, self.account_id, type_job="follow")
            earned = int(res.get("data", {}).get("coin_received") or reward)
            self.stats["coins_earned"] += earned
            log.info(f"  {G}💰 Nhận thành công +{earned} xu! (Tổng kiếm: ~{self.stats['coins_earned']} xu){D}")
        except Exception as e:
            log.error(f"  {R}[!] Lỗi báo cáo complete-job F4F: {e}{D}")

    def _skip(self, job_id, object_id):
        try:
            self.api.skip_job_ig(job_id, self.account_id, self.username, object_id)
            log.info(f"  {Y}↷ Đã gửi yêu cầu bỏ qua (skip) job #{job_id}{D}")
        except Exception as e:
            log.error(f"  [!] Lỗi skip job F4F: {e}")

    def run(self, max_jobs=None):
        """Vòng lặp chạy auto jobs Follow Instagram."""
        self.setup()
        max_jobs = max_jobs or self.cfg.get("max_jobs_per_session", 50)
        log.info(f"Bắt đầu phiên chạy: Tối đa {max_jobs} job(s)")

        total_processed = 0
        consecutive_errors = 0

        while total_processed < max_jobs:
            try:
                job_data = self.api.get_job_ig(self.username, type_job="follow")
                jobs = job_data.get("data", {}).get("jobs", [])
            except Exception as e:
                log.error(f"Lỗi lấy job từ F4F: {e}")
                time.sleep(5)
                continue

            if not jobs:
                log.info(f"{Y}Hiện tại chưa có job Instagram mới. Chờ 15s thử lại...{D}")
                time.sleep(15)
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

                # Chống ban (Lướt feed mô phỏng người thật)
                if self.cfg.get("human_behavior", True):
                    every_n = int(self.cfg.get("human_behavior_every_n_jobs", 5))
                    scroll_times = int(self.cfg.get("human_behavior_scroll_times", 3))
                    if every_n > 0 and self.jobs_since_human >= every_n:
                        log.info(f"  {C}☕ [Anti-Ban] Lướt feed Instagram {scroll_times} lần...{D}")
                        self.adb.simulate_human_browse(scroll_times=scroll_times)
                        self.jobs_since_human = 0

                # Delay ngẫu nhiên giữa các job
                if total_processed < max_jobs:
                    d_min = self.cfg.get("delay_min", 8)
                    d_max = self.cfg.get("delay_max", 18)
                    delay = random.uniform(d_min, d_max)
                    log.info(f"  ⏳ Chờ {delay:.1f}s trước job tiếp theo...")
                    time.sleep(delay)

        self._print_summary()

    def _print_summary(self):
        s = self.stats
        total = s["followed"] + s["already"] + s["skipped"] + s["errors"]
        print(f"""
{C}╔══════════════════════════════════════════════════╗
║             KẾT QUẢ PHIÊN INSTAGRAM              ║
╠══════════════════════════════════════════════════╣
║  {G}Follow thành công : {s['followed']:>5}{C}                       ║
║  {Y}Đã follow từ trước: {s['already']:>5}{C}                       ║
║  {Y}Bỏ qua (skip)     : {s['skipped']:>5}{C}                       ║
║  {R}Lỗi               : {s['errors']:>5}{C}                       ║
║  ─────────────────────────                       ║
║  {W}Tổng xử lý        : {total:>5}{C}                       ║
║  {G}Coin kiếm được     : ~{s['coins_earned']:>4}{C}                       ║
╚══════════════════════════════════════════════════╝{D}
""")
        log.info(f"File log: {log_file}")


if __name__ == "__main__":
    banner()
    runner = InstagramJobRunner()
    try:
        runner.run()
    except KeyboardInterrupt:
        log.info(f"\n{Y}Đã dừng bởi người dùng (Ctrl+C){D}")
        runner._print_summary()
    except Exception as e:
        log.exception(f"{R}Lỗi không xử lý được: {e}{D}")
        runner._print_summary()
