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
from datetime import datetime
from typing import Dict, Any, Optional

from core.helpers import CYAN, GREEN, YELLOW, RED, WHITE, RESET
from config.settings import LOG_DIR, cleanup_old_logs


class BaseJobRunner:
    def __init__(self, platform_name: str, config: Optional[Dict[str, Any]] = None):
        self.platform_name = platform_name
        self.cfg = config or {}
        self.api = None
        self.adb = None
        self.package_name = None
        self.jobs_since_human = 0

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

        # Thiết lập file log phiên
        self.log_file = os.path.join(
            LOG_DIR,
            f"{self.platform_name.lower()}_{datetime.now():%Y%m%d_%H%M%S}.log"
        )
        self.log = logging.getLogger(f"f4f-{self.platform_name.lower()}")
        self._setup_logging()

    def _setup_logging(self):
        """Khởi tạo logger xuất ra cả Console lẫn file log."""
        self.log.setLevel(logging.INFO)
        if not self.log.handlers:
            fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", datefmt="%H:%M:%S")
            c_handler = logging.StreamHandler(sys.stdout)
            c_handler.setFormatter(fmt)
            f_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            f_handler.setFormatter(fmt)
            self.log.addHandler(c_handler)
            self.log.addHandler(f_handler)

    def trigger_anti_ban(self):
        """Kích hoạt lướt feed chống ban nếu đạt số job cấu hình."""
        if not self.cfg.get("human_behavior", True) or not self.adb:
            return

        every_n = int(self.cfg.get("human_behavior_every_n_jobs", 5))
        scroll_times = int(self.cfg.get("human_behavior_scroll_times", 2))

        if every_n > 0 and self.jobs_since_human >= every_n:
            self.log.info(
                f"  {CYAN}☕ [Anti-Ban] Đã xử lý {self.jobs_since_human} job(s) -> "
                f"Lướt feed {scroll_times} lần...{RESET}"
            )
            self.adb.simulate_human_browse(scroll_times=scroll_times)
            self.jobs_since_human = 0

    def sleep_delay(self):
        """Nghỉ ngẫu nhiên giữa các job theo khoảng delay cấu hình."""
        d_min = self.cfg.get("delay_min", 8)
        d_max = self.cfg.get("delay_max", 18)
        delay = random.uniform(d_min, d_max)
        self.log.info(f"  ⏳ Chờ {delay:.1f}s trước job tiếp theo...")
        time.sleep(delay)

    def print_summary(self):
        """In bảng tóm tắt kết quả phiên chạy theo thiết kế hiện đại."""
        s = self.stats
        total = s["followed"] + s["liked"] + s["already"] + s["skipped"] + s["errors"]
        plat_tag = f"SESSION REPORT ({self.platform_name.upper()})"

        print(f"\n{CYAN}╭─ {WHITE}{plat_tag:<32}{CYAN} ─────────────────────╮{RESET}")
        print(f"{CYAN}│{RESET}  {GREEN}✓{RESET} Follow thành công   {GREEN}{s['followed']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {GREEN}♥{RESET} Like thành công     {GREEN}{s['liked']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}●{RESET} Đã thực hiện trước  {YELLOW}{s['already']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}↷{RESET} Đã bỏ qua           {YELLOW}{s['skipped']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {RED}!{RESET} Lỗi                 {RED}{s['errors']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}├────────────────────────────────────────────────────────────┤{RESET}")
        print(f"{CYAN}│{RESET}  Tổng job xử lý       {WHITE}{total:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  Coin nhận được       {GREEN}~{s['coins_earned']:>6}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────────╯{RESET}\n")
        self.log.info(f"File log chi tiết: {self.log_file}")
