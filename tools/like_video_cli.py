"""
tools/like_video_cli.py — Công cụ dòng lệnh (CLI) like video TikTok độc lập
===========================================================================
Sử dụng:
  python tools/like_video_cli.py --url https://vt.tiktok.com/...
  python tools/like_video_cli.py --id 7699698031045790984
"""

import sys
import os
import argparse
import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.helpers import CYAN, GREEN, YELLOW, RED, RESET, resolve_video_id
from core.adb import AdbController


def main():
    parser = argparse.ArgumentParser(description="Tool CLI like video TikTok độc lập qua ADB")
    parser.add_argument("--url", "-u", help="URL video TikTok (hỗ trợ cả short link vt.tiktok.com)")
    parser.add_argument("--id", "-i", help="ID video TikTok (dãy số)")
    parser.add_argument("--serial", "-s", default="auto", help="Serial thiết bị ADB (mặc định: auto)")
    args = parser.parse_args()

    target = args.url or args.id
    if not target:
        target = input(f"{YELLOW}[?] Nhập URL hoặc Video ID TikTok: {RESET}").strip()

    if not target:
        print(f"{RED}[!] Chưa cung cấp URL hoặc ID video.{RESET}")
        sys.exit(1)

    print(f"\n{CYAN}[*] Khởi tạo kết nối ADB...{RESET}")
    adb = AdbController(serial=args.serial)
    pkg = adb.detect_tiktok_package()
    print(f"{GREEN}[✓] Thiết bị: {adb.serial} | TikTok Package: {pkg}{RESET}")

    video_id, full_url = resolve_video_id(target)
    print(f"{CYAN}[*] Đang mở video: {GREEN}{video_id or target}{RESET}")
    ok = adb.open_tiktok_video(target, package_name=pkg)
    if not ok:
        print(f"{RED}[!] Không thể mở video qua ADB.{RESET}")
        sys.exit(1)

    time.sleep(2)
    print(f"{CYAN}[*] Kiểm tra trạng thái và bấm Thích (Like)...{RESET}")
    res = adb.like_video(package=pkg, load_timeout=6, verify_timeout=3)

    if res == "already":
        print(f"{YELLOW}[✓] Video đã được thích từ trước!{RESET}")
    elif res in ("clicked", "click_unverified"):
        print(f"{GREEN}[✓] Đã thả tim (Like) video thành công!{RESET}")
    else:
        print(f"{RED}[✗] Thao tác thất bại: {res}{RESET}")


if __name__ == "__main__":
    main()
