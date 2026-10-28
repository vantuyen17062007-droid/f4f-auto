"""
test_run.py — Proxy tương thích ngược chuyển tiếp sang tools/test_tiktok.py
"""
import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools.test_tiktok import *
