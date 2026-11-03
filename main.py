"""
Follow4Follow Multi-Platform Auto Runner (TikTok & Instagram)
=============================================================
Entrypoint chính điều phối toàn bộ hệ thống:
  - Khởi tạo banner & giao diện dòng lệnh
  - Luồng khởi động gọn: chọn nền tảng -> dùng cấu hình cũ/cài lại
    -> kiểm tra tài khoản -> (TikTok) chọn chế độ job -> chạy
  - Kết nối thiết bị ADB có vòng thử lại & bảng Preflight
  - Hỗ trợ chạy đa nền tảng: PC (Windows/Linux) & Điện thoại Android (Termux)
"""

import sys
import os

# Thêm thư mục gốc vào PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.helpers import GREEN, RED, YELLOW, RESET
from core.ui import print_banner, render_session_overview
from config.settings import (
    load_config,
    interactive_configure,
    ensure_credentials,
    save_config,
    select_platform_menu,
    select_use_saved_config,
    select_job_type_menu,
)
from services.tiktok_service import TikTokJobRunner
from services.instagram_service import InstagramJobRunner


def main() -> int:
    print_banner()

    cfg = load_config()

    # 1. Chọn nền tảng làm job (TikTok / Instagram) — luôn là bước đầu tiên.
    platform = select_platform_menu(cfg)
    cfg["platform"] = platform

    # 2. Hỏi dùng lại cấu hình đã lưu (log cũ) hay cài đặt lại từ đầu.
    #    Lần đầu chạy (config trống) sẽ tự vào trình cài đặt, không hỏi thừa.
    if not select_use_saved_config(cfg):
        cfg = interactive_configure(cfg)

    # 3. Bảo đảm có Username/Password F4F; thiếu thì wizard, vẫn thiếu thì dừng sớm.
    ensure_credentials(cfg)

    # 4. Với TikTok: chọn chế độ job (Follow / Like / All).
    if platform == "tiktok":
        select_job_type_menu(cfg)

    # 5. Lưu toàn bộ lựa chọn một lần duy nhất + hiển thị tổng quan trước khi chạy.
    save_config(cfg)
    print(f"\n{GREEN}✓ Đã lưu cấu hình — bắt đầu phiên làm việc...{RESET}")
    render_session_overview(cfg)

    runner = None
    try:
        # 6. Khởi tạo service (đăng nhập F4F, chọn nick, kết nối ADB, mở app)
        if platform == "instagram":
            runner = InstagramJobRunner(config=cfg)
        else:
            runner = TikTokJobRunner(
                config=cfg, job_type=cfg.get("job_type", "all")
            )

        # 7. Thực thi phiên làm việc
        runner.run()
        return 0
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Đã dừng bởi người dùng (Ctrl+C).{RESET}")
        if runner:
            runner.print_summary()
        return 130
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n{RED}Lỗi không xử lý được: {e}{RESET}")
        if runner:
            runner.print_summary()
        return 1


if __name__ == "__main__":
    sys.exit(main())
