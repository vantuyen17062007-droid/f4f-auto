"""
api_f4f.py — Proxy tương thích ngược.
Toàn bộ mã nguồn API Client đã được chuyển sang api/f4f_client.py
"""
import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api.f4f_client import ApiF4F, F4F, f4f, F4FInstagram, f4f_ig

__all__ = ["ApiF4F", "F4F", "f4f", "F4FInstagram", "f4f_ig"]

if __name__ == "__main__":
    from config.settings import load_config
    cfg = load_config()
    u, p = cfg.get("f4f_user"), cfg.get("f4f_pass")
    if u and p and u != "your_f4f_username":
        client = ApiF4F()
        client.login(u, p)
