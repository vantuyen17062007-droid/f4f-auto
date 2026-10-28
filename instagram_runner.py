"""
instagram_runner.py — Proxy tương thích ngược.
Toàn bộ nghiệp vụ chạy Instagram đã được chuyển sang services/instagram_service.py
"""
import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.instagram_service import InstagramJobRunner
from core.helpers import print_banner, YELLOW, RED, RESET
from config.settings import load_config, check_or_prompt_credentials

if __name__ == "__main__":
    print_banner()
    cfg = load_config()
    cfg = check_or_prompt_credentials(cfg)
    runner = InstagramJobRunner(config=cfg)
    try:
        runner.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Đã dừng bởi người dùng (Ctrl+C).{RESET}")
        runner.print_summary()
    except Exception as e:
        print(f"\n{RED}Lỗi không xử lý được: {e}{RESET}")
        runner.print_summary()
