"""
tools/find_video_cli.py — Công cụ tìm kiếm và phân giải link / Video ID TikTok
==============================================================================
"""

import sys
import os
import argparse

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.helpers import CYAN, GREEN, YELLOW, RED, RESET, resolve_video_id


def main():
    parser = argparse.ArgumentParser(description="Tool phân giải Video ID TikTok")
    parser.add_argument("--url", "-u", help="URL video TikTok")
    args = parser.parse_args()

    target = args.url
    if not target:
        target = input(f"{YELLOW}[?] Nhập URL TikTok cần phân giải: {RESET}").strip()

    if not target:
        print(f"{RED}[!] Chưa nhập URL.{RESET}")
        sys.exit(1)

    print(f"\n{CYAN}[*] Đang phân giải link: {target}{RESET}")
    video_id, full_url = resolve_video_id(target)

    print(f"{GREEN}[✓] Kết quả:{RESET}")
    print(f"    - Video ID:  {CYAN}{video_id}{RESET}")
    print(f"    - Full URL:  {GREEN}{full_url}{RESET}")


if __name__ == "__main__":
    main()
