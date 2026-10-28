"""
Follow4Follow Multi-Platform Auto Runner (TikTok & Instagram)
=============================================================
Entrypoint chính điều phối toàn bộ hệ thống:
  - Khởi tạo banner & giao diện dòng lệnh
  - Kiểm tra và cấu hình trực tiếp từ terminal (không cần sửa config.json thủ công)
  - Chọn nền tảng (TikTok / Instagram) và điều phối service tương ứng
  - Hỗ trợ chạy đa nền tảng: PC (Windows/Linux) & Điện thoại Android (Termux)
"""

import sys
import os

# Thêm thư mục gốc vào PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.helpers import YELLOW, RED, RESET
from core.ui import print_banner
from config.settings import (
    load_config,
    check_or_prompt_credentials,
    select_platform_menu,
    select_job_type_menu,
)
from services.tiktok_service import TikTokJobRunner
from services.instagram_service import InstagramJobRunner


def main():
    print_banner()

    # 1. Tải & kiểm tra cấu hình
    cfg = load_config()
    cfg, quick_start = check_or_prompt_credentials(cfg)

    # 2. Xác định nền tảng chạy
    platform = cfg.get("platform", "tiktok").lower()

    # 3. Khởi tạo service theo nền tảng
    if platform == "instagram":
        runner = InstagramJobRunner(config=cfg)
    else:
        job_type = cfg.get("job_type", "all")
        runner = TikTokJobRunner(config=cfg, job_type=job_type)

    # 4. Thực thi phiên làm việc
    try:
        runner.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Đã dừng bởi người dùng (Ctrl+C).{RESET}")
        runner.print_summary()
    except Exception as e:
        print(f"\n{RED}Lỗi không xử lý được: {e}{RESET}")
        runner.print_summary()


if __name__ == "__main__":
    main()
