"""
services/base_runner.py — Lớp cơ sở trừu tượng cho các Auto Job Runner
======================================================================
Cung cấp các cơ chế dùng chung:
  - Khởi tạo logging phiên làm việc
  - Theo dõi thống kê (stats): followed, liked, already, skipped, errors, coins_earned
  - Cơ chế Anti-Ban lướt feed mô phỏng người thật
  - Delay ngẫu nhiên giữa các job
  - In bảng tổng kết kết quả phiên chạy
"""

import os
import sys
import time
import random
import logging
import itertools
from datetime import datetime
from typing import Dict, Any, Optional

from core.helpers import CYAN, RESET, strip_ansi
from core.helpers import YELLOW
from core.ui import render_summary_report, render_preflight
from core.adb import AdbController, AdbConnectionError
from config.settings import LOG_DIR, cleanup_old_logs


class _StripAnsiFormatter(logging.Formatter):
    """Formatter loại bỏ mã màu ANSI trước khi ghi ra file log."""

    def format(self, record):
        return strip_ansi(super().format(record))


class BaseJobRunner:
    # Bộ đếm đơn điệu: bảo đảm không hai phiên nào trùng tên file log.
    _LOG_SEQ = itertools.count(1)

    def __init__(self, platform_name: str, config: Optional[Dict[str, Any]] = None):
        self.platform_name = platform_name
        self.cfg = config or {}
        self.api = None
        self.adb = None
        self.package_name = None
        self.jobs_since_human = 0
        # Anti-Ban: ngưỡng kích hoạt vẽ ngẫu nhiên (không cố định theo nhịp)
        self._human_trigger_at = self._draw_human_trigger()
        # Chống xử lý lặp cùng một job trong một phiên (API có thể trả lại job cũ).
        self.job_attempts: Dict[str, int] = {}
        self.max_job_attempts = 2

        self.stats = {
            "followed": 0,
            "liked": 0,
            "already": 0,
            "skipped": 0,
            "errors": 0,
            "coins_earned": 0,
        }

        # Dọn dẹp log cũ hơn N ngày
        cleanup_old_logs(self.cfg.get("auto_clean_logs_days", 7))

        # Thiết lập file log phiên (timestamp + số thứ tự: luôn duy nhất)
        self.log_file = os.path.join(
            LOG_DIR,
            f"{self.platform_name.lower()}_"
            f"{datetime.now():%Y%m%d_%H%M%S_%f}_{next(self._LOG_SEQ):03d}.log"
        )
        self.log = logging.getLogger(
            f"f4f-{self.platform_name.lower()}-{id(self):x}"
        )
        self.log.propagate = False
        self._setup_logging()

    def _setup_logging(self):
        """Khởi tạo logger xuất ra cả Console lẫn file log."""
        self.log.setLevel(logging.INFO)
        # Nếu logger đã có handler (ví dụ runner được tạo lại), đóng và thay mới
        # để tránh ghi nhầm sang file log của phiên trước.
        for handler in list(self.log.handlers):
            self.log.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

        fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", datefmt="%H:%M:%S")
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setFormatter(fmt)
        f_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        f_handler.setFormatter(_StripAnsiFormatter("%(asctime)s │ %(levelname)-7s │ %(message)s", datefmt="%H:%M:%S"))
        self.log.addHandler(c_handler)
        self.log.addHandler(f_handler)

    def can_attempt_job(self, job_id) -> bool:
        """True nếu job chưa vượt quá số lần thử tối đa trong phiên."""
        return self.job_attempts.get(str(job_id), 0) < self.max_job_attempts

    def mark_job_attempt(self, job_id):
        key = str(job_id)
        self.job_attempts[key] = self.job_attempts.get(key, 0) + 1

    def _draw_human_trigger(self) -> int:
        """
        Vẽ ngẫu nhiên số job tiếp theo trước khi kích hoạt anti-ban.

        Cấu hình `human_behavior_every_n_jobs` là cỡ trung bình; vòng thực tế
        lệch ±2 job thì máy chủ khó nhận ra nhịp cố định.
        """
        every_n = int(self.cfg.get("human_behavior_every_n_jobs", 5) or 5)
        low = max(1, every_n - 2)
        return random.randint(low, every_n + 2)

    def trigger_anti_ban(self):
        """Kích hoạt lướt feed chống ban tại ngưỡng ngẫu nhiên (không cố định)."""
        if not self.cfg.get("human_behavior", True) or not self.adb:
            return

        every_n = int(self.cfg.get("human_behavior_every_n_jobs", 5) or 5)

        if self.jobs_since_human >= self._human_trigger_at:
            # Số lượt lướt mỗi vòng cũng ngẫu nhiên quanh giá trị cấu hình ±1
            scroll_cfg = int(self.cfg.get("human_behavior_scroll_times", 2) or 2)
            scroll_times = random.randint(max(1, scroll_cfg - 1), scroll_cfg + 1)

            self.log.info(
                f"  {CYAN}☕ [Anti-Ban] Đã xử lý {self.jobs_since_human} job(s) "
                f"(giãn cách ngẫu nhiên {every_n}±2) -> Lướt feed {scroll_times} lần...{RESET}"
            )
            try:
                self.adb.simulate_human_browse(scroll_times=scroll_times, package_name=self.package_name)
            except Exception as e:
                self.log.warning(f"  [!] Không thể lướt feed anti-ban: {e}")
            finally:
                self.jobs_since_human = 0
                # Vẽ lại nhịp ngẫu nhiên cho vòng kế tiếp
                self._human_trigger_at = self._draw_human_trigger()

    def connect_device(self):
        """
        Kết nối ADB và hiển thị bảng Preflight thiết bị.

        Nếu chưa cắm/không kết nối được thiết bị:
        - TTY    : hướng dẫn ngắn, Enter = thử lại, q = thoát.
        - Non-TTY: báo lỗi rõ ràng và dừng (exit 1).
        """
        serial = str(self.cfg.get("adb_serial", "auto") or "auto")
        interactive = bool(sys.stdin and sys.stdin.isatty())

        while True:
            self.log.info(f"Đang kết nối thiết bị ADB ({serial}) ...")
            try:
                self.adb = AdbController(serial=serial)
                break
            except (AdbConnectionError, RuntimeError) as e:
                if not interactive:
                    self.log.error(f"[ADB] {e}")
                    sys.exit(1)

                self.log.warning(f"{YELLOW}✗ Chưa kết nối được thiết bị Android.{RESET}")
                print(f"{'':4}→ Bật USB debugging, cắm cáp hoặc khai báo adb_serial trong config.json")
                print(f"{'':4}→ Kiểm tra lại bằng: adb devices (phải có trạng thái device)")
                print(f"{'':4}→ ADB wifi: adb connect <ip>:<port>")

                try:
                    ans = input(
                        f"{CYAN}›{RESET} Enter = thử lại  {YELLOW}|{RESET}  q = thoát  » "
                    ).strip().lower()
                except KeyboardInterrupt:
                    print("\nĐã hủy.")
                    sys.exit(130)
                except EOFError:
                    print("\nĐã hủy.")
                    sys.exit(1)

                if ans in ("q", "quit", "exit", "thoat", "thoát"):
                    self.log.error("Người dùng hủy vì không có thiết bị ADB.")
                    sys.exit(1)

        info = self.adb.get_device_info()
        render_preflight(
            f"{self.platform_name.upper()} • DEVICE READY",
            [
                ("Thiết bị", info["model"]),
                ("Serial", info["serial"]),
                ("Android", info["android"]),
                ("Màn hình", info["screen"]),
            ],
        )

    def sleep_delay(self):
        """Nghỉ ngẫu nhiên giữa các job theo khoảng delay cấu hình."""
        d_min = self.cfg.get("delay_min", 8)
        d_max = self.cfg.get("delay_max", 18)
        delay = random.uniform(d_min, d_max)
        self.log.info(f"  ⏳ Chờ {delay:.1f}s trước job tiếp theo...")
        time.sleep(delay)

    def print_summary(self):
        """In bảng tóm tắt kết quả phiên chạy theo thiết kế hiện đại."""
        render_summary_report(self.platform_name, self.stats, self.log_file)
