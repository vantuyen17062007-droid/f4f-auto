"""
tiktok_find_video.py — Proxy tương thích ngược chuyển tiếp sang tools/find_video_cli.py
"""
import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools.find_video_cli import main

if __name__ == "__main__":
    main()
